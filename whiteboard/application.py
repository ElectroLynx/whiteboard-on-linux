"""Adw.Application entry point and global CSS styling."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

from .window import Window

APP_ID = "org.victor.Whiteboard"

_CSS = """
.wb-sidebar {
  background-color: alpha(@window_fg_color, 0.03);
}

.wb-text-entry {
  font-size: 16px;
  background-color: alpha(@window_bg_color, 0.92);
  border: 1px solid alpha(@accent_bg_color, 0.9);
  border-radius: 6px;
  padding: 2px 6px;
  box-shadow: 0 2px 10px alpha(black, 0.25);
}
"""


class WhiteboardApplication(Adw.Application):
    def __init__(self):
        super().__init__(
            application_id=APP_ID,
            flags=Gio.ApplicationFlags.DEFAULT_FLAGS,
        )
        self.window = None
        self.connect("activate", self._on_activate)
        self.connect("startup", self._on_startup)

    def _on_startup(self, app):
        Adw.Application.do_startup(self)
        self._load_css()
        self._install_app_actions()

    def _load_css(self):
        provider = Gtk.CssProvider()
        provider.load_from_string(_CSS)
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _install_app_actions(self):
        quit_action = Gio.SimpleAction.new("quit", None)
        quit_action.connect("activate", lambda *_: self.quit())
        self.add_action(quit_action)
        self.set_accels_for_action("app.quit", ["<Primary>q"])

    def _on_activate(self, app):
        if self.window is None:
            self.window = Window(self)
        self.window.present()
