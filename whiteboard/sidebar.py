"""Left-hand tool palette + style controls (colors, stroke width, font size)."""
from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Gdk", "4.0")
from gi.repository import Adw, Gdk, Gtk

from .icons import make_color_swatch, make_tool_icon
from .tools import TOOL_LABELS, TOOL_ORDER, TOOL_SHORTCUTS, Tool

PALETTE = [
    (0.11, 0.11, 0.13, 1.0),   # ink
    (0.93, 0.16, 0.28, 1.0),   # red
    (0.98, 0.55, 0.10, 1.0),   # orange
    (0.98, 0.80, 0.08, 1.0),   # yellow
    (0.20, 0.72, 0.35, 1.0),   # green
    (0.16, 0.55, 0.95, 1.0),   # blue
    (0.55, 0.32, 0.95, 1.0),   # violet
    (0.95, 0.42, 0.75, 1.0),   # pink
    (0.55, 0.36, 0.24, 1.0),   # brown
    (1.00, 1.00, 1.00, 1.0),   # white
]

SHAPE_TOOLS = {Tool.RECTANGLE, Tool.ELLIPSE}
STROKE_TOOLS = {Tool.PEN, Tool.RECTANGLE, Tool.ELLIPSE, Tool.LINE, Tool.ARROW}


def _rgba_to_tuple(rgba: Gdk.RGBA):
    return (rgba.red, rgba.green, rgba.blue, rgba.alpha)


def _tuple_to_rgba(color):
    rgba = Gdk.RGBA()
    rgba.red, rgba.green, rgba.blue, rgba.alpha = color
    return rgba


