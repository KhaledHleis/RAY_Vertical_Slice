"""The right-hand panel: one card per component, built entirely from the schema.

Component order is meaningful -- `Prefab.Instantiate` attaches in array order and
some components read their siblings during `OnAttach` (GodrayRenderer looks up
its LightSource that way) -- so the cards expose explicit move up/down controls
rather than sorting themselves.
"""

from __future__ import annotations

from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import (QComboBox, QFormLayout, QFrame, QHBoxLayout,
                             QLabel, QMenu, QPushButton, QScrollArea,
                             QSizePolicy, QToolButton, QVBoxLayout, QWidget)

from ..model import schema
from ..model.library import Component
from .fields import build_field
from .segments import SegmentTable

CARD_STYLE = """
QFrame#card {
    background: #2b2b33;
    border: 1px solid #3a3a45;
    border-radius: 5px;
}
QLabel#cardTitle { font-weight: bold; }
QLabel#cardDoc { color: #8a8a99; font-size: 11px; }
QLabel#blocked { color: #e08a6a; font-size: 11px; }
"""


class ComponentCard(QFrame):
    modelChanged = pyqtSignal()
    editStarted = pyqtSignal()
    removeRequested = pyqtSignal(object)
    moveRequested = pyqtSignal(object, int)
    segmentSelected = pyqtSignal(int)

    def __init__(self, component, project=None, parent=None):
        super().__init__(parent)
        self.setObjectName("card")
        self.component = component
        self.project = project
        self.widgets = {}
        self.segment_table = None

        spec = component.spec()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 6, 8, 8)
        layout.setSpacing(4)

        header = QHBoxLayout()
        title = QLabel(component.type)
        title.setObjectName("cardTitle")
        header.addWidget(title)
        header.addStretch(1)
        for text, tip, delta in (("^", "Move earlier in the attach order", -1),
                                 ("v", "Move later in the attach order", 1)):
            button = QToolButton()
            button.setText(text)
            button.setToolTip(tip)
            button.clicked.connect(lambda _c=False, d=delta: self.moveRequested.emit(self.component, d))
            header.addWidget(button)
        remove = QToolButton()
        remove.setText("x")
        remove.setToolTip("Remove this component")
        remove.clicked.connect(lambda: self.removeRequested.emit(self.component))
        header.addWidget(remove)
        layout.addLayout(header)

        if spec is None:
            layout.addWidget(_warning(f"Unknown component type {component.type!r}."))
            return

        if spec.doc:
            doc = QLabel(spec.doc)
            doc.setObjectName("cardDoc")
            doc.setWordWrap(True)
            layout.addWidget(doc)

        if not spec.allowed_in_prefab:
            layout.addWidget(_warning(spec.reason))

        form = QFormLayout()
        form.setContentsMargins(0, 4, 0, 0)
        form.setSpacing(4)
        form.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)

        for field in spec.fields:
            if field.kind == schema.SEGMENTS:
                continue
            widget = build_field(field, project)
            if widget is None:
                continue
            widget.set_value(component.args.get(field.name))
            widget.valueChanged.connect(
                lambda value, f=field: self._on_value(f, value))
            widget.editingCommitted.connect(self.editStarted.emit)
            label = QLabel(field.display_label())
            if field.tooltip:
                label.setToolTip(field.tooltip)
            form.addRow(label, widget)
            self.widgets[field.name] = (field, widget, label)

        layout.addLayout(form)

        if any(f.kind == schema.SEGMENTS for f in spec.fields):
            self.segment_table = SegmentTable()
            self.segment_table.set_component(component)
            self.segment_table.changed.connect(self.modelChanged.emit)
            self.segment_table.editCommitted.connect(self.editStarted.emit)
            self.segment_table.selectionChanged.connect(self.segmentSelected.emit)
            layout.addWidget(self.segment_table)

        self.refresh_visibility()

    def _on_value(self, field, value):
        self.component.set(field.name, value)
        self.refresh_visibility()
        self.modelChanged.emit()

    def refresh_visibility(self):
        for name, (field, widget, label) in self.widgets.items():
            visible = field.is_visible(self.component.args)
            widget.setVisible(visible)
            label.setVisible(visible)

    def reload_values(self):
        for name, (field, widget, _label) in self.widgets.items():
            widget.set_value(self.component.args.get(field.name))
        if self.segment_table is not None:
            self.segment_table.set_component(self.component)
        self.refresh_visibility()


def _warning(text):
    label = QLabel(text)
    label.setObjectName("blocked")
    label.setWordWrap(True)
    return label


class Inspector(QWidget):
    modelChanged = pyqtSignal()
    editStarted = pyqtSignal()
    structureChanged = pyqtSignal()
    segmentSelected = pyqtSignal(int)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setStyleSheet(CARD_STYLE)
        self.prefab = None
        self.project = None
        self.cards = []

        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(6)

        add_row = QHBoxLayout()
        self.add_combo = QComboBox()
        self.add_combo.setToolTip("Component types that may live inside a prefab")
        add_row.addWidget(self.add_combo, 1)
        self.add_button = QPushButton("Add component")
        self.add_button.clicked.connect(self._add_component)
        add_row.addWidget(self.add_button)
        outer.addLayout(add_row)

        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.container = QWidget()
        self.container_layout = QVBoxLayout(self.container)
        self.container_layout.setContentsMargins(0, 0, 6, 0)
        self.container_layout.setSpacing(8)
        self.container_layout.addStretch(1)
        self.scroll.setWidget(self.container)
        outer.addWidget(self.scroll, 1)

    def set_project(self, project):
        self.project = project

    def set_prefab(self, prefab):
        self.prefab = prefab
        self.rebuild()

    def rebuild(self):
        for card in self.cards:
            card.setParent(None)
            card.deleteLater()
        self.cards = []

        self._refresh_add_combo()

        if self.prefab is None:
            return

        for component in self.prefab.components:
            card = ComponentCard(component, self.project)
            card.modelChanged.connect(self.modelChanged.emit)
            card.editStarted.connect(self.editStarted.emit)
            card.removeRequested.connect(self._remove_component)
            card.moveRequested.connect(self._move_component)
            card.segmentSelected.connect(self.segmentSelected.emit)
            self.container_layout.insertWidget(self.container_layout.count() - 1, card)
            self.cards.append(card)

    def reload_values(self):
        for card in self.cards:
            card.reload_values()

    def _refresh_add_combo(self):
        self.add_combo.clear()
        existing = set(self.prefab.component_types()) if self.prefab else set()
        available = [name for name in schema.prefab_component_types()
                     if name not in existing]
        self.add_combo.addItems(available)
        self.add_combo.setEnabled(bool(available))
        self.add_button.setEnabled(bool(available))
        if not available and self.prefab is not None:
            self.add_combo.addItem("(every component already added)")

    def _add_component(self):
        if self.prefab is None:
            return
        type_name = self.add_combo.currentText()
        if type_name not in schema.COMPONENTS:
            return
        self.editStarted.emit()
        self.prefab.components.append(Component.create(type_name))
        self.structureChanged.emit()

    def _remove_component(self, component):
        if self.prefab is None or component not in self.prefab.components:
            return
        self.editStarted.emit()
        self.prefab.components.remove(component)
        self.structureChanged.emit()

    def _move_component(self, component, delta):
        if self.prefab is None:
            return
        components = self.prefab.components
        index = components.index(component)
        target = index + delta
        if target < 0 or target >= len(components):
            return
        self.editStarted.emit()
        components[index], components[target] = components[target], components[index]
        self.structureChanged.emit()
