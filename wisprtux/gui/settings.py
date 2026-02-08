"""Settings view — theme, hotkey, model selection, clipboard, offline mode"""
# pylint: disable=import-error, wrong-import-position, too-many-instance-attributes, too-many-locals, too-many-statements, too-few-public-methods

import json
import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gdk, GLib  # noqa: E402


CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "wisprtux")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

AVAILABLE_MODELS = [
    ("tiny.en", "Tiny (English)", "Fastest, least accurate (~72 MB)"),
    ("base.en", "Base (English)", "Good balance of speed and accuracy (~142 MB)"),
    ("small.en", "Small (English)", "Better accuracy, slower (~466 MB)"),
    ("medium.en", "Medium (English)", "High accuracy (~1.5 GB)"),
    ("large", "Large (Multilingual)", "Best accuracy, slowest (~2.9 GB)"),
]

THEME_OPTIONS = [
    ("system", "System Default"),
    ("light", "Light"),
    ("dark", "Dark"),
]

DEFAULT_SETTINGS = {
    "hotkey": "F9",
    "model": "tiny.en",
    "offline_mode": False,
    "theme": "system",
    "auto_clipboard": False,
    "auto_type": False,
}


class SettingsView(Gtk.Box):
    """Settings panel with all user-facing preferences"""

    # pylint: disable=duplicate-code
    def __init__(self, engine, **kwargs):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            **kwargs,
        )
        self.engine = engine
        self.settings = self._load_settings()
        self._build_ui()
        self._apply_settings()

    def _build_ui(self):
        clamp = Adw.Clamp(
            maximum_size=600,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )

        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=24,
        )

        # ── Appearance ──────────────────────────────────────────
        appearance_group = Adw.PreferencesGroup(
            title="Appearance",
            description="Choose your colour scheme",
        )

        self.theme_combo = Adw.ComboRow(
            title="Theme",
            subtitle="Controls the light/dark appearance",
        )
        theme_model = Gtk.StringList()
        for _theme_id, theme_label in THEME_OPTIONS:
            theme_model.append(theme_label)
        self.theme_combo.set_model(theme_model)

        # Set current selection
        current_theme = self.settings.get("theme", "system")
        for idx, (tid, _) in enumerate(THEME_OPTIONS):
            if tid == current_theme:
                self.theme_combo.set_selected(idx)
                break
        self.theme_combo.connect("notify::selected", self._on_theme_changed)
        appearance_group.add(self.theme_combo)

        # ── Recording ──────────────────────────────────────────
        recording_group = Adw.PreferencesGroup(
            title="Recording",
            description="Configure how recording is triggered",
        )

        self.hotkey_row = Adw.ActionRow(
            title="Record Hotkey",
            subtitle="System-wide shortcut to start/stop recording",
        )
        self.hotkey_label = Gtk.Label(
            label=self.settings["hotkey"],
            css_classes=["hotkey-badge"],
            valign=Gtk.Align.CENTER,
        )
        hotkey_button = Gtk.Button(
            label="Change",
            valign=Gtk.Align.CENTER,
            css_classes=["flat"],
        )
        hotkey_button.connect("clicked", self._on_change_hotkey)
        self.hotkey_row.add_suffix(self.hotkey_label)
        self.hotkey_row.add_suffix(hotkey_button)
        recording_group.add(self.hotkey_row)

        # ── Output ─────────────────────────────────────────────
        output_group = Adw.PreferencesGroup(
            title="Output",
            description="What happens with transcribed text",
        )

        self.clipboard_row = Adw.SwitchRow(
            title="Copy to Clipboard",
            subtitle="Automatically copy each final segment to the clipboard",
        )
        self.clipboard_row.set_active(self.settings.get("auto_clipboard", False))
        self.clipboard_row.connect("notify::active", self._on_clipboard_toggled)
        output_group.add(self.clipboard_row)

        self.auto_type_row = Adw.SwitchRow(
            title="Type into Active Window",
            subtitle=(
                "Automatically type transcribed text into the application "
                "that was focused when recording started"
            ),
        )
        self.auto_type_row.set_active(self.settings.get("auto_type", False))
        self.auto_type_row.connect("notify::active", self._on_auto_type_toggled)
        output_group.add(self.auto_type_row)

        # ── Model ──────────────────────────────────────────────
        model_group = Adw.PreferencesGroup(
            title="Model",
            description="Select the Whisper model for transcription",
        )

        self.model_rows = {}
        for model_id, model_name, model_desc in AVAILABLE_MODELS:
            row = Adw.ActionRow(
                title=model_name,
                subtitle=model_desc,
            )
            check = Gtk.CheckButton(
                valign=Gtk.Align.CENTER,
                css_classes=["selection-mode"],
            )
            if model_id == self.settings["model"]:
                check.set_active(True)
            if self.model_rows:
                first_check = list(self.model_rows.values())[0]
                check.set_group(first_check)
            check.connect("toggled", self._on_model_toggled, model_id)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            model_group.add(row)
            self.model_rows[model_id] = check

        # ── Network ────────────────────────────────────────────
        network_group = Adw.PreferencesGroup(
            title="Network",
            description="Control network behaviour",
        )

        self.offline_row = Adw.SwitchRow(
            title="Offline Mode",
            subtitle="Use only locally cached models — no downloads",
        )
        self.offline_row.set_active(self.settings.get("offline_mode", False))
        self.offline_row.connect("notify::active", self._on_offline_toggled)
        network_group.add(self.offline_row)

        # ── Assemble ───────────────────────────────────────────
        main_box.append(appearance_group)
        main_box.append(recording_group)
        main_box.append(output_group)
        main_box.append(model_group)
        main_box.append(network_group)

        clamp.set_child(main_box)

        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
        )
        scroll.set_child(clamp)
        self.append(scroll)

    # ── Theme ──────────────────────────────────────────────────

    def _on_theme_changed(self, combo, _pspec):
        idx = combo.get_selected()
        if 0 <= idx < len(THEME_OPTIONS):
            theme_id = THEME_OPTIONS[idx][0]
            self.settings["theme"] = theme_id
            self._save_settings()
            apply_theme(theme_id)

    def _on_change_hotkey(self, _button):
        """Open the hotkey capture dialog"""
        dialog = HotkeyDialog(on_apply=self._on_hotkey_apply)
        dialog.present(self.get_root())

    def _on_hotkey_apply(self, key_name):
        self.settings["hotkey"] = key_name
        self.hotkey_label.set_label(key_name)
        self._save_settings()
        self.engine.set_hotkey(key_name)

    # ── Output toggles ─────────────────────────────────────────

    def _on_clipboard_toggled(self, row, _pspec):
        self.settings["auto_clipboard"] = row.get_active()
        self._save_settings()
        self.engine.set_auto_clipboard(row.get_active())

    def _on_auto_type_toggled(self, row, _pspec):
        self.settings["auto_type"] = row.get_active()
        self._save_settings()
        self.engine.set_auto_type(row.get_active())

    # ── Model / Offline ────────────────────────────────────────

    def _on_model_toggled(self, check, model_id):
        if check.get_active():
            self.settings["model"] = model_id
            self._save_settings()
            self.engine.set_model(model_id)

    def _on_offline_toggled(self, row, _pspec):
        self.settings["offline_mode"] = row.get_active()
        self._save_settings()
        self.engine.set_offline(row.get_active())

    # ── Accessors ──────────────────────────────────────────────

    def get_hotkey_keyval(self):
        """Return the Gdk keyval for the current hotkey"""
        key_name = self.settings.get("hotkey", "F9")
        keyval = Gdk.keyval_from_name(key_name)
        if keyval == Gdk.KEY_VoidSymbol:
            return None
        return keyval

    def get_hotkey_name(self):
        """Return the human-readable string name of the hotkey"""
        return self.settings.get("hotkey", "F9")

    # ── Apply / Load / Save ────────────────────────────────────

    def _apply_settings(self):
        self.engine.set_model(self.settings["model"])
        self.engine.set_offline(self.settings["offline_mode"])
        self.engine.set_auto_clipboard(self.settings.get("auto_clipboard", False))
        self.engine.set_auto_type(self.settings.get("auto_type", False))
        apply_theme(self.settings.get("theme", "system"))

    def _load_settings(self):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                saved = json.load(f)
                merged = dict(DEFAULT_SETTINGS)
                merged.update(saved)
                return merged
        except (FileNotFoundError, json.JSONDecodeError):
            return dict(DEFAULT_SETTINGS)

    def _save_settings(self):
        """Persist settings to disk in JSON format"""
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.settings, f, indent=2)


