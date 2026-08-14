"""The right-hand panel: transform, per-component overrides, extra components.

The central idea is the difference between a *default* and an *override*. Every
field shows the value the engine would end up using, but a field the level file
does not touch is drawn muted and reads straight from the prefab -- change the
prefab later and this object follows. Touch it and it turns bold, gains a revert
arrow, and from then on the level file pins it.

Segments are deliberately read-only here. Editing a light surface is a prefab
decision that should apply everywhere the prefab is used; doing it per instance
would silently fork the geometry of a mirror into seven slightly different
mirrors, which is exactly the failure mode a prefab system exists to prevent.
"""

from __future__ import annotations

import math

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import (QComboBox, QDoubleSpinBox, QFormLayout, QFrame,
                             QHBoxLayout, QLabel, QLineEdit, QPushButton,
                             QScrollArea, QToolButton, QVBoxLayout, QWidget)

from ..model import level as level_model
from ..model import schema
from .fields import build_field

CARD_STYLE = """
QFrame#card {
    background: #2b2b33;
    border: 1px solid #3a3a45;
    border-radius: 5px;
}
QLabel#cardTitle { font-weight: bold; }
QLabel#cardDoc { color: #8a8a99; font-size: 11px; }
QLabel#muted { color: #8a8a99; }
QLabel#warn { color: #e08a6a; font-size: 11px; }
QLabel#overridden { color: #f0b45a; font-weight: bold; }
"""


class TransformCard(QFrame):
    modelChanged = pyqtSignal()
    editStarted = pyqtSignal()
    structureChanged = pyqtSignal()

    def __init__(self, obj, level, library, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.obj = obj
        self.level = level
        self.library = library
        self._updating = False

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        title = QLabel("Object")
        title.setObjectName("cardTitle")
        layout.addWidget(title)

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)

        self.prefab_box = QComboBox()
        names = library.names() if library else []
        if obj.prefab not in names:
            names = [obj.prefab] + names
        self.prefab_box.addItems(names)
        self.prefab_box.setCurrentText(obj.prefab)
        self.prefab_box.currentTextChanged.connect(self._on_prefab)
        form.addRow("Prefab", self.prefab_box)

        self.id_edit = QLineEdit(obj.id or "")
        self.id_edit.setPlaceholderText("optional -- needed only for joints")
        self.id_edit.editingFinished.connect(self._on_id)
        form.addRow("Id", self.id_edit)

        row = QHBoxLayout()
        self.x_spin = _coord_spin("x ")
        self.y_spin = _coord_spin("y ")
        self.x_spin.setValue(obj.x)
        self.y_spin.setValue(obj.y)
        self.x_spin.valueChanged.connect(self._on_position)
        self.y_spin.valueChanged.connect(self._on_position)
        row.addWidget(self.x_spin)
        row.addWidget(self.y_spin)
        holder = QWidget()
        holder.setLayout(row)
        row.setContentsMargins(0, 0, 0, 0)
        form.addRow("Position", holder)

        self.rotation_spin = QDoubleSpinBox()
        self.rotation_spin.setRange(-3600.0, 3600.0)
        self.rotation_spin.setDecimals(2)
        self.rotation_spin.setSingleStep(15.0)
        self.rotation_spin.setSuffix(" deg")
        self.rotation_spin.setValue(math.degrees(obj.angle()))
        self.rotation_spin.valueChanged.connect(self._on_rotation)
        form.addRow("Rotation", self.rotation_spin)

        layout.addLayout(form)

        orphans = level_model.orphan_overrides(obj, library)
        if orphans:
            layout.addWidget(_warning(
                "Overrides for " + ", ".join(orphans) + " are ignored: prefab "
                f"'{obj.prefab}' does not declare them."))

    def refresh(self):
        self._updating = True
        self.x_spin.setValue(self.obj.x)
        self.y_spin.setValue(self.obj.y)
        self.rotation_spin.setValue(math.degrees(self.obj.angle()))
        self._updating = False

    def _on_prefab(self, name):
        if self._updating or name == self.obj.prefab:
            return
        self.editStarted.emit()
        self.obj.prefab = name
        self.structureChanged.emit()

    def _on_id(self):
        text = self.id_edit.text().strip() or None
        if text == self.obj.id:
            return
        if text and self.level is not None:
            clash = self.level.find_by_id(text)
            if clash is not None and clash is not self.obj:
                self.id_edit.setText(self.obj.id or "")
                return
        self.editStarted.emit()
        self.obj.id = text
        self.structureChanged.emit()

    def _on_position(self):
        if self._updating:
            return
        self.obj.move_to(round(self.x_spin.value(), 4),
                         round(self.y_spin.value(), 4))
        self.modelChanged.emit()

    def _on_rotation(self, degrees):
        if self._updating:
            return
        self.obj.set_angle(round(math.radians(degrees), 6),
                           keep_zero=self.obj.rotation is not None)
        self.modelChanged.emit()


