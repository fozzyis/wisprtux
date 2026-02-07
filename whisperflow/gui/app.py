"""WhisperFlow GTK4/Adwaita application entry point"""

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio, GLib  # noqa: E402

from whisperflow.gui.window import WhisperFlowWindow
from whisperflow.gui.style import load_css


class WhisperFlowApp(Adw.Application):
    """Main application class"""

    def __init__(self):
        super().__init__(
            application_id="io.github.whisperflow",
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window = None

    def do_activate(self):
        load_css()
        if not self.window:
            self.window = WhisperFlowWindow(application=self)
        self.window.present()

    def do_startup(self):
        Adw.Application.do_startup(self)
        self._setup_actions()

    def _setup_actions(self):
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Ctrl>q"])

        about_action = Gio.SimpleAction.new("about", None)
        about_action.connect("activate", self._on_about)
        self.add_action(about_action)

    def _on_about(self, *_args):
        about = Adw.AboutDialog(
            application_name="WhisperFlow",
            application_icon="audio-input-microphone-symbolic",
            developer_name="Dima Statz",
            version="1.0.0",
            comments="Real-time transcription using OpenAI Whisper",
            website="https://github.com/dimastatz/whisper-flow",
            license_type=Gtk.License.MIT_X11,
        )
        about.present(self.window)


def main():
    app = WhisperFlowApp()
    return app.run(sys.argv)
