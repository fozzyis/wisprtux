"""Transcription engine — bridges the GUI to WisprTux's backend.
# pylint: disable=too-many-instance-attributes, import-outside-toplevel, too-many-locals, too-many-statements

Handles audio capture, model inference, and output routing (clipboard,
active-window typing).  Runs the heavy work in a background thread so
the GTK main loop stays responsive.
"""

import logging
import os
import threading
import queue

import numpy as np

import whisper

from wisprtux.gui.window_tracker import (
    WindowSnapshot,
    set_clipboard,
    type_text,
    focus_window,
)

log = logging.getLogger(__name__)

MODEL_FILES = {
    "tiny.en": "tiny.en.pt",
    "base.en": "base.en.pt",
    "small.en": "small.en.pt",
    "medium.en": "medium.en.pt",
    "large": "large.pt",
}

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")


class TranscriptionEngine:
    """Manages audio capture, Whisper model, and streaming transcription."""

    def __init__(self):
        self._model = None
        self._model_name = "tiny.en"
        self._offline = False
        self._recording = False
        self._auto_clipboard = False
        self._auto_type = False

        self._status_cb = None
        self._transcript_cb = None
        self._audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = None

        # Snapshot of the window that was active when recording started
        self._origin_window = None

    @property
    def origin_window(self):
        """The window that was active when recording started"""
        return self._origin_window

    @property
    def auto_type(self):
        """Whether auto-typing is enabled"""
        return self._auto_type

    # ── Callback wiring (called from GUI) ──────────────────────

    def connect_status(self, callback):
        """Connect a callback to receive status updates"""
        self._status_cb = callback

    def connect_transcript(self, callback):
        """Connect a callback to receive transcription results"""
        self._transcript_cb = callback

    def _emit_status(self, text):
        if self._status_cb:
            self._status_cb(text)

    def _emit_transcript(self, result):
        if self._transcript_cb:
            self._transcript_cb(result)

    # ── Settings ───────────────────────────────────────────────

    def set_model(self, model_name):
        self._model_name = model_name
        self._model = None

    def set_offline(self, offline):
        """Set whether to only use locally cached models"""
        self._offline = offline

    def set_auto_clipboard(self, enabled):
        """Set whether to automatically copy results to clipboard"""
        self._auto_clipboard = enabled

    def set_auto_type(self, enabled):
        """Set whether to automatically type results into active window"""
        self._auto_type = enabled

    def set_hotkey(self, _key_name):
        """Placeholder — the global hotkey is managed by the window."""

    # ── Model loading ──────────────────────────────────────────

    def _load_model(self):
        """Load the Whisper model (locally or download if needed)"""
        self._emit_status("Loading model...")
        file_name = MODEL_FILES.get(self._model_name, "tiny.en.pt")
        local_path = os.path.join(MODELS_DIR, file_name)

        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"

            if os.path.exists(local_path):
                self._model = whisper.load_model(local_path).to(device)
            elif not self._offline:
                model_size = self._model_name.replace(".en", "")
                self._model = whisper.load_model(
                    model_size, download_root=MODELS_DIR
                ).to(device)
            else:
                self._emit_status("Model not available offline")
                return False
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._emit_status(f"Model load failed: {exc}")
            return False

        self._emit_status("Model loaded")
        return True

    # ── Recording control ──────────────────────────────────────

    def start_recording(self):
        """Start capturing audio and running transcription in a background thread"""
        if self._recording:
            return

        # Capture the currently active window *before* our own window
        # steals focus (the user may have clicked our record button,
        # but for global-hotkey use, this captures the right target).
        self._origin_window = WindowSnapshot()
        log.info("Origin window captured: %s", self._origin_window)

        self._recording = True
        self._stop_event.clear()
        self._audio_queue = queue.Queue()
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def stop_recording(self):
        """Signal the background thread to stop recording"""
        if not self._recording:
            return
        self._recording = False
        self._stop_event.set()
        self._emit_status("Ready")

    # ── Output routing ─────────────────────────────────────────

    def _route_final_text(self, text):
        """Send finalized text to clipboard / active window as configured."""
        if not text:
            return

        if self._auto_clipboard:
            set_clipboard(text)
            log.info("Copied to clipboard: %s", text[:60])

        if self._auto_type and self._origin_window and self._origin_window.valid:
            focus_window(self._origin_window.window_id)
            type_text(text)
            log.info(
                "Typed into window %s: %s",
                self._origin_window.window_id,
                text[:60],
            )

    # ── Worker loop ────────────────────────────────────────────

    # pylint: disable=too-many-branches, too-many-statements
    def _worker_loop(self):
        """Background worker: loads model, captures audio, transcribes."""
        if self._model is None:
            if not self._load_model():
                self._recording = False
                return

        self._emit_status("Recording...")

        try:
            import pyaudio
        except ImportError:
            self._emit_status("PyAudio not installed")
            self._recording = False
            return

        audio = pyaudio.PyAudio()
        try:
            stream = audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=16000,
                input=True,
                frames_per_buffer=1024,
            )
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self._emit_status(f"Audio error: {exc}")
            audio.terminate()
            self._recording = False
            return

        window = []
        transcribe_interval = 0.5
        chunks_per_interval = int(16000 * transcribe_interval / 1024)
        chunk_count = 0
        prev_text = ""
        stable_cycles = 0

        try:
            while not self._stop_event.is_set():
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                except Exception:  # pylint: disable=broad-exception-caught
                    continue

                window.append(data)
                chunk_count += 1

                if chunk_count >= chunks_per_interval and window:
                    chunk_count = 0
                    self._emit_status("Transcribing...")

                    audio_data = b"".join(window)
                    arr = (
                        np.frombuffer(audio_data, np.int16).flatten().astype(np.float32)
                        / 32768.0
                    )

                    try:
                        result = self._model.transcribe(
                            arr,
                            fp16=False,
                            language="en",
                            temperature=0.1,
                            logprob_threshold=-0.5,
                        )
                        text = result.get("text", "").strip()
                    except Exception:  # pylint: disable=broad-exception-caught
                        text = ""

                    if text:
                        if text == prev_text:
                            stable_cycles += 1
                        else:
                            stable_cycles = 0
                            prev_text = text

                        if stable_cycles >= 2:
                            self._emit_transcript(
                                {"is_partial": False, "data": {"text": text}}
                            )
                            self._route_final_text(text)
                            window = []
                            prev_text = ""
                            stable_cycles = 0
                        else:
                            self._emit_transcript(
                                {"is_partial": True, "data": {"text": text}}
                            )

                    self._emit_status("Recording...")
        finally:
            stream.stop_stream()
            stream.close()
            audio.terminate()
            self._emit_status("Ready")
