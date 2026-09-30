"""Document model: the ordered list of shapes plus undo/redo and I/O."""
from __future__ import annotations

import copy
import json

from .shapes import shape_from_dict

FORMAT_VERSION = 1
MAX_HISTORY = 60


class Document:
    def __init__(self):
        self.shapes = []
        self.selected_id = None
        self.file_path = None
        self.dirty = False
        self._undo_stack = []
        self._redo_stack = []

    # --- selection ------------------------------------------------------
    def selected_shape(self):
        if self.selected_id is None:
            return None
        for shape in self.shapes:
            if shape.id == self.selected_id:
                return shape
        return None

    def select(self, shape_id):
        self.selected_id = shape_id

    # --- mutation (undo-aware) ------------------------------------------
    def push_undo(self):
        self._undo_stack.append(self._snapshot())
        if len(self._undo_stack) > MAX_HISTORY:
            self._undo_stack.pop(0)
        self._redo_stack.clear()

    def _snapshot(self):
        return [copy.deepcopy(s) for s in self.shapes]

    def add_shape(self, shape, record=True):
        if record:
            self.push_undo()
        self.shapes.append(shape)
        self.selected_id = shape.id
        self.dirty = True

    def remove_shape(self, shape_id, record=True):
        if record:
            self.push_undo()
        self.shapes = [s for s in self.shapes if s.id != shape_id]
        if self.selected_id == shape_id:
            self.selected_id = None
        self.dirty = True

    def remove_selected(self):
        if self.selected_id is not None:
            self.remove_shape(self.selected_id)

    def bring_to_front(self, shape_id):
        shape = next((s for s in self.shapes if s.id == shape_id), None)
        if shape is None:
            return
        self.push_undo()
        self.shapes.remove(shape)
        self.shapes.append(shape)
        self.dirty = True

    def send_to_back(self, shape_id):
        shape = next((s for s in self.shapes if s.id == shape_id), None)
        if shape is None:
            return
        self.push_undo()
        self.shapes.remove(shape)
        self.shapes.insert(0, shape)
        self.dirty = True

    def clear(self, record=True):
        if record and self.shapes:
            self.push_undo()
        self.shapes = []
        self.selected_id = None
        self.dirty = False

    # --- undo/redo --------------------------------------------------------
    def can_undo(self):
        return bool(self._undo_stack)

    def can_redo(self):
        return bool(self._redo_stack)

    def undo(self):
        if not self._undo_stack:
            return False
        self._redo_stack.append(self._snapshot())
        self.shapes = self._undo_stack.pop()
        self.selected_id = None
        self.dirty = True
        return True

    def redo(self):
        if not self._redo_stack:
            return False
        self._undo_stack.append(self._snapshot())
        self.shapes = self._redo_stack.pop()
        self.selected_id = None
        self.dirty = True
        return True

    def reset_history(self):
        self._undo_stack.clear()
        self._redo_stack.clear()

    # --- persistence -----------------------------------------------------
    def to_dict(self):
        return {"version": FORMAT_VERSION, "shapes": [s.to_dict() for s in self.shapes]}

    @classmethod
    def from_dict(cls, data):
        doc = cls()
        doc.shapes = [shape_from_dict(sd) for sd in data.get("shapes", [])]
        return doc

    def save(self, path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2)
        self.file_path = path
        self.dirty = False

    @classmethod
    def load(cls, path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        doc = cls.from_dict(data)
        doc.file_path = path
        return doc

    def bounds(self):
        """Bounding box covering all shapes, or None if empty."""
        if not self.shapes:
            return None
        x0s, y0s, x1s, y1s = [], [], [], []
        for s in self.shapes:
            a, b, c, d = s.norm_bbox()
            x0s.append(a)
            y0s.append(b)
            x1s.append(c)
            y1s.append(d)
        return min(x0s), min(y0s), max(x1s), max(y1s)
