"""CSS styling for WhisperFlow — clean Adwaita/Handy aesthetic"""

import gi

gi.require_version("Gtk", "4.0")

from gi.repository import Gtk, Gdk  # noqa: E402

CSS = """
/* -- Transcript area -- */
.transcript-frame {
    border-radius: 12px;
    border: 1px solid alpha(@borders, 0.5);
    background: @view_bg_color;
}

.transcript-text {
    font-family: "Cantarell", "Inter", sans-serif;
    font-size: 15px;
    line-height: 1.6;
    background: transparent;
}

/* -- Record button -- */
.record-button {
    min-width: 64px;
    min-height: 64px;
    border-radius: 50%;
    transition: all 200ms ease;
}

.record-button:hover {
    transform: scale(1.05);
}

/* -- Status indicators -- */
.status-icon {
    transition: color 300ms ease;
}

.status-idle {
    color: @dim_label_color;
}

.status-recording {
    color: #e01b24;
}

.status-processing {
    color: #f5c211;
}

.status-label {
    font-size: 13px;
    font-weight: 500;
    color: @dim_label_color;
}

/* -- Settings: hotkey badge -- */
.hotkey-badge {
    background: alpha(@accent_bg_color, 0.15);
    color: @accent_color;
    border-radius: 6px;
    padding: 4px 12px;
    font-family: monospace;
    font-size: 13px;
    font-weight: 600;
    margin-end: 8px;
}

/* -- Hotkey capture dialog -- */
.hotkey-capture-display {
    font-family: monospace;
    font-size: 28px;
    font-weight: 700;
    color: @accent_color;
    padding: 16px;
}

/* -- Navigation sidebar -- */
.navigation-sidebar {
    background: transparent;
}

.navigation-sidebar row {
    border-radius: 8px;
    margin: 2px 8px;
}
"""


def load_css():
    provider = Gtk.CssProvider()
    provider.load_from_string(CSS)
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