# ── Theme helper ───────────────────────────────────────────────

_SCHEME_MAP = {
    "system": Adw.ColorScheme.DEFAULT,
    "light": Adw.ColorScheme.FORCE_LIGHT,
    "dark": Adw.ColorScheme.FORCE_DARK,
}


def apply_theme(theme_id):
    """Apply the selected color scheme to the application"""
    scheme = _SCHEME_MAP.get(theme_id, Adw.ColorScheme.DEFAULT)
    Adw.StyleManager.get_default().set_color_scheme(scheme)


# ── Hotkey capture dialog ──────────────────────────────────────


class HotkeyDialog(Adw.Dialog):
    """Dialog for capturing a hotkey press"""

    def __init__(self, on_apply=None, **kwargs):
        super().__init__(**kwargs)
        self.captured_key = None
        self._on_apply = on_apply
        self.set_title("Set Hotkey")
        self.set_content_width(360)
        self.set_content_height(220)

        toolbar = Adw.ToolbarView()
        header = Adw.HeaderBar(show_end_title_buttons=True)
        toolbar.add_top_bar(header)

        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
        )

        self.prompt_label = Gtk.Label(
            label="Press a key to use as the recording hotkey...",
            css_classes=["title-3"],
            wrap=True,
        )
        self.key_display = Gtk.Label(
            label="Waiting...",
            css_classes=["hotkey-capture-display"],
        )

        button_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.END,
            margin_top=8,
        )
        cancel_btn = Gtk.Button(label="Cancel", css_classes=["flat"])
        cancel_btn.connect("clicked", self._on_cancel)
        self.apply_btn = Gtk.Button(
            label="Apply",
            css_classes=["suggested-action"],
            sensitive=False,
        )
        self.apply_btn.connect("clicked", self._on_apply_clicked)

        button_box.append(cancel_btn)
        button_box.append(self.apply_btn)

        box.append(self.prompt_label)
        box.append(self.key_display)
        box.append(button_box)

        toolbar.set_content(box)
        self.set_child(toolbar)

        controller = Gtk.EventControllerKey()
        controller.connect("key-pressed", self._on_key_pressed)
        toolbar.add_controller(controller)

    def _on_key_pressed(self, _ctrl, keyval, _keycode, _state):
        name = Gdk.keyval_name(keyval)
        if name:
            self.captured_key = name
            self.key_display.set_label(name)
            self.apply_btn.set_sensitive(True)
        return True

    def _on_cancel(self, *_args):
        self.close()

    def _on_apply_clicked(self, *_args):
        if self._on_apply and self.captured_key:
            self._on_apply(self.captured_key)
        self.close()
