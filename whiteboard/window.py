"""The main application window: header bar, sidebar, canvas, text editor."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

from .canvas import Canvas
from .document import Document
from .shapes import TextShape
from .sidebar import Sidebar
from .tools import Tool

APP_TITLE = "Whiteboard"


class Window(Adw.ApplicationWindow):
    def __init__(self, app):
        super().__init__(application=app)
        self.set_title(APP_TITLE)
        self.set_default_size(1300, 840)

        self.canvas = Canvas(self)

        self.overlay = Gtk.Overlay()
        self.overlay.set_child(self.canvas)
        self.overlay.connect("get-child-position", self._position_overlay_child)

        self._text_entry = None
        self._editing_shape = None
        self._text_anchor = (0.0, 0.0)
        self._text_entry_commit_pending = True

        self.sidebar = Sidebar(self)

        content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=0)
        content.append(self.sidebar)
        content.append(Gtk.Separator())
        content.append(self.overlay)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(self._build_header())
        toolbar_view.set_content(content)
        self.set_content(toolbar_view)

        self._install_actions()
        self.sync_undo_redo_sensitivity()
        self.sync_zoom_label()
        self._update_title()

        self.connect("close-request", self._on_close_request)

    # ------------------------------------------------------------------
    # Header bar
    # ------------------------------------------------------------------
    def _build_header(self):
        header = Adw.HeaderBar()

        new_btn = Gtk.Button(icon_name="document-new-symbolic")
        new_btn.set_tooltip_text("Nouveau tableau (Ctrl+N)")
        new_btn.connect("clicked", self._on_new)
        header.pack_start(new_btn)

        open_btn = Gtk.Button(icon_name="document-open-symbolic")
        open_btn.set_tooltip_text("Ouvrir… (Ctrl+O)")
        open_btn.connect("clicked", self._on_open)
        header.pack_start(open_btn)

        zoom_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL)
        zoom_box.add_css_class("linked")
        zoom_out = Gtk.Button(icon_name="zoom-out-symbolic")
        zoom_out.set_tooltip_text("Zoom -")
        zoom_out.connect("clicked", lambda *_: self.canvas.zoom_by(1 / 1.2))
        self.zoom_label_btn = Gtk.Button(label="100%")
        self.zoom_label_btn.set_tooltip_text("Réinitialiser le zoom (Ctrl+0)")
        self.zoom_label_btn.connect("clicked", lambda *_: self.canvas.zoom_reset())
        zoom_in = Gtk.Button(icon_name="zoom-in-symbolic")
        zoom_in.set_tooltip_text("Zoom +")
        zoom_in.connect("clicked", lambda *_: self.canvas.zoom_by(1.2))
        zoom_box.append(zoom_out)
        zoom_box.append(self.zoom_label_btn)
        zoom_box.append(zoom_in)
        header.pack_start(zoom_box)

        self.window_title = Adw.WindowTitle(title=APP_TITLE, subtitle="Sans titre")
        header.set_title_widget(self.window_title)

        menu = Gio.Menu()
        menu.append("Enregistrer", "win.save-document")
        menu.append("Enregistrer sous…", "win.save-document-as")
        menu.append("Exporter en PNG…", "win.export-png")
        menu_btn = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu_btn.set_tooltip_text("Menu")
        menu_btn.set_menu_model(menu)
        header.pack_end(menu_btn)

        self.redo_btn = Gtk.Button(icon_name="edit-redo-symbolic")
        self.redo_btn.set_tooltip_text("Rétablir (Ctrl+Maj+Z)")
        self.redo_btn.connect("clicked", self._on_redo)
        header.pack_end(self.redo_btn)

        self.undo_btn = Gtk.Button(icon_name="edit-undo-symbolic")
        self.undo_btn.set_tooltip_text("Annuler (Ctrl+Z)")
        self.undo_btn.connect("clicked", self._on_undo)
        header.pack_end(self.undo_btn)

        return header

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _install_actions(self):
        app = self.get_application()

        def add_action(name, callback, accel=None):
            action = Gio.SimpleAction.new(name, None)
            action.connect("activate", callback)
            self.add_action(action)
            if accel:
                app.set_accels_for_action(f"win.{name}", [accel])

        add_action("new-document", self._on_new, "<Primary>n")
        add_action("open-document", self._on_open, "<Primary>o")
        add_action("save-document", self._on_save, "<Primary>s")
        add_action("save-document-as", self._on_save_as, "<Primary><Shift>s")
        add_action("export-png", self._on_export_png, "<Primary>e")
        add_action("undo", self._on_undo, "<Primary>z")
        add_action("redo", self._on_redo, "<Primary><Shift>z")
        add_action("zoom-in", lambda *_: self.canvas.zoom_by(1.2), "<Primary>plus")
        add_action("zoom-out", lambda *_: self.canvas.zoom_by(1 / 1.2), "<Primary>minus")
        add_action("zoom-reset", lambda *_: self.canvas.zoom_reset(), "<Primary>0")

    # ------------------------------------------------------------------
    # Tool switching (delegates to canvas + sidebar)
    # ------------------------------------------------------------------
    def set_active_tool(self, tool: Tool):
        self.canvas.set_tool(tool)
        self.sidebar.set_active_tool_button(tool)

    # ------------------------------------------------------------------
    # Undo/redo/zoom/title sync
    # ------------------------------------------------------------------
    def sync_undo_redo_sensitivity(self):
        self.undo_btn.set_sensitive(self.canvas.doc.can_undo())
        self.redo_btn.set_sensitive(self.canvas.doc.can_redo())

    def sync_zoom_label(self):
        self.zoom_label_btn.set_label(f"{round(self.canvas.zoom * 100)}%")

    def mark_dirty(self):
        self.canvas.doc.dirty = True
        self._update_title()

    def _update_title(self):
        doc = self.canvas.doc
        if doc.file_path:
            name = GLib.path_get_basename(doc.file_path)
        else:
            name = "Sans titre"
        if doc.dirty:
            name = f"• {name}"
        self.window_title.set_subtitle(name)

    # ------------------------------------------------------------------
    # File actions
    # ------------------------------------------------------------------
    def _on_new(self, *_args):
        self.canvas.new_document()
        self._update_title()
        self.sync_undo_redo_sensitivity()

    def _on_open(self, *_args):
        dialog = Gtk.FileDialog()
        wb_filter = Gtk.FileFilter()
        wb_filter.set_name("Tableaux blancs (*.json)")
        wb_filter.add_pattern("*.json")
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(wb_filter)
        dialog.set_filters(filters)
        dialog.open(self, None, self._on_open_finish)

    def _on_open_finish(self, dialog, result, *_args):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        try:
            doc = Document.load(path)
        except Exception as exc:  # noqa: BLE001 - surface any load error to the user
            self._show_error(f"Impossible d'ouvrir « {path} » : {exc}")
            return
        self.canvas.set_document(doc)
        self._update_title()
        self.sync_undo_redo_sensitivity()

    def _on_save(self, *_args):
        doc = self.canvas.doc
        if doc.file_path:
            doc.save(doc.file_path)
            self._update_title()
        else:
            self._on_save_as()

    def _on_save_as(self, *_args):
        dialog = Gtk.FileDialog()
        dialog.set_initial_name("tableau-blanc.json")
        dialog.save(self, None, self._on_save_finish)

    def _on_save_finish(self, dialog, result, *_args):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        if not path.lower().endswith(".json"):
            path += ".json"
        try:
            self.canvas.doc.save(path)
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"Impossible d'enregistrer : {exc}")
            return
        self._update_title()

    def _on_export_png(self, *_args):
        dialog = Gtk.FileDialog()
        dialog.set_initial_name("tableau-blanc.png")
        dialog.save(self, None, self._on_export_finish)

    def _on_export_finish(self, dialog, result, *_args):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            self.canvas.render_to_png(path)
        except Exception as exc:  # noqa: BLE001
            self._show_error(f"Export impossible : {exc}")

    def _on_undo(self, *_args):
        if self.canvas.doc.undo():
            self.canvas.queue_draw()
            self.sync_undo_redo_sensitivity()
            self.mark_dirty()

    def _on_redo(self, *_args):
        if self.canvas.doc.redo():
            self.canvas.queue_draw()
            self.sync_undo_redo_sensitivity()
            self.mark_dirty()

    def _on_close_request(self, *_args):
        return False

    def _show_error(self, message):
        dialog = Adw.AlertDialog(heading="Erreur", body=message)
        dialog.add_response("ok", "OK")
        dialog.present(self)

    # ------------------------------------------------------------------
    # Text tool: floating entry overlay
    # ------------------------------------------------------------------
    def start_text_edit(self, doc_x, doc_y):
        self._finish_text_edit(commit=True)
        self._editing_shape = None
        self._text_anchor = (doc_x, doc_y)
        self._show_text_entry("")

    def edit_text_shape(self, shape: TextShape):
        self._finish_text_edit(commit=True)
        self._editing_shape = shape
        shape.hidden = True
        self._text_anchor = (shape.x, shape.y)
        self._show_text_entry(shape.text)
        self.canvas.queue_draw()

    def _show_text_entry(self, initial_text):
        entry = Gtk.Text()
        entry.set_text(initial_text)
        entry.add_css_class("wb-text-entry")
        self._text_entry_commit_pending = True

        # Enter/Escape never remove the widget directly: doing so from
        # within one of the entry's own signal handlers ("activate", a
        # key press) crashes GTK, which is still unwinding that signal
        # emission and touches the widget afterwards. Instead they just
        # move focus away (a perfectly ordinary operation); the resulting
        # focus "leave" is the single, real trigger that performs the
        # actual (idle-deferred) removal exactly once.
        entry.connect("activate", lambda *_: self._request_close_text_entry(True))

        focus_ctrl = Gtk.EventControllerFocus.new()
        focus_ctrl.connect("leave", lambda *_: GLib.idle_add(
            self._finish_text_edit, self._text_entry_commit_pending
        ))
        entry.add_controller(focus_ctrl)

        key_ctrl = Gtk.EventControllerKey.new()
        key_ctrl.connect("key-pressed", self._on_text_entry_key)
        entry.add_controller(key_ctrl)

        self._text_entry = entry
        self.overlay.add_overlay(entry)
        entry.grab_focus()
        entry.set_position(-1)

    def _request_close_text_entry(self, commit):
        self._text_entry_commit_pending = commit
        self.canvas.grab_focus()

    def _on_text_entry_key(self, controller, keyval, keycode, state):
        if Gdk.keyval_name(keyval) == "Escape":
            self._request_close_text_entry(False)
            return True
        return False

    def _finish_text_edit(self, commit):
        entry = self._text_entry
        if entry is None:
            return GLib.SOURCE_REMOVE
        # Clear the reference *before* touching the widget tree: removing
        # the overlay child triggers a focus "leave" on the entry, which
        # would otherwise re-enter this method with the same (already
        # being removed) widget.
        self._text_entry = None
        text = entry.get_text().strip()
        self.overlay.remove_overlay(entry)
        doc = self.canvas.doc

        if self._editing_shape is not None:
            shape = self._editing_shape
            shape.hidden = False
            self._editing_shape = None
            if commit:
                if text:
                    doc.push_undo()
                    shape.text = text
                else:
                    doc.push_undo()
                    doc.shapes = [s for s in doc.shapes if s.id != shape.id]
                    if doc.selected_id == shape.id:
                        doc.selected_id = None
        elif commit and text:
            shape = TextShape(
                self._text_anchor[0],
                self._text_anchor[1],
                text=text,
                font_size=self.canvas.tool_ctx.font_size,
                color=self.canvas.tool_ctx.stroke_color,
            )
            doc.add_shape(shape)

        self.sync_undo_redo_sensitivity()
        self.mark_dirty()
        self.canvas.grab_focus()
        self.canvas.queue_draw()
        return GLib.SOURCE_REMOVE

    def _position_overlay_child(self, overlay, widget, rect):
        if widget is not self._text_entry:
            return False
        x, y = self.canvas.doc_to_screen(*self._text_anchor)
        zoom = self.canvas.zoom
        if self._editing_shape is not None:
            font_size = self._editing_shape.font_size
        else:
            font_size = self.canvas.tool_ctx.font_size
        rect.x = int(x)
        rect.y = int(y)
        rect.width = max(140, int(240 * zoom))
        rect.height = max(30, int(font_size * 1.5 * zoom))
        return True
