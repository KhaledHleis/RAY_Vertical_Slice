"""Widget factory. Every editor in the inspector is built from a schema Field.

Nothing here knows about specific components -- add a Field to `schema.py` and
the matching widget appears. `editingCommitted` fires once when a value settles,
which is what the document uses to push an undo snapshot.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDoubleSpinBox,
                             QFileDialog, QHBoxLayout, QLabel, QLineEdit,
                             QPushButton, QSpinBox, QToolButton, QVBoxLayout,
                             QWidget)

from ..luaio.types import Vec2
from ..model import schema


class FieldWidget(QWidget):
    """Base class: emits `valueChanged` while editing, `editingCommitted` after."""

    valueChanged = pyqtSignal(object)
    editingCommitted = pyqtSignal()

    def __init__(self, field, parent=None):
        super().__init__(parent)
        self.field = field
        self._updating = False
        if field.tooltip:
            self.setToolTip(field.tooltip)

    def set_value(self, value):
        raise NotImplementedError

    def value(self):
        raise NotImplementedError

    def _emit(self, value):
        if not self._updating:
            self.valueChanged.emit(value)


def _spinbox(field, integer=False):
    """A spin box honouring the schema's bounds. QSpinBox rejects float bounds."""
    if integer:
        box = QSpinBox()
        low = int(field.minimum) if field.minimum is not None else -2_147_483_647
        high = int(field.maximum) if field.maximum is not None else 2_147_483_647
    else:
        box = QDoubleSpinBox()
        box.setDecimals(field.decimals)
        box.setSingleStep(field.step)
        low = float(field.minimum) if field.minimum is not None else -1e9
        high = float(field.maximum) if field.maximum is not None else 1e9

    box.setRange(low, high)
    if field.suffix:
        box.setSuffix(field.suffix)
    box.setKeyboardTracking(False)
    return box


class NumberField(FieldWidget):
    def __init__(self, field, integer=False, parent=None):
        super().__init__(field, parent)
        self.integer = integer
        self.box = _spinbox(field, integer)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.box)
        self.box.valueChanged.connect(lambda v: self._emit(int(v) if integer else float(v)))
        self.box.editingFinished.connect(self.editingCommitted.emit)

    def set_value(self, value):
        self._updating = True
        if value is None:
            value = self.field.default if self.field.default is not None else 0
        self.box.setValue(int(value) if self.integer else float(value))
        self._updating = False

    def value(self):
        return int(self.box.value()) if self.integer else float(self.box.value())


class OptionalNumberField(FieldWidget):
    """A number that can be genuinely unset.

    `frameWidth`, `frameHeight` and `radius` have no `or <default>` fallback in
    the engine -- absent means absent. A plain spin box cannot express that: it
    would clamp None to the minimum and make an unset field look configured.
    """

    def __init__(self, field, integer=False, parent=None):
        super().__init__(field, parent)
        self.integer = integer
        self.enabled_box = QCheckBox()
        self.enabled_box.setToolTip("Unchecked leaves this argument out entirely")
        self.box = _spinbox(field, integer)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.addWidget(self.enabled_box)
        layout.addWidget(self.box, 1)

        self.enabled_box.toggled.connect(self._on_toggled)
        self.box.valueChanged.connect(lambda _v: self._emit(self.value()))
        self.box.editingFinished.connect(self.editingCommitted.emit)

    def _on_toggled(self, state):
        self.box.setEnabled(bool(state))
        self._emit(self.value())
        if not self._updating:
            self.editingCommitted.emit()

    def set_value(self, value):
        self._updating = True
        has_value = value is not None
        self.enabled_box.setChecked(has_value)
        self.box.setEnabled(has_value)
        if has_value:
            self.box.setValue(int(value) if self.integer else float(value))
        self._updating = False

    def value(self):
        if not self.enabled_box.isChecked():
            return None
        return int(self.box.value()) if self.integer else float(self.box.value())


class BooleanField(FieldWidget):
    def __init__(self, field, parent=None):
        super().__init__(field, parent)
        self.box = QCheckBox()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.box)
        layout.addStretch(1)
        self.box.toggled.connect(self._on_toggled)

    def _on_toggled(self, state):
        self._emit(bool(state))
        if not self._updating:
            self.editingCommitted.emit()

    def set_value(self, value):
        self._updating = True
        self.box.setChecked(bool(value))
        self._updating = False

    def value(self):
        return self.box.isChecked()


class EnumField(FieldWidget):
    def __init__(self, field, parent=None):
        super().__init__(field, parent)
        self.box = QComboBox()
        self.box.addItems(field.options or [])
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.box)
        self.box.currentTextChanged.connect(self._on_changed)

    def _on_changed(self, text):
        self._emit(text)
        if not self._updating:
            self.editingCommitted.emit()

    def set_value(self, value):
        self._updating = True
        index = self.box.findText(str(value))
        self.box.setCurrentIndex(max(0, index))
        self._updating = False

    def value(self):
        return self.box.currentText()


