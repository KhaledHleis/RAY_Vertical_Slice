"""Table editor for LightCollider segments.

Each row is one segment: both endpoints in local space plus the three material
parameters that `LightSource:castRay` reads. The material colour swatch uses the
same convention as `debug_light_renderer.lua`, so a row reads the same way as
the gizmo in the viewport and the overlay in the running game.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QAbstractItemView, QDoubleSpinBox, QHBoxLayout,
                             QHeaderView, QLabel, QPushButton, QTableWidget,
                             QTableWidgetItem, QVBoxLayout, QWidget)

from ..luaio.types import Vec2
from ..model import generators

COLUMNS = ["", "ax", "ay", "bx", "by", "reflect", "refract", "absorb", "length"]
MATERIAL_COLUMN = 0
LENGTH_COLUMN = 8


def material_label(segment):
    if float(segment.get("refractiveIndex", 1) or 1) != 1:
        return "glass", QColor(75, 150, 255)
    if float(segment.get("reflective", 0) or 0) > 0:
        return "mirror", QColor(230, 230, 50)
    if float(segment.get("absorption", 0) or 0) > 0:
        return "absorb", QColor(205, 50, 50)
    return "inert", QColor(180, 180, 180)


class SegmentTable(QWidget):
    changed = pyqtSignal()
    editCommitted = pyqtSignal()
    selectionChanged = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.component = None
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        self.table.verticalHeader().setDefaultSectionSize(24)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeMode.ResizeToContents)
        self.table.itemSelectionChanged.connect(self._on_selection)
        layout.addWidget(self.table)

        buttons = QHBoxLayout()
        buttons.setSpacing(4)
        for label, slot, tip in (
            ("Add", self.add_segment, "Append a new horizontal segment"),
            ("Duplicate", self.duplicate_segment, "Copy the selected segment"),
            ("Remove", self.remove_segment, "Delete the selected segment"),
            ("Flip", self.flip_segment, "Swap the endpoints, reversing the normal"),
        ):
            button = QPushButton(label)
            button.setToolTip(tip)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        buttons.addStretch(1)
        layout.addLayout(buttons)

        hint = QLabel("Endpoints are in local space; the engine rotates them by "
                      "the object's angle each frame when dynamic is set.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: #888; font-size: 11px;")
        layout.addWidget(hint)

    # -- data --------------------------------------------------------------

    def set_component(self, component):
        self.component = component
        self.refresh()

    def segments(self):
        if self.component is None:
            return []
        segments = self.component.get("segments")
        if segments is None:
            segments = []
            self.component.set("segments", segments)
        return segments

    def selected_index(self):
        rows = self.table.selectionModel().selectedRows() if self.table.selectionModel() else []
        return rows[0].row() if rows else -1

    def select(self, index):
        if index is None or index < 0 or index >= self.table.rowCount():
            return
        self._updating = True
        self.table.selectRow(index)
        self._updating = False

    def refresh(self):
        self._updating = True
        segments = self.segments()
        self.table.setRowCount(len(segments))

        for row, segment in enumerate(segments):
            label, color = material_label(segment)
            item = QTableWidgetItem(label)
            item.setForeground(color)
            item.setFlags(Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable)
            self.table.setItem(row, MATERIAL_COLUMN, item)

            a, b = segment.get("a"), segment.get("b")
            self._numeric_cell(row, 1, float(a.x), lambda v, r=row: self._set_point(r, "a", "x", v))
            self._numeric_cell(row, 2, float(a.y), lambda v, r=row: self._set_point(r, "a", "y", v))
            self._numeric_cell(row, 3, float(b.x), lambda v, r=row: self._set_point(r, "b", "x", v))
            self._numeric_cell(row, 4, float(b.y), lambda v, r=row: self._set_point(r, "b", "y", v))
            self._numeric_cell(row, 5, float(segment.get("reflective", 0) or 0),
                               lambda v, r=row: self._set_material(r, "reflective", v),
                               low=0.0, high=1.0, step=0.05)
            self._numeric_cell(row, 6, float(segment.get("refractiveIndex", 1) or 1),
                               lambda v, r=row: self._set_material(r, "refractiveIndex", v),
                               low=0.1, high=4.0, step=0.05)
            self._numeric_cell(row, 7, float(segment.get("absorption", 0) or 0),
                               lambda v, r=row: self._set_material(r, "absorption", v),
                               low=0.0, high=1.0, step=0.05)

            length = math.hypot(float(b.x) - float(a.x), float(b.y) - float(a.y))
            length_item = QTableWidgetItem(f"{length:.1f}")
            length_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            if length < 1e-6:
                length_item.setForeground(QColor(230, 80, 80))
                length_item.setToolTip("Zero-length segments can never be hit.")
            self.table.setItem(row, LENGTH_COLUMN, length_item)

        self._updating = False

    def _numeric_cell(self, row, column, value, setter, low=-100000.0, high=100000.0, step=1.0):
        box = QDoubleSpinBox()
        box.setRange(low, high)
        box.setDecimals(3)
        box.setSingleStep(step)
        box.setKeyboardTracking(False)
        box.setValue(value)
        box.setFrame(False)
        box.valueChanged.connect(lambda v: None if self._updating else setter(v))
        box.editingFinished.connect(lambda: None if self._updating else self.editCommitted.emit())
        self.table.setCellWidget(row, column, box)

    # -- mutation ----------------------------------------------------------

    def _set_point(self, row, key, axis, value):
        segments = self.segments()
        if row >= len(segments):
            return
        segment = segments[row]
        point = segment.get(key) or Vec2(0.0, 0.0, Vec2.CALL)
        x = float(value) if axis == "x" else float(point.x)
        y = float(value) if axis == "y" else float(point.y)
        segment[key] = Vec2(x, y, point.style or Vec2.CALL)
        segment.setdefault("_explicit", set()).add(key)
        self._refresh_derived(row)
        self.changed.emit()

    def _set_material(self, row, key, value):
        segments = self.segments()
        if row >= len(segments):
            return
        segments[row][key] = float(value)
        segments[row].setdefault("_explicit", set()).add(key)
        self._refresh_derived(row)
        self.changed.emit()

    def _refresh_derived(self, row):
        segments = self.segments()
        if row >= len(segments):
            return
        segment = segments[row]
        label, color = material_label(segment)
        item = self.table.item(row, MATERIAL_COLUMN)
        if item is not None:
            item.setText(label)
            item.setForeground(color)
        a, b = segment.get("a"), segment.get("b")
        length = math.hypot(float(b.x) - float(a.x), float(b.y) - float(a.y))
        length_item = self.table.item(row, LENGTH_COLUMN)
        if length_item is not None:
            length_item.setText(f"{length:.1f}")

    def add_segment(self):
        if self.component is None:
            return
        segments = self.segments()
        segments.append(generators.new_segment(segments[-1] if segments else None))
        self.component.explicit.add("segments")
        self.refresh()
        self.select(len(segments) - 1)
        self.editCommitted.emit()
        self.changed.emit()

    def duplicate_segment(self):
        index = self.selected_index()
        segments = self.segments()
        if index < 0 or index >= len(segments):
            return
        source = segments[index]
        clone = {
            "a": Vec2(float(source["a"].x), float(source["a"].y) + 8.0, source["a"].style),
            "b": Vec2(float(source["b"].x), float(source["b"].y) + 8.0, source["b"].style),
            "reflective": float(source.get("reflective", 0) or 0),
            "refractiveIndex": float(source.get("refractiveIndex", 1) or 1),
            "absorption": float(source.get("absorption", 0) or 0),
            "_explicit": set(source.get("_explicit", {"a", "b"})),
        }
        segments.insert(index + 1, clone)
        self.refresh()
        self.select(index + 1)
        self.editCommitted.emit()
        self.changed.emit()

    def remove_segment(self):
        index = self.selected_index()
        segments = self.segments()
        if index < 0 or index >= len(segments):
            return
        segments.pop(index)
        self.refresh()
        self.select(min(index, len(segments) - 1))
        self.editCommitted.emit()
        self.changed.emit()

    def flip_segment(self):
        index = self.selected_index()
        segments = self.segments()
        if index < 0 or index >= len(segments):
            return
        segment = segments[index]
        segment["a"], segment["b"] = segment["b"], segment["a"]
        self.refresh()
        self.select(index)
        self.editCommitted.emit()
        self.changed.emit()

    def _on_selection(self):
        if not self._updating:
            self.selectionChanged.emit(self.selected_index())
