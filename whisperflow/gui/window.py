"""Main application window with navigation split view"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, GLib, Pango  # noqa: E402

from whisperflow.gui.recording import RecordingView
from whisperflow.gui.settings import SettingsView
from whisperflow.gui.transcription_engine import TranscriptionEngine
from whisperflow.gui.global_hotkey import GlobalHotkey


class WhisperFlowWindow(Adw.ApplicationWindow):
    """Main window with sidebar navigation and content area"""

    def __init__(self, **kwargs):
        super().__init__(
            default_width=900,
            default_height=620,
            title="WhisperFlow",
            **kwargs,
        )

        self.engine = TranscriptionEngine()
        self.engine.connect_status(self._on_status_changed)
        self.engine.connect_transcript(self._on_transcript_received)

        # Global (system-wide) hotkey listener
        self._global_hotkey = GlobalHotkey()

        self._build_ui()
        self._setup_hotkey_controller()
        self._setup_global_hotkey()

    def _build_ui(self):
        # ── Sidebar navigation (fun icons) ─────────────────────
        self.sidebar_list = Gtk.ListBox(css_classes=["navigation-sidebar"])
        self.sidebar_list.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.sidebar_list.connect("row-activated", self._on_nav_row_activated)

        row_record = self._make_nav_row(
            "audio-input-microphone-symbolic", "Record"
        )
        row_settings = self._make_nav_row(
            "applications-system-symbolic", "Settings"
        )

        self.sidebar_list.append(row_record)
        self.sidebar_list.append(row_settings)

        sidebar_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        sidebar_header = Adw.HeaderBar(
            title_widget=Gtk.Label(label="WhisperFlow"),
            show_end_title_buttons=False,
        )
        sidebar_box.append(sidebar_header)
        sidebar_box.append(self.sidebar_list)

        # ── Content stack ──────────────────────────────────────
        self.content_stack = Gtk.Stack(
            transition_type=Gtk.StackTransitionType.CROSSFADE,
            transition_duration=200,
        )

        self.recording_view = RecordingView(engine=self.engine)
        self.settings_view = SettingsView(engine=self.engine)

        self.content_stack.add_named(self.recording_view, "record")
        self.content_stack.add_named(self.settings_view, "settings")

        content_header = Adw.HeaderBar(
            title_widget=Gtk.Label(label=""),
        )
        self.content_title = content_header.get_title_widget()

        content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        content_box.append(content_header)
        content_box.append(self.content_stack)

        # ── Split view (Handy-style) ──────────────────────────
        self.split_view = Adw.NavigationSplitView()

        sidebar_page = Adw.NavigationPage(
            title="WhisperFlow",
            child=sidebar_box,
        )
        content_page = Adw.NavigationPage(
            title="Record",
            child=content_box,
        )

        self.split_view.set_sidebar(sidebar_page)
        self.split_view.set_content(content_page)

        self.set_content(self.split_view)

        # Select first row by default
        self.sidebar_list.select_row(row_record)
        self._navigate_to("record", "Record")

    def _make_nav_row(self, icon_name, label_text):
        box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            margin_top=8,
            margin_bottom=8,
            margin_start=12,
            margin_end=12,
        )
        icon = Gtk.Image(icon_name=icon_name)
        label = Gtk.Label(label=label_text, xalign=0, hexpand=True)
        box.append(icon)
        box.append(label)

        row = Gtk.ListBoxRow(child=box)
        row.nav_name = label_text.lower()
        row.nav_title = label_text
        return row

    def _on_nav_row_activated(self, _listbox, row):
        self._navigate_to(row.nav_name, row.nav_title)

    def _navigate_to(self, name, title):
        self.content_stack.set_visible_child_name(name)
        self.content_title.set_label(title)

    # ── In-app hotkey (when window has focus) ──────────────────

    def _setup_hotkey_controller(self):
        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_pressed)
        self.add_controller(controller)

    def _on_key_pressed(self, _controller, keyval, _keycode, state):
        hotkey = self.settings_view.get_hotkey_keyval()
        if hotkey and keyval == hotkey:
            self.recording_view.toggle_recording()
            return True
        return False

    # ── Global hotkey (system-wide, works when unfocused) ──────

    def _setup_global_hotkey(self):
        key_name = self.settings_view.get_hotkey_name()
        self._global_hotkey.set_hotkey(
            key_name, self._on_global_hotkey_pressed
        )

    def _on_global_hotkey_pressed(self):
        """Called from the pynput listener thread — bounce to GTK thread."""
        GLib.idle_add(self.recording_view.toggle_recording)

    # ── Engine callbacks ───────────────────────────────────────

    def _on_status_changed(self, status):
        GLib.idle_add(self.recording_view.set_status, status)

    def _on_transcript_received(self, result):
        GLib.idle_add(self.recording_view.append_transcript, result)