class StringField(FieldWidget):
    def __init__(self, field, parent=None):
        super().__init__(field, parent)
        self.edit = QLineEdit()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.edit)
        self.edit.textChanged.connect(self._emit)
        self.edit.editingFinished.connect(self.editingCommitted.emit)

    def set_value(self, value):
        self._updating = True
        self.edit.setText("" if value is None else str(value))
        self._updating = False

    def value(self):
        return self.edit.text()


class PathField(FieldWidget):
    """A project-relative asset path, with a picker and a known-paths dropdown."""

    def __init__(self, field, project=None, parent=None):
        super().__init__(field, parent)
        self.project = project
        self.combo = QComboBox()
        self.combo.setEditable(True)
        if project is not None:
            self.combo.addItems([""] + project.sprite_paths())
        browse = QToolButton()
        browse.setText("...")
        browse.setToolTip("Browse for an image inside the project")
        browse.clicked.connect(self._browse)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.combo, 1)
        layout.addWidget(browse)

        self.combo.currentTextChanged.connect(self._on_changed)

    def _on_changed(self, text):
        self._emit(text or None)
        if not self._updating:
            self.editingCommitted.emit()

    def _browse(self):
        start = self.project.resources_path if self.project else os.getcwd()
        path, _ = QFileDialog.getOpenFileName(
            self, "Choose a sprite", start, "Images (*.png *.jpg *.jpeg *.bmp)")
        if not path:
            return
        if self.project is not None:
            try:
                path = os.path.relpath(path, self.project.root).replace(os.sep, "/")
            except ValueError:
                pass
        self.combo.setCurrentText(path)

    def set_value(self, value):
        self._updating = True
        self.combo.setCurrentText("" if value is None else str(value))
        self._updating = False

    def value(self):
        return self.combo.currentText() or None


class Vec2Field(FieldWidget):
    def __init__(self, field, parent=None):
        super().__init__(field, parent)
        self.x_box = _spinbox(field)
        self.y_box = _spinbox(field)
        self._style = None

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        for label, box in (("x", self.x_box), ("y", self.y_box)):
            caption = QLabel(label)
            caption.setStyleSheet("color: #888;")
            layout.addWidget(caption)
            layout.addWidget(box, 1)
            box.valueChanged.connect(lambda _v: self._emit(self.value()))
            box.editingFinished.connect(self.editingCommitted.emit)

    def set_value(self, value):
        self._updating = True
        if isinstance(value, Vec2):
            self._style = value.style
            self.x_box.setValue(float(value.x))
            self.y_box.setValue(float(value.y))
        else:
            self.x_box.setValue(0.0)
            self.y_box.setValue(0.0)
        self._updating = False

    def value(self):
        return Vec2(float(self.x_box.value()), float(self.y_box.value()), self._style)


class ColorField(FieldWidget):
    def __init__(self, field, parent=None):
        super().__init__(field, parent)
        self.channels = []
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(3)

        self.swatch = QPushButton()
        self.swatch.setFixedWidth(30)
        self.swatch.clicked.connect(self._pick)
        layout.addWidget(self.swatch)

        for name in ("r", "g", "b", "a"):
            box = QDoubleSpinBox()
            box.setRange(0.0, 1.0)
            box.setSingleStep(0.05)
            box.setDecimals(3)
            box.setKeyboardTracking(False)
            box.setToolTip(name)
            box.valueChanged.connect(lambda _v: self._on_changed())
            box.editingFinished.connect(self.editingCommitted.emit)
            self.channels.append(box)
            layout.addWidget(box, 1)

    def _on_changed(self):
        self._update_swatch()
        self._emit(self.value())

    def _update_swatch(self):
        r, g, b, _a = (c.value() for c in self.channels)
        color = QColor.fromRgbF(r, g, b)
        self.swatch.setStyleSheet(f"background-color: {color.name()};")

    def _pick(self):
        r, g, b, a = (c.value() for c in self.channels)
        chosen = QColorDialog.getColor(
            QColor.fromRgbF(r, g, b, a), self, "Sprite tint",
            QColorDialog.ColorDialogOption.ShowAlphaChannel)
        if not chosen.isValid():
            return
        for box, value in zip(self.channels, chosen.getRgbF()):
            box.setValue(value)
        self.editingCommitted.emit()

    def set_value(self, value):
        self._updating = True
        channels = list(value or [1.0, 1.0, 1.0, 1.0])
        while len(channels) < 4:
            channels.append(1.0)
        for box, channel in zip(self.channels, channels[:4]):
            box.setValue(float(channel))
        self._update_swatch()
        self._updating = False

    def value(self):
        return [float(box.value()) for box in self.channels]


def build_field(field, project=None):
    kind = field.kind
    if kind == schema.NUMBER:
        if field.optional:
            return OptionalNumberField(field)
        return NumberField(field)
    if kind == schema.INTEGER:
        if field.optional:
            return OptionalNumberField(field, integer=True)
        return NumberField(field, integer=True)
    if kind == schema.BOOLEAN:
        return BooleanField(field)
    if kind == schema.ENUM:
        return EnumField(field)
    if kind == schema.PATH:
        return PathField(field, project)
    if kind == schema.VEC2:
        return Vec2Field(field)
    if kind == schema.COLOR:
        return ColorField(field)
    if kind == schema.STRING:
        return StringField(field)
    return None