class ComponentCard(QFrame):
    """One prefab component, with an override state per field."""

    modelChanged = pyqtSignal()
    editStarted = pyqtSignal()

    def __init__(self, obj, component, project=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.obj = obj
        self.component = component       # the *prefab's* component
        self.project = project
        self.rows = {}

        spec = component.spec()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(component.type)
        title.setObjectName("cardTitle")
        header.addWidget(title)
        header.addStretch(1)
        self.count_label = QLabel()
        self.count_label.setObjectName("muted")
        header.addWidget(self.count_label)
        layout.addLayout(header)

        if spec is None:
            layout.addWidget(_warning(f"Unknown component type {component.type!r}."))
            return

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for field in spec.fields:
            if field.kind == schema.SEGMENTS:
                count = len(component.get("segments") or [])
                note = QLabel(f"{count} segment(s) -- edit in the prefab editor")
                note.setObjectName("muted")
                form.addRow("Segments", note)
                continue

            if field.kind == schema.TILES:
                # Deliberately not editable here. A grid is painted, not typed,
                # and a text field holding a few hundred integers is a way to
                # corrupt a map rather than a way to fix one.
                tiles = self.obj.overrides.get(component.type, {}).get(field.name)
                if tiles is None:
                    tiles = component.get(field.name) or []
                painted = sum(1 for t in tiles if t)
                note = QLabel(f"{painted} of {len(tiles)} cells painted "
                              "-- paint in the Tiles panel")
                note.setObjectName("muted")
                form.addRow("Tiles", note)
                continue

            widget = build_field(field, project)
            if widget is None:
                continue
            widget.set_value(self._effective(field))
            widget.valueChanged.connect(
                lambda value, f=field: self._on_value(f, value))
            widget.editingCommitted.connect(self.editStarted.emit)

            label = QLabel(field.display_label())
            if field.tooltip:
                label.setToolTip(field.tooltip)

            revert = QToolButton()
            revert.setText("\u21ba")
            revert.setAutoRaise(True)
            revert.setFixedWidth(20)
            revert.setToolTip("Revert to the prefab value")
            revert.clicked.connect(lambda _c=False, f=field: self._revert(f))

            holder = QWidget()
            row = QHBoxLayout(holder)
            row.setContentsMargins(0, 0, 0, 0)
            row.setSpacing(3)
            # The revert arrow sits on the left, against the label: a wide
            # field (a Vec2 pair, a colour) can push the right edge of the row
            # past the panel, and the one control you must always be able to
            # reach is the one that undoes an override.
            row.addWidget(revert)
            row.addWidget(widget, 1)

            form.addRow(label, holder)
            self.rows[field.name] = (field, widget, label, revert, holder)

        layout.addLayout(form)
        self.refresh_state()

    def _effective(self, field):
        if self.obj.is_overridden(self.component.type, field.name):
            return self.obj.overrides[self.component.type][field.name]
        return self.component.args.get(field.name)

    def _on_value(self, field, value):
        prefab_value = self.component.args.get(field.name)
        if _same(value, prefab_value):
            self.obj.clear_override(self.component.type, field.name)
        else:
            self.obj.override(self.component.type, field.name, value)
        self.refresh_state()
        self.modelChanged.emit()

    def _revert(self, field):
        if not self.obj.is_overridden(self.component.type, field.name):
            return
        self.editStarted.emit()
        self.obj.clear_override(self.component.type, field.name)
        field_widget = self.rows[field.name][1]
        field_widget.set_value(self.component.args.get(field.name))
        self.refresh_state()
        self.modelChanged.emit()

    def refresh_state(self):
        overridden = 0
        args = self._visible_args()
        for name, (field, widget, label, revert, holder) in self.rows.items():
            is_override = self.obj.is_overridden(self.component.type, name)
            overridden += int(is_override)
            label.setStyleSheet("color: #f0b45a; font-weight: bold;"
                                if is_override else "")
            revert.setEnabled(is_override)
            visible = field.is_visible(args)
            holder.setVisible(visible)
            label.setVisible(visible)
        self.count_label.setText(f"{overridden} override(s)" if overridden else "")

    def _visible_args(self):
        args = dict(self.component.args)
        args.update(self.obj.overrides.get(self.component.type, {}))
        return args


class ExtraComponentCard(QFrame):
    """An entry in extraComponents -- currently only HingeJoint is useful."""

    modelChanged = pyqtSignal()
    editStarted = pyqtSignal()
    structureChanged = pyqtSignal()

    def __init__(self, obj, extra, level, project=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.obj = obj
        self.extra = extra
        self.level = level

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(f"{extra.type}  (extra)")
        title.setObjectName("cardTitle")
        header.addWidget(title)
        header.addStretch(1)
        remove = QToolButton()
        remove.setText("x")
        remove.setToolTip("Remove this component from the object")
        remove.clicked.connect(self._remove)
        header.addWidget(remove)
        layout.addLayout(header)

        spec = schema.spec_for(extra.type)
        if spec is not None and spec.doc:
            doc = QLabel(spec.doc)
            doc.setObjectName("cardDoc")
            doc.setWordWrap(True)
            layout.addWidget(doc)

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        if extra.type == "HingeJoint":
            self.target_box = QComboBox()
            self.target_box.addItem("")
            for candidate in level.ids():
                if candidate != obj.id:
                    self.target_box.addItem(candidate)
            current = extra.args.get("connectedObjectId") or ""
            if current and self.target_box.findText(current) < 0:
                self.target_box.addItem(current)
            self.target_box.setCurrentText(current)
            self.target_box.setToolTip(
                "Level.load swaps this id for the live object. The target needs "
                "an id and a RigidBody.")
            self.target_box.currentTextChanged.connect(self._on_target)
            form.addRow("Connected to", self.target_box)

        if spec is not None:
            for field in spec.fields:
                widget = build_field(field, project)
                if widget is None:
                    continue
                widget.set_value(extra.args.get(field.name, field.make_default()))
                widget.valueChanged.connect(
                    lambda value, f=field: self._on_value(f, value))
                widget.editingCommitted.connect(self.editStarted.emit)
                label = QLabel(field.display_label())
                if field.tooltip:
                    label.setToolTip(field.tooltip)
                form.addRow(label, widget)

        layout.addLayout(form)

        if extra.type == "HingeJoint":
            layout.addWidget(_muted(
                "The anchor is in world pixels, not object-local. Drag the pink "
                "crosshair in the viewport to place it."))

    def _on_target(self, text):
        self.editStarted.emit()
        if text:
            self.extra.args["connectedObjectId"] = text
        else:
            self.extra.args.pop("connectedObjectId", None)
        self.modelChanged.emit()

    def _on_value(self, field, value):
        self.extra.args[field.name] = value
        self.modelChanged.emit()

    def _remove(self):
        self.editStarted.emit()
        if self.extra in self.obj.extra_components:
            self.obj.extra_components.remove(self.extra)
        self.structureChanged.emit()


class Inspector(QScrollArea):
    modelChanged = pyqtSignal()
    editStarted = pyqtSignal()
    structureChanged = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(330)
        self.setStyleSheet(CARD_STYLE)
        self.project = None
        self.level = None
        self.library = None
        self.obj = None
        self._cards = []
        self._body = None
        self.set_object(None)

    def set_context(self, project, level, library):
        self.project = project
        self.level = level
        self.library = library

    def set_object(self, obj):
        self.obj = obj
        self._rebuild()

    def refresh(self):
        for card in self._cards:
            if isinstance(card, TransformCard):
                card.refresh()
            elif isinstance(card, ComponentCard):
                card.refresh_state()

    def _rebuild(self):
        self._cards = []
        body = QWidget()
        layout = QVBoxLayout(body)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(8)

        if self.obj is None:
            placeholder = QLabel("Select an object")
            placeholder.setObjectName("muted")
            placeholder.setAlignment(Qt.AlignmentFlag.AlignCenter)
            layout.addWidget(placeholder)
            layout.addStretch(1)
            self.setWidget(body)
            self._body = body
            return

        transform = TransformCard(self.obj, self.level, self.library)
        self._wire(transform)
        transform.structureChanged.connect(self.structureChanged.emit)
        layout.addWidget(transform)
        self._cards.append(transform)

        resolved_prefab = self.library.find(self.obj.prefab) if self.library else None
        if resolved_prefab is None:
            layout.addWidget(_warning(
                f"No prefab named '{self.obj.prefab}' in definitions.lua. "
                "Prefab.Instantiate asserts on this, so the level will not load."))
        else:
            for component in resolved_prefab.components:
                card = ComponentCard(self.obj, component, self.project)
                self._wire(card)
                layout.addWidget(card)
                self._cards.append(card)

        for extra in list(self.obj.extra_components):
            card = ExtraComponentCard(self.obj, extra, self.level, self.project)
            self._wire(card)
            card.structureChanged.connect(self.structureChanged.emit)
            layout.addWidget(card)
            self._cards.append(card)

        add_joint = QPushButton("Add HingeJoint")
        add_joint.setToolTip(
            "Joints live in the level, not the prefab: they need a live object "
            "reference that only Level.load can resolve.")
        add_joint.clicked.connect(self._add_hinge)
        layout.addWidget(add_joint)

        layout.addStretch(1)
        self.setWidget(body)
        self._body = body

    def _wire(self, card):
        card.modelChanged.connect(self.modelChanged.emit)
        card.editStarted.connect(self.editStarted.emit)

    def _add_hinge(self):
        from ..luaio.types import Vec2
        from ..model.level import ExtraComponent

        if self.obj is None:
            return
        self.editStarted.emit()
        anchor = Vec2(self.obj.x, self.obj.y, Vec2.TABLE)
        self.obj.extra_components.append(
            ExtraComponent("HingeJoint", {"anchor": anchor}))
        self.structureChanged.emit()


def _coord_spin(prefix):
    spin = QDoubleSpinBox()
    spin.setRange(-100000.0, 100000.0)
    spin.setDecimals(2)
    spin.setSingleStep(1.0)
    spin.setPrefix(prefix)
    spin.setMinimumWidth(74)
    return spin


def _warning(text):
    label = QLabel(text)
    label.setObjectName("warn")
    label.setWordWrap(True)
    label.setStyleSheet("color: #e08a6a; font-size: 11px;")
    return label


def _muted(text):
    label = QLabel(text)
    label.setObjectName("muted")
    label.setWordWrap(True)
    label.setStyleSheet("color: #8a8a99; font-size: 11px;")
    return label


def _same(left, right):
    from ..luaio.types import Vec2
    if isinstance(left, Vec2) and isinstance(right, Vec2):
        return left.as_tuple() == right.as_tuple()
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same(a, b)
                                               for a, b in zip(left, right))
    if left is None or right is None:
        return left is right
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) == bool(right)
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return abs(float(left) - float(right)) < 1e-9
    return left == right
