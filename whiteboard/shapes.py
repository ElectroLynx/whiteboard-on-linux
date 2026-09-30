"""Shape model: every drawable object on the whiteboard canvas.

Each shape knows how to draw itself with Cairo, how to report its
bounding box and resize handles, how to hit-test a point, and how to
(de)serialize itself to/from a plain dict for JSON persistence.

Resize handles use a small fixed vocabulary so `Canvas` never needs to
know about shape-specific geometry:
  - "x0y0", "x1y0", "x0y1", "x1y1"  -> corner handles (rect/ellipse/stroke)
  - "p0", "p1"                       -> endpoint handles (line/arrow)
  - "x1y1"                           -> single resize handle (text)
"""
from __future__ import annotations

import math
import uuid

import gi

gi.require_version("Pango", "1.0")
gi.require_version("PangoCairo", "1.0")
from gi.repository import Pango, PangoCairo

DEFAULT_STROKE = (0.11, 0.11, 0.13, 1.0)


def point_segment_distance(px, py, x0, y0, x1, y1):
    """Shortest distance from point (px, py) to segment (x0,y0)-(x1,y1)."""
    dx, dy = x1 - x0, y1 - y0
    length_sq = dx * dx + dy * dy
    if length_sq == 0:
        return math.hypot(px - x0, py - y0)
    t = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / length_sq))
    proj_x, proj_y = x0 + t * dx, y0 + t * dy
    return math.hypot(px - proj_x, py - proj_y)


class Shape:
    """Base class for all drawable objects."""

    kind = "shape"

    def __init__(self, stroke_color=DEFAULT_STROKE, fill_color=None, stroke_width=3.0):
        self.id = uuid.uuid4().hex
        self.stroke_color = tuple(stroke_color)
        self.fill_color = tuple(fill_color) if fill_color else None
        self.stroke_width = float(stroke_width)
        self.hidden = False  # transient UI state (e.g. while text-editing); not persisted

    # --- geometry -----------------------------------------------------
    def bbox(self):
        """Return (x0, y0, x1, y1), not necessarily normalized."""
        raise NotImplementedError

    def norm_bbox(self):
        x0, y0, x1, y1 = self.bbox()
        return min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)

    def move(self, dx, dy):
        raise NotImplementedError

    def handles(self):
        """Return {handle_name: (x, y)} for resize handles."""
        return {}

    def resize(self, handle, x, y):
        pass

    # --- interaction ----------------------------------------------------
    def hit_test(self, x, y, tolerance=6.0):
        x0, y0, x1, y1 = self.norm_bbox()
        t = tolerance
        return x0 - t <= x <= x1 + t and y0 - t <= y <= y1 + t

    # --- rendering ------------------------------------------------------
    def draw(self, cr):
        raise NotImplementedError

    def _fill_and_stroke(self, cr, allow_fill=True):
        if allow_fill and self.fill_color:
            cr.set_source_rgba(*self.fill_color)
            cr.fill_preserve()
        cr.set_source_rgba(*self.stroke_color)
        cr.set_line_width(self.stroke_width)
        cr.stroke()

    # --- persistence ------------------------------------------------------
    def _base_dict(self):
        return {
            "type": self.kind,
            "id": self.id,
            "stroke_color": list(self.stroke_color),
            "fill_color": list(self.fill_color) if self.fill_color else None,
            "stroke_width": self.stroke_width,
        }

    def to_dict(self):
        raise NotImplementedError

    def _restore_base(self, d):
        self.id = d.get("id", self.id)
        self.stroke_color = tuple(d.get("stroke_color", DEFAULT_STROKE))
        fc = d.get("fill_color")
        self.fill_color = tuple(fc) if fc else None
        self.stroke_width = float(d.get("stroke_width", 3.0))


class BBoxShape(Shape):
    """Shapes defined by two opposite corners: Rectangle, Ellipse."""

    def __init__(self, x0, y0, x1, y1, **kwargs):
        super().__init__(**kwargs)
        self.x0, self.y0, self.x1, self.y1 = float(x0), float(y0), float(x1), float(y1)

    def bbox(self):
        return self.x0, self.y0, self.x1, self.y1

    def move(self, dx, dy):
        self.x0 += dx
        self.y0 += dy
        self.x1 += dx
        self.y1 += dy

    def handles(self):
        return {
            "x0y0": (self.x0, self.y0),
            "x1y0": (self.x1, self.y0),
            "x0y1": (self.x0, self.y1),
            "x1y1": (self.x1, self.y1),
        }

    def resize(self, handle, x, y):
        if handle == "x0y0":
            self.x0, self.y0 = x, y
        elif handle == "x1y0":
            self.x1, self.y0 = x, y
        elif handle == "x0y1":
            self.x0, self.y1 = x, y
        elif handle == "x1y1":
            self.x1, self.y1 = x, y

    def to_dict(self):
        d = self._base_dict()
        d.update(x0=self.x0, y0=self.y0, x1=self.x1, y1=self.y1)
        return d

    @classmethod
    def from_dict(cls, d):
        shape = cls(d["x0"], d["y0"], d["x1"], d["y1"])
        shape._restore_base(d)
        return shape


