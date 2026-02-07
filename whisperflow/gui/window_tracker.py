"""Active window tracking and text injection using xdotool.

Captures the currently active window (ID + title) so that when
transcription completes, we can:
  1. Restore focus to that window
  2. Type the transcribed text into whatever input had focus
"""

import shutil
import subprocess
import logging

log = logging.getLogger(__name__)


def _run(args, timeout=5):
    """Run a subprocess and return stripped stdout, or None on failure."""
    try:
        result = subprocess.run(
            args,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError) as exc:
        log.debug("Command %s failed: %s", args, exc)
    return None


def is_available():
    """Return True if xdotool is installed."""
    return shutil.which("xdotool") is not None


def get_active_window():
    """Return the X11 window ID of the currently focused window, or None."""
    return _run(["xdotool", "getactivewindow"])


def get_window_name(window_id):
    """Return the title of a given window ID."""
    if not window_id:
        return None
    return _run(["xdotool", "getactivewindow", "getwindowname"])


def get_window_pid(window_id):
    """Return the PID of the process owning the window."""
    if not window_id:
        return None
    return _run(["xdotool", "getwindowpid", str(window_id)])


def focus_window(window_id):
    """Raise and focus a window by its X11 ID."""
    if not window_id:
        return False
    result = _run(["xdotool", "windowactivate", "--sync", str(window_id)])
    return result is not None


def type_text(text, window_id=None, delay_ms=12):
    """Type text into the currently focused window (or a specific window).

    Uses xdotool's --clearmodifiers to avoid modifier key interference.
    The delay between keystrokes prevents dropped characters in some apps.
    """
    if not text:
        return False

    args = ["xdotool"]
    if window_id:
        args += ["--window", str(window_id)]
    args += [
        "type",
        "--clearmodifiers",
        "--delay", str(delay_ms),
        "--",
        text,
    ]
    result = _run(args, timeout=max(10, len(text) * delay_ms / 1000 + 5))
    return result is not None


def set_clipboard(text):
    """Copy text to the system clipboard (tries xclip, then xsel)."""
    for cmd in [
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
    ]:
        if shutil.which(cmd[0]):
            try:
                subprocess.run(
                    cmd,
                    input=text,
                    text=True,
                    timeout=5,
                    check=True,
                )
                return True
            except (subprocess.SubprocessError, OSError):
                continue
    return False


class WindowSnapshot:
    """Captures the active window state at a point in time."""

    def __init__(self):
        self.window_id = get_active_window()
        self.window_name = get_window_name(self.window_id)
        self.window_pid = get_window_pid(self.window_id)

    @property
    def valid(self):
        return self.window_id is not None

    def restore_and_type(self, text):
        """Bring the captured window back to front and type text into it."""
        if not self.valid or not text:
            return False
        if not focus_window(self.window_id):
            return False
        return type_text(text)

    def __repr__(self):
        return (
            f"WindowSnapshot(id={self.window_id}, "
            f"name={self.window_name!r}, pid={self.window_pid})"
        )
