"""Transcription engine — bridges the GUI to WhisperFlow's backend"""

import os
import threading
import asyncio
import queue

import numpy as np

import whisper
from whisper import Whisper


# Whisper model filename mapping
MODEL_FILES = {
    "tiny.en": "tiny.en.pt",
    "base.en": "base.en.pt",
    "small.en": "small.en.pt",
    "medium.en": "medium.en.pt",
    "large": "large.pt",
}

MODELS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "models")


class TranscriptionEngine:
    """Manages audio capture, Whisper model, and streaming transcription.

    Runs the async transcription loop in a background thread so the
    GTK main loop stays responsive.
    """

    def __init__(self):
        self._model = None
        self._model_name = "tiny.en"
        self._offline = False
        self._recording = False
        self._status_cb = None
        self._transcript_cb = None
        self._audio_queue = queue.Queue()
        self._stop_event = threading.Event()
        self._worker_thread = None

    # -- Callback wiring (called from GUI) --

    def connect_status(self, callback):
        self._status_cb = callback

    def connect_transcript(self, callback):
        self._transcript_cb = callback

    def _emit_status(self, text):
        if self._status_cb:
            self._status_cb(text)

    def _emit_transcript(self, result):
        if self._transcript_cb:
            self._transcript_cb(result)

    # -- Settings --

    def set_model(self, model_name):
        self._model_name = model_name
        # Model will be loaded on next recording start
        self._model = None

    def set_offline(self, offline):
        self._offline = offline

    # -- Model loading --

    def _load_model(self):
        self._emit_status("Loading model...")
        file_name = MODEL_FILES.get(self._model_name, "tiny.en.pt")
        local_path = os.path.join(MODELS_DIR, file_name)

        try:
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"

            if os.path.exists(local_path):
                self._model = whisper.load_model(local_path).to(device)
            elif not self._offline:
                # Let whisper download the model
                model_size = self._model_name.replace(".en", "")
                self._model = whisper.load_model(
                    model_size, download_root=MODELS_DIR
                ).to(device)
            else:
                self._emit_status("Model not available offline")
                return False
        except Exception as exc:
            self._emit_status(f"Model load failed: {exc}")
            return False

        self._emit_status("Model loaded")
        return True

    # -- Recording control --

    def start_recording(self):
        if self._recording:
            return
        self._recording = True
        self._stop_event.clear()
        self._audio_queue = queue.Queue()
        self._worker_thread = threading.Thread(
            target=self._worker_loop, daemon=True
        )
        self._worker_thread.start()

    def stop_recording(self):
        if not self._recording:
            return
        self._recording = False
        self._stop_event.set()
        self._emit_status("Ready")

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
        except Exception as exc:
            self._emit_status(f"Audio error: {exc}")
            audio.terminate()
            self._recording = False
            return

        window = []
        transcribe_interval = 0.5  # seconds between transcriptions
        chunks_per_interval = int(16000 * transcribe_interval / 1024)
        chunk_count = 0
        prev_text = ""
        stable_cycles = 0

        try:
            while not self._stop_event.is_set():
                try:
                    data = stream.read(1024, exception_on_overflow=False)
                except Exception:
                    continue

                window.append(data)
                chunk_count += 1

                if chunk_count >= chunks_per_interval and window:
                    chunk_count = 0
                    self._emit_status("Transcribing...")

                    # Transcribe accumulated audio
                    audio_data = b"".join(window)
                    arr = (
                        np.frombuffer(audio_data, np.int16)
                        .flatten()
                        .astype(np.float32)
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
                    except Exception:
                        text = ""

                    if text:
                        if text == prev_text:
                            stable_cycles += 1
                        else:
                            stable_cycles = 0
                            prev_text = text

                        if stable_cycles >= 2:
                            # Segment finalized
                            self._emit_transcript(
                                {"is_partial": False, "data": {"text": text}}
                            )
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
