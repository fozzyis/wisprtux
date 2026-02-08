"""System-wide global hotkey listener using pynput.

Runs a background keyboard listener that fires a callback when
the configured hotkey is pressed, regardless of which application
has focus.
"""

import logging
import threading

log = logging.getLogger(__name__)

try:
    from pynput import keyboard

    PYNPUT_AVAILABLE = True
except ImportError:
    PYNPUT_AVAILABLE = False
    log.warning("pynput not installed — global hotkey disabled")


# Map common GDK key names to pynput Key attrs
_SPECIAL_KEYS = {
    "F1": "f1",
    "F2": "f2",
    "F3": "f3",
    "F4": "f4",
    "F5": "f5",
    "F6": "f6",
    "F7": "f7",
    "F8": "f8",
    "F9": "f9",
    "F10": "f10",
    "F11": "f11",
    "F12": "f12",
    "Escape": "esc",
    "Return": "enter",
    "space": "space",
    "Tab": "tab",
    "BackSpace": "backspace",
    "Delete": "delete",
    "Home": "home",
    "End": "end",
    "Page_Up": "page_up",
    "Page_Down": "page_down",
    "Insert": "insert",
    "Pause": "pause",
    "Scroll_Lock": "scroll_lock",
    "Print": "print_screen",
    "Caps_Lock": "caps_lock",
    "Num_Lock": "num_lock",
}


def _gdk_name_to_pynput(key_name):
    """Convert a GDK key name (e.g. 'F9', 'a') to a pynput key object."""
    if not PYNPUT_AVAILABLE:
        return None

    # Check special keys first
    if key_name in _SPECIAL_KEYS:
        attr = _SPECIAL_KEYS[key_name]
        return getattr(keyboard.Key, attr, None)

    # Single character keys
    if len(key_name) == 1:
        return keyboard.KeyCode.from_char(key_name.lower())

    return None


class GlobalHotkey:
    """Manages a system-wide hotkey listener."""

    def __init__(self):
        self._listener = None
        self._target_key = None
        self._callback = None
        self._lock = threading.Lock()

    @property
    def available(self):
        """Return True if pynput is available"""
        return PYNPUT_AVAILABLE

    def set_hotkey(self, gdk_key_name, callback):
        """Configure the hotkey. Restarts the listener if already running."""
        with self._lock:
            self._target_key = _gdk_name_to_pynput(gdk_key_name)
            self._callback = callback
            if self._target_key is None:
                log.warning("Could not map key %r to pynput", gdk_key_name)

        # Restart listener with new key
        self.stop()
        self.start()

    def start(self):
        """Start the global listener in a daemon thread."""
        if not PYNPUT_AVAILABLE:
            return
        if self._listener is not None:
            return

        self._listener = keyboard.Listener(on_press=self._on_press)
        self._listener.daemon = True
        self._listener.start()
        log.info("Global hotkey listener started")

    def stop(self):
        """Stop the global listener."""
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
            log.info("Global hotkey listener stopped")

    def _on_press(self, key):
        with self._lock:
            target = self._target_key
            callback = self._callback

        if target is None or callback is None:
            return

        # Compare the pressed key against the target
        match = False
        if isinstance(target, keyboard.Key):
            match = key == target
        elif isinstance(target, keyboard.KeyCode):
            if isinstance(key, keyboard.KeyCode):
                match = key.char == target.char if key.char else False

        if match:
            try:
                callback()
            except Exception:  # pylint: disable=broad-exception-caught
                log.exception("Global hotkey callback error")
