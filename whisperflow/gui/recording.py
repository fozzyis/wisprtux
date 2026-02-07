"""Recording view — main transcription surface"""

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Pango, GLib  # noqa: E402


class RecordingView(Gtk.Box):
    """Recording surface with transcript display and record button"""

    def __init__(self, engine, **kwargs):
        super().__init__(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            **kwargs,
        )
        self.engine = engine
        self._is_recording = False
        self._build_ui()

    def _build_ui(self):
        # -- Main clamp for centered content --
        clamp = Adw.Clamp(
            maximum_size=720,
            margin_top=24,
            margin_bottom=24,
            margin_start=24,
            margin_end=24,
            vexpand=True,
        )

        main_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            vexpand=True,
        )

        # -- Status indicator --
        self.status_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            margin_bottom=8,
        )
        self.status_icon = Gtk.Image(
            icon_name="media-record-symbolic",
            css_classes=["status-icon", "status-idle"],
        )
        self.status_label = Gtk.Label(
            label="Ready",
            css_classes=["status-label"],
        )
        self.status_box.append(self.status_icon)
        self.status_box.append(self.status_label)

        # -- Transcript area --
        transcript_frame = Gtk.Frame(
            css_classes=["transcript-frame"],
            vexpand=True,
        )
        scroll = Gtk.ScrolledWindow(
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            vscrollbar_policy=Gtk.PolicyType.AUTOMATIC,
            vexpand=True,
            min_content_height=300,
        )
        self.text_view = Gtk.TextView(
            editable=False,
            cursor_visible=False,
            wrap_mode=Gtk.WrapMode.WORD_CHAR,
            top_margin=16,
            bottom_margin=16,
            left_margin=16,
            right_margin=16,
            css_classes=["transcript-text"],
        )
        self.text_buffer = self.text_view.get_buffer()

        # Create tags for styling partial vs final text
        self.tag_partial = self.text_buffer.create_tag(
            "partial",
            foreground="#888888",
            style=Pango.Style.ITALIC,
        )
        self.tag_final = self.text_buffer.create_tag(
            "final",
            weight=Pango.Weight.NORMAL,
        )

        # Placeholder
        self.text_buffer.set_text(
            "Press the record button or your hotkey to begin transcription..."
        )
        start = self.text_buffer.get_start_iter()
        end = self.text_buffer.get_end_iter()
        self.text_buffer.apply_tag(self.tag_partial, start, end)
        self._has_placeholder = True

        scroll.set_child(self.text_view)
        transcript_frame.set_child(scroll)
        self._scroll = scroll

        # -- Bottom controls --
        controls_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            margin_top=8,
        )

        self.record_button = Gtk.Button(
            css_classes=["record-button", "circular", "suggested-action"],
            tooltip_text="Start recording",
            width_request=64,
            height_request=64,
        )
        record_icon = Gtk.Image(
            icon_name="media-record-symbolic",
            pixel_size=28,
        )
        self.record_button.set_child(record_icon)
        self.record_button.connect("clicked", self._on_record_clicked)

        self.clear_button = Gtk.Button(
            icon_name="edit-clear-all-symbolic",
            tooltip_text="Clear transcript",
            css_classes=["flat"],
        )
        self.clear_button.connect("clicked", self._on_clear_clicked)

        controls_box.append(self.clear_button)
        controls_box.append(self.record_button)

        # -- Assemble --
        main_box.append(self.status_box)
        main_box.append(transcript_frame)
        main_box.append(controls_box)

        clamp.set_child(main_box)
        self.append(clamp)

    def toggle_recording(self):
        self._on_record_clicked(None)

    def _on_record_clicked(self, _button):
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if self._has_placeholder:
            self.text_buffer.set_text("")
            self._has_placeholder = False
        self._is_recording = True
        self._update_record_button()
        self.engine.start_recording()

    def _stop_recording(self):
        self._is_recording = False
        self._update_record_button()
        self.engine.stop_recording()

    def _update_record_button(self):
        icon = self.record_button.get_child()
        if self._is_recording:
            icon.set_from_icon_name("media-playback-stop-symbolic")
            self.record_button.remove_css_class("suggested-action")
            self.record_button.add_css_class("destructive-action")
            self.record_button.set_tooltip_text("Stop recording")
        else:
            icon.set_from_icon_name("media-record-symbolic")
            self.record_button.remove_css_class("destructive-action")
            self.record_button.add_css_class("suggested-action")
            self.record_button.set_tooltip_text("Start recording")

    def set_status(self, status):
        self.status_label.set_label(status)
        self.status_icon.remove_css_class("status-idle")
        self.status_icon.remove_css_class("status-recording")
        self.status_icon.remove_css_class("status-processing")
        if "recording" in status.lower():
            self.status_icon.add_css_class("status-recording")
        elif "processing" in status.lower() or "transcribing" in status.lower():
            self.status_icon.add_css_class("status-processing")
        else:
            self.status_icon.add_css_class("status-idle")

    def append_transcript(self, result):
        if self._has_placeholder:
            self.text_buffer.set_text("")
            self._has_placeholder = False

        is_partial = result.get("is_partial", False)
        text = result.get("data", {}).get("text", "").strip()

        if not text:
            return

        # Remove previous partial line if present
        if hasattr(self, "_partial_mark") and self._partial_mark is not None:
            partial_iter = self.text_buffer.get_iter_at_mark(self._partial_mark)
            end_iter = self.text_buffer.get_end_iter()
            self.text_buffer.delete(partial_iter, end_iter)
        else:
            self._partial_mark = None

        end_iter = self.text_buffer.get_end_iter()

        if is_partial:
            # Mark where partial text starts
            self._partial_mark = self.text_buffer.create_mark(
                "partial_start", end_iter, True
            )
            self.text_buffer.insert(end_iter, text)
            # Apply partial styling
            mark_iter = self.text_buffer.get_iter_at_mark(self._partial_mark)
            end_iter = self.text_buffer.get_end_iter()
            self.text_buffer.apply_tag(self.tag_partial, mark_iter, end_iter)
        else:
            # Final text — remove partial mark
            if self._partial_mark is not None:
                self.text_buffer.delete_mark(self._partial_mark)
                self._partial_mark = None
            self.text_buffer.insert(end_iter, text + "\n")
            # Apply final styling to the line we just added
            line_start = self.text_buffer.get_end_iter()
            line_start.backward_chars(len(text) + 1)
            end_iter = self.text_buffer.get_end_iter()
            self.text_buffer.apply_tag(self.tag_final, line_start, end_iter)

        # Auto-scroll to bottom
        end_iter = self.text_buffer.get_end_iter()
        self.text_view.scroll_to_iter(end_iter, 0.0, False, 0.0, 1.0)

    def _on_clear_clicked(self, _button):
        self.text_buffer.set_text("")
        self._has_placeholder = False
        if hasattr(self, "_partial_mark") and self._partial_mark is not None:
            self.text_buffer.delete_mark(self._partial_mark)
            self._partial_mark = None
