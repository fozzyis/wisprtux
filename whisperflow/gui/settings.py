"""Settings view — hotkey, model selection, offline mode"""

import json
import os

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gdk, GLib  # noqa: E402


CONFIG_DIR = os.path.join(GLib.get_user_config_dir(), "whisperflow")
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")

AVAILABLE_MODELS = [
    ("tiny.en", "Tiny (English)", "Fastest, least accurate (~72MB)"),
    ("base.en", "Base (English)", "Good balance of speed and accuracy (~142MB)"),
    ("small.en", "Small (English)", "Better accuracy, slower (~466MB)"),
    ("medium.en", "Medium (English)", "High accuracy (~1.5GB)"),
    ("large", "Large (Multilingual)", "Best accuracy, slowest (~2.9GB)"),
]

DEFAULT_SETTINGS = {
    "hotkey": "F9",
    "model": "tiny.en",
    "offline_mode": False,
}


class SettingsView(Gtk.Box):
    """Settings panel with hotkey, model, and offline configuration"""

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

        # -- Recording group --
        recording_group = Adw.PreferencesGroup(
            title="Recording",
            description="Configure how recording is triggered",
        )

        # Hotkey row
        self.hotkey_row = Adw.ActionRow(
            title="Record Hotkey",
            subtitle="Press to set a new hotkey",
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

        # -- Model group --
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
            # Group all radio buttons together
            if self.model_rows:
                first_check = list(self.model_rows.values())[0]
                check.set_group(first_check)
            check.connect("toggled", self._on_model_toggled, model_id)
            row.add_prefix(check)
            row.set_activatable_widget(check)
            model_group.add(row)
            self.model_rows[model_id] = check

        # -- Network group --
        network_group = Adw.PreferencesGroup(
            title="Network",
            description="Control network behaviour",
        )

        self.offline_row = Adw.SwitchRow(
            title="Offline Mode",
            subtitle="Use only locally cached models — no downloads",
        )
        self.offline_row.set_active(self.settings["offline_mode"])
        self.offline_row.connect("notify::active", self._on_offline_toggled)
        network_group.add(self.offline_row)

        # -- Assemble --
        main_box.append(recording_group)
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

    def _on_change_hotkey(self, _button):
        dialog = HotkeyDialog(on_apply=self._on_hotkey_apply)
        dialog.present(self.get_root())

    def _on_hotkey_apply(self, key_name):
        self.settings["hotkey"] = key_name
        self.hotkey_label.set_label(key_name)
        self._save_settings()

    def _on_model_toggled(self, check, model_id):
        if check.get_active():
            self.settings["model"] = model_id
            self._save_settings()
            self.engine.set_model(model_id)

    def _on_offline_toggled(self, row, _pspec):
        self.settings["offline_mode"] = row.get_active()
        self._save_settings()
        self.engine.set_offline(row.get_active())

    def get_hotkey_keyval(self):
        key_name = self.settings.get("hotkey", "F9")
        keyval = Gdk.keyval_from_name(key_name)
        if keyval == Gdk.KEY_VoidSymbol:
            return None
        return keyval

    def _apply_settings(self):
        self.engine.set_model(self.settings["model"])
        self.engine.set_offline(self.settings["offline_mode"])

    def _load_settings(self):
        try:
            with open(CONFIG_FILE, "r") as f:
                saved = json.load(f)
                merged = dict(DEFAULT_SETTINGS)
                merged.update(saved)
                return merged
        except (FileNotFoundError, json.JSONDecodeError):
            return dict(DEFAULT_SETTINGS)

    def _save_settings(self):
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w") as f:
            json.dump(self.settings, f, indent=2)


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

        # Key capture
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