class Rectangle(BBoxShape):
    kind = "rectangle"

    def draw(self, cr):
        x0, y0, x1, y1 = self.norm_bbox()
        radius = min(10.0, abs(x1 - x0) / 2, abs(y1 - y0) / 2)
        if radius > 1:
            self._rounded_rect(cr, x0, y0, x1, y1, radius)
        else:
            cr.rectangle(x0, y0, x1 - x0, y1 - y0)
        self._fill_and_stroke(cr)

    @staticmethod
    def _rounded_rect(cr, x0, y0, x1, y1, r):
        cr.new_sub_path()
        cr.arc(x1 - r, y0 + r, r, -math.pi / 2, 0)
        cr.arc(x1 - r, y1 - r, r, 0, math.pi / 2)
        cr.arc(x0 + r, y1 - r, r, math.pi / 2, math.pi)
        cr.arc(x0 + r, y0 + r, r, math.pi, 3 * math.pi / 2)
        cr.close_path()


class Ellipse(BBoxShape):
    kind = "ellipse"

    def draw(self, cr):
        x0, y0, x1, y1 = self.norm_bbox()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = max((x1 - x0) / 2, 0.01), max((y1 - y0) / 2, 0.01)
        cr.save()
        cr.translate(cx, cy)
        cr.scale(rx, ry)
        cr.arc(0, 0, 1, 0, 2 * math.pi)
        cr.restore()
        self._fill_and_stroke(cr)

    def hit_test(self, x, y, tolerance=6.0):
        x0, y0, x1, y1 = self.norm_bbox()
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        rx, ry = max((x1 - x0) / 2, 0.01) + tolerance, max((y1 - y0) / 2, 0.01) + tolerance
        nx, ny = (x - cx) / rx, (y - cy) / ry
        return (nx * nx + ny * ny) <= 1.0


class TwoPointShape(Shape):
    """Shapes defined by two endpoints: Line, Arrow."""

    def __init__(self, x0, y0, x1, y1, **kwargs):
        super().__init__(**kwargs)
        self.x0, self.y0, self.x1, self.y1 = float(x0), float(y0), float(x1), float(y1)

    def bbox(self):
        return self.x0, self.y0, self.x1, self.y1

    def move(self, dx, dy):
        self.x0 += dx
        self.y0 += dy
        self.x1 += dx
        self.y1 += dy

    def handles(self):
        return {"p0": (self.x0, self.y0), "p1": (self.x1, self.y1)}

    def resize(self, handle, x, y):
        if handle == "p0":
            self.x0, self.y0 = x, y
        elif handle == "p1":
            self.x1, self.y1 = x, y

    def hit_test(self, x, y, tolerance=6.0):
        tol = tolerance + self.stroke_width
        return point_segment_distance(x, y, self.x0, self.y0, self.x1, self.y1) <= tol

    def to_dict(self):
        d = self._base_dict()
        d.update(x0=self.x0, y0=self.y0, x1=self.x1, y1=self.y1)
        return d

    @classmethod
    def from_dict(cls, d):
        shape = cls(d["x0"], d["y0"], d["x1"], d["y1"])
        shape._restore_base(d)
        return shape


class Line(TwoPointShape):
    kind = "line"

    def draw(self, cr):
        cr.set_source_rgba(*self.stroke_color)
        cr.set_line_width(self.stroke_width)
        cr.set_line_cap(1)  # ROUND
        cr.move_to(self.x0, self.y0)
        cr.line_to(self.x1, self.y1)
        cr.stroke()


class Arrow(TwoPointShape):
    kind = "arrow"

    def draw(self, cr):
        cr.set_source_rgba(*self.stroke_color)
        cr.set_line_width(self.stroke_width)
        cr.set_line_cap(1)  # ROUND
        cr.set_line_join(1)  # ROUND
        cr.move_to(self.x0, self.y0)
        cr.line_to(self.x1, self.y1)
        cr.stroke()

        angle = math.atan2(self.y1 - self.y0, self.x1 - self.x0)
        head_len = max(12.0, self.stroke_width * 3.2)
        spread = math.radians(28)
        for sign in (-1, 1):
            a = angle + math.pi - sign * spread
            hx = self.x1 + head_len * math.cos(a)
            hy = self.y1 + head_len * math.sin(a)
            cr.move_to(self.x1, self.y1)
            cr.line_to(hx, hy)
        cr.stroke()


