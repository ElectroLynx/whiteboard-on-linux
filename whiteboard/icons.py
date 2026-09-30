"""Small, crisp Cairo-drawn glyphs for the tool palette and color swatches.

The Adwaita icon theme has no icons for "draw a rectangle" or "freehand
pen", so each tool gets a tiny hand-drawn vector pictogram instead of a
mismatched stock icon. Pictograms use the widget's current foreground
color (`Gtk.Widget.get_color()`), so they automatically adapt to
light/dark mode and to selected/insensitive button states.
"""
from __future__ import annotations

import math

import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

from .tools import Tool


def _rgba(cr, rgba):
    cr.set_source_rgba(rgba.red, rgba.green, rgba.blue, rgba.alpha)


def _rounded_rect_path(cr, x0, y0, x1, y1, r):
    cr.new_sub_path()
    cr.arc(x1 - r, y0 + r, r, -math.pi / 2, 0)
    cr.arc(x1 - r, y1 - r, r, 0, math.pi / 2)
    cr.arc(x0 + r, y1 - r, r, math.pi / 2, math.pi)
    cr.arc(x0 + r, y0 + r, r, math.pi, 3 * math.pi / 2)
    cr.close_path()


def _draw_select(cr, s, rgba):
    _rgba(cr, rgba)
    cr.move_to(s * 0.20, s * 0.12)
    cr.line_to(s * 0.20, s * 0.84)
    cr.line_to(s * 0.39, s * 0.67)
    cr.line_to(s * 0.53, s * 0.88)
    cr.line_to(s * 0.64, s * 0.81)
    cr.line_to(s * 0.50, s * 0.60)
    cr.line_to(s * 0.72, s * 0.58)
    cr.close_path()
    cr.fill()


def _draw_pen(cr, s, rgba):
    cr.save()
    cr.translate(s * 0.5, s * 0.5)
    cr.rotate(math.radians(-45))
    _rgba(cr, rgba)
    body_w, body_h = s * 0.16, s * 0.62
    cr.move_to(-body_w / 2, -body_h / 2)
    cr.line_to(body_w / 2, -body_h / 2)
    cr.line_to(body_w / 2, body_h / 2 - body_w / 2)
    cr.line_to(0, body_h / 2)
    cr.line_to(-body_w / 2, body_h / 2 - body_w / 2)
    cr.close_path()
    cr.fill()
    cr.restore()


def _draw_rectangle(cr, s, rgba):
    _rgba(cr, rgba)
    cr.set_line_width(s * 0.09)
    m, r = s * 0.20, s * 0.08
    _rounded_rect_path(cr, m, m, s - m, s - m, r)
    cr.stroke()


def _draw_ellipse(cr, s, rgba):
    _rgba(cr, rgba)
    cr.set_line_width(s * 0.09)
    cr.save()
    cr.translate(s * 0.5, s * 0.5)
    cr.scale(s * 0.36, s * 0.30)
    cr.arc(0, 0, 1, 0, 2 * math.pi)
    cr.restore()
    cr.stroke()


def _draw_line(cr, s, rgba):
    _rgba(cr, rgba)
    cr.set_line_width(s * 0.10)
    cr.set_line_cap(1)  # round
    cr.move_to(s * 0.18, s * 0.80)
    cr.line_to(s * 0.82, s * 0.20)
    cr.stroke()


def _draw_arrow(cr, s, rgba):
    _rgba(cr, rgba)
    cr.set_line_width(s * 0.09)
    cr.set_line_cap(1)  # round
    cr.set_line_join(1)  # round
    x0, y0, x1, y1 = s * 0.16, s * 0.82, s * 0.82, s * 0.18
    cr.move_to(x0, y0)
    cr.line_to(x1, y1)
    cr.stroke()
    angle = math.atan2(y1 - y0, x1 - x0)
    head, spread = s * 0.24, math.radians(28)
    for sign in (-1, 1):
        a = angle + math.pi - sign * spread
        cr.move_to(x1, y1)
        cr.line_to(x1 + head * math.cos(a), y1 + head * math.sin(a))
    cr.stroke()


def _draw_text(cr, s, rgba):
    _rgba(cr, rgba)
    cr.set_line_width(s * 0.11)
    cr.set_line_cap(2)  # square, crisp corners
    cr.move_to(s * 0.20, s * 0.24)
    cr.line_to(s * 0.80, s * 0.24)
    cr.stroke()
    cr.move_to(s * 0.50, s * 0.24)
    cr.line_to(s * 0.50, s * 0.80)
    cr.stroke()


def _draw_eraser(cr, s, rgba):
    cr.save()
    cr.translate(s * 0.5, s * 0.5)
    cr.rotate(math.radians(-30))
    _rgba(cr, rgba)
    w, h, r = s * 0.62, s * 0.34, s * 0.07
    x0, y0, x1, y1 = -w / 2, -h / 2, w / 2, h / 2
    _rounded_rect_path(cr, x0, y0, x1, y1, r)
    cr.set_line_width(s * 0.05)
    cr.stroke()
    cr.move_to(-w * 0.12, y0)
    cr.line_to(-w * 0.12, y1)
    cr.set_line_width(s * 0.035)
    cr.stroke()
    cr.restore()


_DRAW_FUNCS = {
    Tool.SELECT: _draw_select,
    Tool.PEN: _draw_pen,
    Tool.RECTANGLE: _draw_rectangle,
    Tool.ELLIPSE: _draw_ellipse,
    Tool.LINE: _draw_line,
    Tool.ARROW: _draw_arrow,
    Tool.TEXT: _draw_text,
    Tool.ERASER: _draw_eraser,
}


def make_tool_icon(tool: Tool, size: int = 22) -> Gtk.Widget:
    """A small DrawingArea painting a pictogram for `tool`."""
    area = Gtk.DrawingArea()
    area.set_content_width(size)
    area.set_content_height(size)
    area.set_can_target(False)
    draw_fn = _DRAW_FUNCS.get(tool, _draw_select)

    def _draw(widget, cr, w, h, *_ignored):
        rgba = widget.get_color()
        draw_fn(cr, min(w, h), rgba)

    area.set_draw_func(_draw)
    return area


def make_color_swatch(color, size: int = 22) -> Gtk.Widget:
    """A small round swatch filled with `color` (r, g, b, a)."""
    area = Gtk.DrawingArea()
    area.set_content_width(size)
    area.set_content_height(size)
    area.set_can_target(False)

    def _draw(widget, cr, w, h, *_ignored):
        cx, cy = w / 2, h / 2
        r = min(w, h) / 2 - 1.5
        cr.arc(cx, cy, r, 0, 2 * math.pi)
        cr.set_source_rgba(*color)
        cr.fill_preserve()
        cr.set_source_rgba(0, 0, 0, 0.18)
        cr.set_line_width(1.2)
        cr.stroke()

    area.set_draw_func(_draw)
    return area
