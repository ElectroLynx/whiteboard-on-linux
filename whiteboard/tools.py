"""Tools: what happens while the pointer is pressed/dragged/released.

`ToolContext` holds the *style* used for newly created shapes (color,
stroke width, fill, font size). `ToolHandler` subclasses implement the
press/drag/release lifecycle for tools that create a new shape by
dragging (pen, rectangle, ellipse, line, arrow, eraser).

The Select and Text tools need extra context (existing shapes / the
window's overlay for the text entry) so they are implemented directly
in `canvas.py`; only their enum members and labels live here.
"""
from __future__ import annotations

from enum import Enum

from .shapes import Arrow, Ellipse, Line, Rectangle, Stroke


class Tool(Enum):
    SELECT = "select"
    PEN = "pen"
    RECTANGLE = "rectangle"
    ELLIPSE = "ellipse"
    LINE = "line"
    ARROW = "arrow"
    TEXT = "text"
    ERASER = "eraser"


TOOL_ORDER = [
    Tool.SELECT,
    Tool.PEN,
    Tool.RECTANGLE,
    Tool.ELLIPSE,
    Tool.LINE,
    Tool.ARROW,
    Tool.TEXT,
    Tool.ERASER,
]

TOOL_LABELS = {
    Tool.SELECT: "Sélection",
    Tool.PEN: "Stylo",
    Tool.RECTANGLE: "Rectangle",
    Tool.ELLIPSE: "Ellipse",
    Tool.LINE: "Ligne",
    Tool.ARROW: "Flèche",
    Tool.TEXT: "Texte",
    Tool.ERASER: "Gomme",
}

# Single-letter mnemonics, active when no modifier key is held and the
# text tool isn't currently editing.
TOOL_SHORTCUTS = {
    Tool.SELECT: "s",
    Tool.PEN: "p",
    Tool.RECTANGLE: "r",
    Tool.ELLIPSE: "o",
    Tool.LINE: "l",
    Tool.ARROW: "a",
    Tool.TEXT: "t",
    Tool.ERASER: "e",
}

KEY_TO_TOOL = {v: k for k, v in TOOL_SHORTCUTS.items()}


class ToolContext:
    """Current drawing style applied to newly created shapes."""

    def __init__(self):
        self.stroke_color = (0.11, 0.11, 0.13, 1.0)
        self.fill_color = (0.30, 0.55, 0.95, 1.0)
        self.fill_enabled = False
        self.stroke_width = 4.0
        self.font_size = 28.0

    def active_fill(self):
        return self.fill_color if self.fill_enabled else None


class ToolHandler:
    """Base interaction handler: create+grow a shape while dragging."""

    shape_cls = None

    def __init__(self, ctx: ToolContext):
        self.ctx = ctx
        self.shape = None

    def press(self, doc, x, y):
        raise NotImplementedError

    def drag(self, doc, x, y):
        pass

    def release(self, doc, x, y):
        self.shape = None


class _CornerShapeHandler(ToolHandler):
    """Rectangle / Ellipse: drag from one corner to the opposite one."""

    def press(self, doc, x, y):
        self.shape = self.shape_cls(
            x, y, x, y,
            stroke_color=self.ctx.stroke_color,
            fill_color=self.ctx.active_fill(),
            stroke_width=self.ctx.stroke_width,
        )
        doc.add_shape(self.shape)

    def drag(self, doc, x, y):
        if self.shape is not None:
            self.shape.resize("x1y1", x, y)


class RectangleHandler(_CornerShapeHandler):
    shape_cls = Rectangle


class EllipseHandler(_CornerShapeHandler):
    shape_cls = Ellipse


class _TwoPointShapeHandler(ToolHandler):
    """Line / Arrow: drag from the start point to the end point."""

    def press(self, doc, x, y):
        self.shape = self.shape_cls(
            x, y, x, y,
            stroke_color=self.ctx.stroke_color,
            stroke_width=self.ctx.stroke_width,
        )
        doc.add_shape(self.shape)

    def drag(self, doc, x, y):
        if self.shape is not None:
            self.shape.resize("p1", x, y)


class LineHandler(_TwoPointShapeHandler):
    shape_cls = Line


class ArrowHandler(_TwoPointShapeHandler):
    shape_cls = Arrow


class PenHandler(ToolHandler):
    """Freehand drawing: accumulate points while dragging."""

    def press(self, doc, x, y):
        self.shape = Stroke(
            points=[(x, y)],
            stroke_color=self.ctx.stroke_color,
            stroke_width=self.ctx.stroke_width,
        )
        doc.add_shape(self.shape)

    def drag(self, doc, x, y):
        if self.shape is not None:
            self.shape.add_point(x, y)


class EraserHandler(ToolHandler):
    """Delete whichever shape is under the pointer while dragging."""

    def press(self, doc, x, y):
        self._erase_at(doc, x, y)

    def drag(self, doc, x, y):
        self._erase_at(doc, x, y)

    @staticmethod
    def _erase_at(doc, x, y):
        for shape in reversed(doc.shapes):
            if shape.hit_test(x, y):
                doc.remove_shape(shape.id)
                break


_HANDLERS = {
    Tool.RECTANGLE: RectangleHandler,
    Tool.ELLIPSE: EllipseHandler,
    Tool.LINE: LineHandler,
    Tool.ARROW: ArrowHandler,
    Tool.PEN: PenHandler,
    Tool.ERASER: EraserHandler,
}


def create_handler(tool: Tool, ctx: ToolContext):
    """Return a fresh ToolHandler for `tool`, or None (SELECT/TEXT)."""
    cls = _HANDLERS.get(tool)
    return cls(ctx) if cls else None