class Stroke(Shape):
    """Freehand pen path: a poly-line of points."""

    kind = "stroke"

    def __init__(self, points=None, **kwargs):
        super().__init__(**kwargs)
        self.points = [tuple(p) for p in (points or [])]

    def add_point(self, x, y):
        self.points.append((x, y))

    def bbox(self):
        if not self.points:
            return 0.0, 0.0, 0.0, 0.0
        xs = [p[0] for p in self.points]
        ys = [p[1] for p in self.points]
        return min(xs), min(ys), max(xs), max(ys)

    def move(self, dx, dy):
        self.points = [(x + dx, y + dy) for x, y in self.points]

    def handles(self):
        x0, y0, x1, y1 = self.bbox()
        return {"x0y0": (x0, y0), "x1y0": (x1, y0), "x0y1": (x0, y1), "x1y1": (x1, y1)}

    def resize(self, handle, x, y):
        x0, y0, x1, y1 = self.bbox()
        nx0, ny0, nx1, ny1 = x0, y0, x1, y1
        if handle == "x0y0":
            nx0, ny0 = x, y
        elif handle == "x1y0":
            nx1, ny0 = x, y
        elif handle == "x0y1":
            nx0, ny1 = x, y
        elif handle == "x1y1":
            nx1, ny1 = x, y
        old_w = (x1 - x0) or 1e-6
        old_h = (y1 - y0) or 1e-6
        new_w = (nx1 - nx0) or 1e-6
        new_h = (ny1 - ny0) or 1e-6
        sx, sy = new_w / old_w, new_h / old_h
        self.points = [(nx0 + (px - x0) * sx, ny0 + (py - y0) * sy) for px, py in self.points]

    def hit_test(self, x, y, tolerance=6.0):
        tol = tolerance + self.stroke_width
        pts = self.points
        if len(pts) == 1:
            return math.hypot(x - pts[0][0], y - pts[0][1]) <= tol
        for (x0, y0), (x1, y1) in zip(pts, pts[1:]):
            if point_segment_distance(x, y, x0, y0, x1, y1) <= tol:
                return True
        return False

    def draw(self, cr):
        if not self.points:
            return
        cr.set_source_rgba(*self.stroke_color)
        if len(self.points) == 1:
            x, y = self.points[0]
            cr.arc(x, y, self.stroke_width / 2, 0, 2 * math.pi)
            cr.fill()
            return
        cr.set_line_width(self.stroke_width)
        cr.set_line_cap(1)  # ROUND
        cr.set_line_join(1)  # ROUND
        cr.move_to(*self.points[0])
        for p in self.points[1:]:
            cr.line_to(*p)
        cr.stroke()

    def to_dict(self):
        d = self._base_dict()
        d["points"] = [list(p) for p in self.points]
        return d

    @classmethod
    def from_dict(cls, d):
        shape = cls(points=[tuple(p) for p in d.get("points", [])])
        shape._restore_base(d)
        return shape


class TextShape(Shape):
    """A rendered text label, positioned by its top-left corner."""

    kind = "text"

    def __init__(self, x, y, text="", font_size=28.0, color=DEFAULT_STROKE, **kwargs):
        kwargs.setdefault("stroke_color", color)
        super().__init__(**kwargs)
        self.x, self.y = float(x), float(y)
        self.text = text
        self.font_size = float(font_size)
        self._w, self._h = 20.0, self.font_size * 1.3

    def bbox(self):
        return self.x, self.y, self.x + self._w, self.y + self._h

    def move(self, dx, dy):
        self.x += dx
        self.y += dy

    def handles(self):
        x0, y0, x1, y1 = self.bbox()
        return {"x1y1": (x1, y1)}

    def resize(self, handle, x, y):
        if handle == "x1y1":
            new_w = max(10.0, x - self.x)
            scale = new_w / self._w if self._w else 1.0
            self.font_size = max(6.0, min(400.0, self.font_size * scale))

    def hit_test(self, x, y, tolerance=4.0):
        x0, y0, x1, y1 = self.bbox()
        return x0 - tolerance <= x <= x1 + tolerance and y0 - tolerance <= y <= y1 + tolerance

    def _layout(self, cr):
        layout = PangoCairo.create_layout(cr)
        layout.set_text(self.text or "", -1)
        font_desc = Pango.FontDescription.new()
        font_desc.set_family("Cantarell, Sans")
        font_desc.set_absolute_size(self.font_size * Pango.SCALE)
        layout.set_font_description(font_desc)
        return layout

    def draw(self, cr):
        layout = self._layout(cr)
        _ink, logical = layout.get_pixel_extents()
        self._w = max(logical.width, 20.0)
        self._h = max(logical.height, self.font_size * 1.3)
        cr.save()
        cr.set_source_rgba(*self.stroke_color)
        cr.move_to(self.x, self.y)
        PangoCairo.show_layout(cr, layout)
        cr.restore()

    def to_dict(self):
        d = self._base_dict()
        d.update(x=self.x, y=self.y, text=self.text, font_size=self.font_size)
        return d

    @classmethod
    def from_dict(cls, d):
        shape = cls(d["x"], d["y"], text=d.get("text", ""), font_size=d.get("font_size", 28.0))
        shape._restore_base(d)
        return shape


_REGISTRY = {
    "rectangle": Rectangle,
    "ellipse": Ellipse,
    "line": Line,
    "arrow": Arrow,
    "stroke": Stroke,
    "text": TextShape,
}


def shape_from_dict(d):
    cls = _REGISTRY.get(d.get("type"))
    if cls is None:
        raise ValueError(f"Unknown shape type: {d.get('type')!r}")
    return cls.from_dict(d)
