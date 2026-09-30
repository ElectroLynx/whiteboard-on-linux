"""The infinite whiteboard canvas: rendering, pan/zoom, and interaction."""
from __future__ import annotations

import math

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gtk

from .document import Document
from .tools import KEY_TO_TOOL, Tool, ToolContext, create_handler

HANDLE_SIZE = 9.0
HANDLE_HIT_RADIUS = 11.0
SHAPE_HIT_TOLERANCE = 6.0
GRID_SIZE = 40.0
MIN_ZOOM = 0.1
MAX_ZOOM = 8.0


class Canvas(Gtk.DrawingArea):
    """A Gtk.DrawingArea that renders a Document and dispatches tool
    interactions coming from pointer gestures, scroll (zoom/pan), and
    a handful of keyboard shortcuts."""

    def __init__(self, window):
        super().__init__()
        self.window = window
        self.doc = Document()
        self.tool_ctx = ToolContext()
        self.current_tool = Tool.SELECT

        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0

        self._active_handler = None
        self._select_mode = None  # None | "move" | "resize"
        self._select_handle = None
        self._last_doc_point = (0.0, 0.0)
        self._space_down = False
        self._panning = False
        self._pan_start_screen = (0.0, 0.0)
        self._pan_origin = (0.0, 0.0)
        self._last_pointer = (0.0, 0.0)

        self.set_hexpand(True)
        self.set_vexpand(True)
        self.set_focusable(True)
        self.set_can_focus(True)
        self.set_draw_func(self._on_draw)

        self._setup_gestures()

        style_mgr = Adw.StyleManager.get_default()
        style_mgr.connect("notify::dark", lambda *_: self.queue_draw())

    # ------------------------------------------------------------------
    # Coordinate transforms
    # ------------------------------------------------------------------
    def screen_to_doc(self, x, y):
        return (x - self.pan_x) / self.zoom, (y - self.pan_y) / self.zoom

    def doc_to_screen(self, x, y):
        return x * self.zoom + self.pan_x, y * self.zoom + self.pan_y

    # ------------------------------------------------------------------
    # Gesture / event wiring
    # ------------------------------------------------------------------
    def _setup_gestures(self):
        primary = Gtk.GestureDrag.new()
        primary.set_button(Gdk.BUTTON_PRIMARY)
        primary.connect("drag-begin", self._on_primary_begin)
        primary.connect("drag-update", self._on_primary_update)
        primary.connect("drag-end", self._on_primary_end)
        self.add_controller(primary)

        middle = Gtk.GestureDrag.new()
        middle.set_button(Gdk.BUTTON_MIDDLE)
        middle.connect("drag-begin", self._on_pan_begin)
        middle.connect("drag-update", self._on_pan_update)
        self.add_controller(middle)

        click = Gtk.GestureClick.new()
        click.set_button(Gdk.BUTTON_PRIMARY)
        click.connect("pressed", self._on_click_pressed)
        self.add_controller(click)

        scroll = Gtk.EventControllerScroll.new(
            Gtk.EventControllerScrollFlags.HORIZONTAL | Gtk.EventControllerScrollFlags.VERTICAL
        )
        scroll.connect("scroll", self._on_scroll)
        self.add_controller(scroll)

        motion = Gtk.EventControllerMotion.new()
        motion.connect("motion", self._on_motion)
        self.add_controller(motion)

        key = Gtk.EventControllerKey.new()
        key.connect("key-pressed", self._on_key_pressed)
        key.connect("key-released", self._on_key_released)
        self.add_controller(key)

    # ------------------------------------------------------------------
    # Tool selection
    # ------------------------------------------------------------------
    def set_tool(self, tool: Tool):
        self.current_tool = tool
        self._active_handler = None
        cursor_name = {
            Tool.SELECT: "default",
            Tool.TEXT: "text",
            Tool.ERASER: "not-allowed",
        }.get(tool, "crosshair")
        self.set_cursor(Gdk.Cursor.new_from_name(cursor_name))
        self.queue_draw()

    # ------------------------------------------------------------------
    # Primary button: draw / select / place text
    # ------------------------------------------------------------------
    def _on_primary_begin(self, gesture, x, y):
        self.grab_focus()
        if self._space_down:
            self._start_pan(x, y)
            return
        doc_x, doc_y = self.screen_to_doc(x, y)
        if self.current_tool == Tool.SELECT:
            self._begin_select(doc_x, doc_y)
        elif self.current_tool == Tool.TEXT:
            self.window.start_text_edit(doc_x, doc_y)
        else:
            self._active_handler = create_handler(self.current_tool, self.tool_ctx)
            if self._active_handler is not None:
                self._active_handler.press(self.doc, doc_x, doc_y)
                self.window.sync_undo_redo_sensitivity()
                self.queue_draw()

    def _on_primary_update(self, gesture, dx, dy):
        ok, sx, sy = gesture.get_start_point()
        if not ok:
            return
        x, y = sx + dx, sy + dy
        if self._panning:
            self._update_pan(x, y)
            return
        doc_x, doc_y = self.screen_to_doc(x, y)
        if self.current_tool == Tool.SELECT:
            self._update_select(doc_x, doc_y)
        elif self._active_handler is not None:
            self._active_handler.drag(self.doc, doc_x, doc_y)
        self.queue_draw()

    def _on_primary_end(self, gesture, dx, dy):
        if self._panning:
            self._panning = False
            return
        if self.current_tool == Tool.SELECT:
            self._end_select()
        elif self._active_handler is not None:
            ok, sx, sy = gesture.get_start_point()
            if ok:
                doc_x, doc_y = self.screen_to_doc(sx + dx, sy + dy)
                self._active_handler.release(self.doc, doc_x, doc_y)
            self._active_handler = None
        self.window.sync_undo_redo_sensitivity()
        self.window.mark_dirty()
        self.queue_draw()

    def _on_click_pressed(self, gesture, n_press, x, y):
        if n_press == 2 and self.current_tool == Tool.SELECT:
            doc_x, doc_y = self.screen_to_doc(x, y)
            shape = self._shape_at(doc_x, doc_y)
            if shape is not None and getattr(shape, "kind", None) == "text":
                self.window.edit_text_shape(shape)

    # --- select tool ------------------------------------------------------
    def _begin_select(self, x, y):
        selected = self.doc.selected_shape()
        if selected is not None:
            handle = self._hit_handle(selected, x, y)
            if handle is not None:
                self.doc.push_undo()
                self._select_mode = "resize"
                self._select_handle = handle
                self.queue_draw()
                return
        shape = self._shape_at(x, y)
        if shape is not None:
            self.doc.select(shape.id)
            self.doc.push_undo()
            self._select_mode = "move"
            self._last_doc_point = (x, y)
        else:
            self.doc.select(None)
            self._select_mode = None
        self.window.sync_undo_redo_sensitivity()
        self.queue_draw()

    def _update_select(self, x, y):
        selected = self.doc.selected_shape()
        if selected is None or self._select_mode is None:
            return
        if self._select_mode == "resize":
            selected.resize(self._select_handle, x, y)
        elif self._select_mode == "move":
            lx, ly = self._last_doc_point
            selected.move(x - lx, y - ly)
            self._last_doc_point = (x, y)
        self.doc.dirty = True

    def _end_select(self):
        self._select_mode = None
        self._select_handle = None

    def _shape_at(self, x, y):
        for shape in reversed(self.doc.shapes):
            if shape.hit_test(x, y, tolerance=SHAPE_HIT_TOLERANCE):
                return shape
        return None

    def _hit_handle(self, shape, x, y):
        tol = HANDLE_HIT_RADIUS / self.zoom
        best_name, best_dist = None, tol
        for name, (hx, hy) in shape.handles().items():
            dist = math.hypot(x - hx, y - hy)
            if dist <= best_dist:
                best_name, best_dist = name, dist
        return best_name

    # ------------------------------------------------------------------
    # Middle button / space+drag: panning
    # ------------------------------------------------------------------
    def _on_pan_begin(self, gesture, x, y):
        self._start_pan(x, y)

    def _on_pan_update(self, gesture, dx, dy):
        ok, sx, sy = gesture.get_start_point()
        if ok:
            self._update_pan(sx + dx, sy + dy)

    def _start_pan(self, x, y):
        self._panning = True
        self._pan_start_screen = (x, y)
        self._pan_origin = (self.pan_x, self.pan_y)
        self.set_cursor(Gdk.Cursor.new_from_name("grabbing"))

    def _update_pan(self, x, y):
        sx, sy = self._pan_start_screen
        ox, oy = self._pan_origin
        self.pan_x = ox + (x - sx)
        self.pan_y = oy + (y - sy)
        self.queue_draw()

    # ------------------------------------------------------------------
    # Scroll: pan, or zoom with Ctrl held
    # ------------------------------------------------------------------
    def _on_scroll(self, controller, dx, dy):
        event = controller.get_current_event()
        state = event.get_modifier_state() if event else 0
        ctrl = bool(state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl:
            factor = 1.1 if dy < 0 else (1 / 1.1)
            self.zoom_by(factor, center=self._last_pointer)
        else:
            self.pan_x -= dx * 50
            self.pan_y -= dy * 50
            self.queue_draw()
        return True

    def _on_motion(self, controller, x, y):
        self._last_pointer = (x, y)

    def zoom_by(self, factor, center=None):
        if center is None:
            center = (self.get_width() / 2, self.get_height() / 2)
        cx, cy = center
        doc_x, doc_y = self.screen_to_doc(cx, cy)
        self.zoom = max(MIN_ZOOM, min(MAX_ZOOM, self.zoom * factor))
        self.pan_x = cx - doc_x * self.zoom
        self.pan_y = cy - doc_y * self.zoom
        self.queue_draw()
        self.window.sync_zoom_label()

    def zoom_reset(self):
        self.zoom = 1.0
        self.pan_x = 0.0
        self.pan_y = 0.0
        self.queue_draw()
        self.window.sync_zoom_label()

    # ------------------------------------------------------------------
    # Keyboard: space-to-pan, tool mnemonics, delete
    # ------------------------------------------------------------------
    def _on_key_pressed(self, controller, keyval, keycode, state):
        name = Gdk.keyval_name(keyval) or ""
        if name == "space":
            self._space_down = True
            return True
        if name in ("Delete", "BackSpace"):
            if self.doc.selected_id is not None:
                self.doc.remove_selected()
                self.window.sync_undo_redo_sensitivity()
                self.window.mark_dirty()
                self.queue_draw()
            return True
        modifiers = state & (
            Gdk.ModifierType.CONTROL_MASK
            | Gdk.ModifierType.ALT_MASK
            | Gdk.ModifierType.SUPER_MASK
        )
        if not modifiers:
            tool = KEY_TO_TOOL.get(name.lower())
            if tool is not None:
                self.window.set_active_tool(tool)
                return True
        return False

    def _on_key_released(self, controller, keyval, keycode, state):
        name = Gdk.keyval_name(keyval) or ""
        if name == "space":
            self._space_down = False

    # ------------------------------------------------------------------
    # Drawing
    # ------------------------------------------------------------------
    def _on_draw(self, area, cr, width, height):
        dark = Adw.StyleManager.get_default().get_dark()
        bg = (0.13, 0.13, 0.15) if dark else (0.97, 0.97, 0.98)
        cr.set_source_rgb(*bg)
        cr.paint()

        cr.save()
        cr.translate(self.pan_x, self.pan_y)
        cr.scale(self.zoom, self.zoom)

        self._draw_grid(cr, width, height, dark)

        for shape in self.doc.shapes:
            if getattr(shape, "hidden", False):
                continue
            cr.save()
            shape.draw(cr)
            cr.restore()

        selected = self.doc.selected_shape()
        if selected is not None:
            self._draw_selection(cr, selected, dark)

        cr.restore()

    def _draw_grid(self, cr, width, height, dark):
        x0, y0 = self.screen_to_doc(0, 0)
        x1, y1 = self.screen_to_doc(width, height)
        color = (1, 1, 1, 0.05) if dark else (0, 0, 0, 0.055)
        cr.set_source_rgba(*color)
        cr.set_line_width(1.0 / self.zoom)
        gx = math.floor(x0 / GRID_SIZE) * GRID_SIZE
        while gx <= x1:
            cr.move_to(gx, y0)
            cr.line_to(gx, y1)
            gx += GRID_SIZE
        gy = math.floor(y0 / GRID_SIZE) * GRID_SIZE
        while gy <= y1:
            cr.move_to(x0, gy)
            cr.line_to(x1, gy)
            gy += GRID_SIZE
        cr.stroke()

    def _draw_selection(self, cr, shape, dark):
        accent = (0.29, 0.56, 0.98, 1.0)
        x0, y0, x1, y1 = shape.norm_bbox()
        pad = 5.0 / self.zoom
        cr.save()
        cr.set_source_rgba(*accent)
        cr.set_line_width(1.6 / self.zoom)
        cr.set_dash([5.0 / self.zoom, 3.5 / self.zoom])
        cr.rectangle(x0 - pad, y0 - pad, (x1 - x0) + 2 * pad, (y1 - y0) + 2 * pad)
        cr.stroke()
        cr.set_dash([])

        hs = HANDLE_SIZE / self.zoom
        for hx, hy in shape.handles().values():
            cr.rectangle(hx - hs / 2, hy - hs / 2, hs, hs)
            cr.set_source_rgba(1, 1, 1, 1)
            cr.fill_preserve()
            cr.set_source_rgba(*accent)
            cr.set_line_width(1.4 / self.zoom)
            cr.stroke()
        cr.restore()

    # ------------------------------------------------------------------
    # Document helpers used by Window / Sidebar / App actions
    # ------------------------------------------------------------------
    def set_document(self, doc: Document):
        self.doc = doc
        self._select_mode = None
        self._active_handler = None
        self.queue_draw()

    def new_document(self):
        self.set_document(Document())
        self.zoom_reset()

    def render_to_png(self, path, padding=40):
        import cairo

        bounds = self.doc.bounds()
        if bounds is None:
            bounds = (0, 0, 800, 600)
        x0, y0, x1, y1 = bounds
        w = max(1, int(x1 - x0 + padding * 2))
        h = max(1, int(y1 - y0 + padding * 2))
        surface = cairo.ImageSurface(cairo.FORMAT_ARGB32, w, h)
        cr = cairo.Context(surface)
        cr.set_source_rgb(1, 1, 1)
        cr.paint()
        cr.translate(padding - x0, padding - y0)
        for shape in self.doc.shapes:
            if getattr(shape, "hidden", False):
                continue
            cr.save()
            shape.draw(cr)
            cr.restore()
        surface.write_to_png(path)