class Sidebar(Gtk.Box):
    def __init__(self, window):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        self.window = window
        # Keep the sidebar a fixed width: without this, the fill row's
        # hexpand=True (used below to push the switch to the right)
        # would otherwise propagate up through the unset-hexpand parent
        # boxes and make the whole sidebar fight the canvas for width
        # whenever the fill panel becomes visible (Rectangle/Ellipse).
        self.set_hexpand(False)
        self.set_size_request(196, -1)
        self.add_css_class("wb-sidebar")
        self.set_margin_top(10)
        self.set_margin_bottom(10)
        self.set_margin_start(10)
        self.set_margin_end(10)

        self._tool_buttons = {}
        self.append(self._build_tool_palette())
        self.append(Gtk.Separator())
        self.append(self._build_style_section())

    # ------------------------------------------------------------------
    def _section_label(self, text):
        label = Gtk.Label(label=text, xalign=0)
        label.add_css_class("caption-heading")
        label.add_css_class("dim-label")
        return label

    def _build_tool_palette(self):
        grid = Gtk.Grid()
        grid.set_row_spacing(6)
        grid.set_column_spacing(6)
        grid.set_column_homogeneous(True)

        first_button = None
        for i, tool in enumerate(TOOL_ORDER):
            button = Gtk.ToggleButton()
            button.set_child(make_tool_icon(tool, size=22))
            shortcut = TOOL_SHORTCUTS[tool].upper()
            button.set_tooltip_text(f"{TOOL_LABELS[tool]} ({shortcut})")
            button.add_css_class("flat")
            button.set_size_request(-1, 40)
            if first_button is None:
                first_button = button
            else:
                button.set_group(first_button)
            self._tool_buttons[tool] = button
            grid.attach(button, i % 2, i // 2, 1, 1)

        # Set the initial selection before wiring "toggled", so the
        # window (which hasn't finished constructing the sidebar yet)
        # isn't notified during construction.
        self._tool_buttons[Tool.SELECT].set_active(True)
        for tool, button in self._tool_buttons.items():
            button.connect("toggled", self._on_tool_toggled, tool)
        return grid

    def _on_tool_toggled(self, button, tool):
        if button.get_active():
            self.window.set_active_tool(tool)

    def set_active_tool_button(self, tool):
        button = self._tool_buttons.get(tool)
        if button is not None and not button.get_active():
            button.set_active(True)
        self._update_visibility(tool)

    # ------------------------------------------------------------------
    def _build_style_section(self):
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

        box.append(self._section_label("Couleur du trait"))
        self.stroke_flow = self._build_palette_row(self._on_stroke_color_picked)
        box.append(self.stroke_flow)

        self.stroke_custom = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())
        self.stroke_custom.set_rgba(_tuple_to_rgba(self.window.canvas.tool_ctx.stroke_color))
        self.stroke_custom.connect("notify::rgba", self._on_stroke_custom_changed)
        self.stroke_custom.set_tooltip_text("Couleur personnalisée")
        box.append(self.stroke_custom)

        self.fill_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        fill_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8)
        fill_row.append(self._section_label("Remplissage"))
        self.fill_switch = Gtk.Switch()
        self.fill_switch.set_halign(Gtk.Align.END)
        self.fill_switch.set_hexpand(True)
        self.fill_switch.connect("notify::active", self._on_fill_toggled)
        fill_row.append(self.fill_switch)
        self.fill_group.append(fill_row)

        self.fill_custom = Gtk.ColorDialogButton(dialog=Gtk.ColorDialog())
        self.fill_custom.set_rgba(_tuple_to_rgba(self.window.canvas.tool_ctx.fill_color))
        self.fill_custom.connect("notify::rgba", self._on_fill_custom_changed)
        self.fill_group.append(self.fill_custom)
        box.append(self.fill_group)

        box.append(Gtk.Separator())
        box.append(self._section_label("Épaisseur du trait"))
        self.width_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 1, 30, 1)
        self.width_scale.set_value(self.window.canvas.tool_ctx.stroke_width)
        self.width_scale.set_draw_value(False)
        self.width_scale.connect("value-changed", self._on_width_changed)
        box.append(self.width_scale)

        self.font_group = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)
        self.font_group.append(self._section_label("Taille du texte"))
        self.font_scale = Gtk.Scale.new_with_range(Gtk.Orientation.HORIZONTAL, 8, 96, 1)
        self.font_scale.set_value(self.window.canvas.tool_ctx.font_size)
        self.font_scale.set_draw_value(False)
        self.font_scale.connect("value-changed", self._on_font_size_changed)
        self.font_group.append(self.font_scale)
        box.append(self.font_group)

        self.fill_switch.set_active(False)
        self._update_visibility(Tool.SELECT)
        return box

    def _build_palette_row(self, on_pick):
        flow = Gtk.FlowBox()
        flow.set_selection_mode(Gtk.SelectionMode.NONE)
        flow.set_max_children_per_line(5)
        flow.set_min_children_per_line(5)
        flow.set_row_spacing(4)
        flow.set_column_spacing(4)
        for color in PALETTE:
            button = Gtk.Button()
            button.set_child(make_color_swatch(color, size=22))
            button.add_css_class("flat")
            button.connect("clicked", lambda b, c=color: on_pick(c))
            flow.append(button)
        return flow

    def _update_visibility(self, tool):
        self.fill_group.set_visible(tool in SHAPE_TOOLS)
        self.width_scale.set_visible(tool in STROKE_TOOLS)
        self.font_group.set_visible(tool == Tool.TEXT)

    # ------------------------------------------------------------------
    # Style callbacks: update the active style context and, if a shape
    # is currently selected, restyle it live for immediate feedback.
    # ------------------------------------------------------------------
    def _on_stroke_color_picked(self, color):
        self.stroke_custom.set_rgba(_tuple_to_rgba(color))
        self._apply_stroke_color(color)

    def _on_stroke_custom_changed(self, button, _pspec):
        self._apply_stroke_color(_rgba_to_tuple(button.get_rgba()))

    def _apply_stroke_color(self, color):
        ctx = self.window.canvas.tool_ctx
        ctx.stroke_color = color
        selected = self.window.canvas.doc.selected_shape()
        if selected is not None:
            self.window.canvas.doc.push_undo()
            selected.stroke_color = color
            self.window.mark_dirty()
            self.window.canvas.queue_draw()

    def _on_fill_toggled(self, switch, _pspec):
        ctx = self.window.canvas.tool_ctx
        ctx.fill_enabled = switch.get_active()
        selected = self.window.canvas.doc.selected_shape()
        if selected is not None and hasattr(selected, "fill_color"):
            self.window.canvas.doc.push_undo()
            selected.fill_color = ctx.active_fill()
            self.window.mark_dirty()
            self.window.canvas.queue_draw()

    def _on_fill_custom_changed(self, button, _pspec):
        color = _rgba_to_tuple(button.get_rgba())
        ctx = self.window.canvas.tool_ctx
        ctx.fill_color = color
        selected = self.window.canvas.doc.selected_shape()
        if selected is not None and hasattr(selected, "fill_color") and ctx.fill_enabled:
            self.window.canvas.doc.push_undo()
            selected.fill_color = color
            self.window.mark_dirty()
            self.window.canvas.queue_draw()

    def _on_width_changed(self, scale):
        width = scale.get_value()
        ctx = self.window.canvas.tool_ctx
        ctx.stroke_width = width
        selected = self.window.canvas.doc.selected_shape()
        if selected is not None:
            selected.stroke_width = width
            self.window.canvas.queue_draw()

    def _on_font_size_changed(self, scale):
        size = scale.get_value()
        ctx = self.window.canvas.tool_ctx
        ctx.font_size = size
        selected = self.window.canvas.doc.selected_shape()
        if selected is not None and getattr(selected, "kind", None) == "text":
            selected.font_size = size
            self.window.canvas.queue_draw()
