"""Application shell: prefab list, viewport, inspector, lint dock, save flow."""

from __future__ import annotations

import difflib
import math
import os

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QColor, QKeySequence
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFileDialog, QHBoxLayout,
                             QInputDialog, QLabel, QListWidget, QMainWindow,
                             QMessageBox, QPlainTextEdit, QPushButton, QSlider,
                             QSplitter, QToolBar, QTreeWidget, QTreeWidgetItem,
                             QVBoxLayout, QWidget)

from ..luaio.types import LuaSyntaxError
from ..model import generators
from ..model.document import Document
from ..model.library import Prefab, PrefabLibrary
from ..model.project import Project
from ..validate import lint
from .inspector import Inspector
from .viewport import Viewport

SEVERITY_COLORS = {
    lint.ERROR: QColor(235, 100, 90),
    lint.WARNING: QColor(230, 185, 80),
    lint.INFO: QColor(130, 175, 235),
}


class DiffDialog(QDialog):
    """Shows what saving would change before it touches the file."""

    def __init__(self, before, after, path, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Review changes")
        self.resize(900, 620)

        layout = QVBoxLayout(self)
        diff = list(difflib.unified_diff(
            before.splitlines(), after.splitlines(),
            fromfile=f"{os.path.basename(path)} (on disk)",
            tofile=f"{os.path.basename(path)} (about to write)",
            lineterm="",
        ))

        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setStyleSheet("font-family: monospace;")
        view.setPlainText("\n".join(diff) if diff else "No changes.")
        layout.addWidget(view)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self, project=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("RAY prefab editor")
        self.resize(1500, 900)

        self.project = project
        self.document = Document()

        self._build_ui()
        self._build_actions()

        if project is not None:
            self.load_definitions(project.definitions_path)

    # -- construction ------------------------------------------------------

    def _build_ui(self):
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left: prefab list
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 6, 3, 6)
        left_layout.addWidget(QLabel("Prefabs"))
        self.prefab_list = QListWidget()
        self.prefab_list.currentTextChanged.connect(self._on_prefab_selected)
        left_layout.addWidget(self.prefab_list, 1)

        buttons = QHBoxLayout()
        for label, slot in (("New", self.new_prefab),
                            ("Duplicate", self.duplicate_prefab),
                            ("Rename", self.rename_prefab),
                            ("Delete", self.delete_prefab)):
            button = QPushButton(label)
            button.clicked.connect(slot)
            buttons.addWidget(button)
        left_layout.addLayout(buttons)
        left.setMinimumWidth(215)
        left.setMaximumWidth(340)
        splitter.addWidget(left)

        # Centre: viewport plus its controls
        centre = QWidget()
        centre_layout = QVBoxLayout(centre)
        centre_layout.setContentsMargins(3, 6, 3, 6)
        centre_layout.setSpacing(4)

        self.viewport = Viewport()
        self.viewport.modelChanged.connect(self._on_model_changed)
        self.viewport.editStarted.connect(self.document.begin_edit)
        self.viewport.selectionChanged.connect(self._on_segment_selected)

        controls = QHBoxLayout()
        controls.setSpacing(8)

        controls.addWidget(QLabel("Preview rotation"))
        self.rotation_slider = QSlider(Qt.Orientation.Horizontal)
        self.rotation_slider.setRange(-180, 180)
        self.rotation_slider.setFixedWidth(180)
        self.rotation_slider.valueChanged.connect(self._on_rotation)
        controls.addWidget(self.rotation_slider)
        self.rotation_label = QLabel("0deg")
        self.rotation_label.setFixedWidth(48)
        controls.addWidget(self.rotation_label)

        reset = QPushButton("Reset")
        reset.setToolTip("Back to 0 degrees")
        reset.clicked.connect(lambda: self.rotation_slider.setValue(0))
        controls.addWidget(reset)

        controls.addSpacing(12)
        controls.addWidget(QLabel("Snap"))
        self.snap_box = QDoubleSpinBox()
        self.snap_box.setRange(0.0, 64.0)
        self.snap_box.setDecimals(2)
        self.snap_box.setValue(1.0)
        self.snap_box.setToolTip("0 disables snapping. Pixel art usually wants 1 or 8.")
        self.snap_box.valueChanged.connect(self._on_snap)
        controls.addWidget(self.snap_box)

        controls.addStretch(1)
        frame = QPushButton("Frame (F)")
        frame.setToolTip("Zoom to fit the prefab and the light probe")
        frame.clicked.connect(self.viewport.frame_content)
        controls.addWidget(frame)
        centre_layout.addLayout(controls)

        toggles = QHBoxLayout()
        toggles.setSpacing(10)
        toggles.addWidget(QLabel("Show"))
        for label, attribute, default in (
            ("Sprite", "show_sprite", True),
            ("Collider", "show_body", True),
            ("Segments", "show_segments", True),
            ("Light", "show_light", True),
            ("Godrays", "show_godrays", True),
            ("Probe", "probe_enabled", True),
            ("Grid", "show_grid", True),
        ):
            box = QCheckBox(label)
            box.setChecked(default)
            box.toggled.connect(
                lambda state, a=attribute: self._set_viewport_flag(a, state))
            toggles.addWidget(box)
        toggles.addStretch(1)
        centre_layout.addLayout(toggles)

        centre_layout.addWidget(self.viewport, 1)

        generator_row = QHBoxLayout()
        generator_row.setSpacing(6)
        fit = QPushButton("Fit collider to sprite")
        fit.setToolTip("Resize the RigidBody rectangle to the drawn sprite footprint")
        fit.clicked.connect(self.fit_collider)
        generator_row.addWidget(fit)

        generator_row.addWidget(QLabel("Segments from collider:"))
        self.face_combo = QComboBox()
        self.face_combo.addItems(["all four edges", "top edge only"])
        generator_row.addWidget(self.face_combo)
        self.material_combo = QComboBox()
        self.material_combo.addItems(["mirror", "absorber", "glass"])
        generator_row.addWidget(self.material_combo)
        generate = QPushButton("Generate")
        generate.clicked.connect(self.generate_segments)
        generator_row.addWidget(generate)
        generator_row.addStretch(1)
        centre_layout.addLayout(generator_row)

        centre.setMinimumWidth(460)
        splitter.addWidget(centre)

        # Right: inspector
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(3, 6, 6, 6)
        right_layout.addWidget(QLabel("Components"))
        self.inspector = Inspector()
        self.inspector.modelChanged.connect(self._on_model_changed)
        self.inspector.editStarted.connect(self.document.begin_edit)
        self.inspector.structureChanged.connect(self._on_structure_changed)
        self.inspector.segmentSelected.connect(self._on_segment_selected)
        right_layout.addWidget(self.inspector, 1)
        right.setMinimumWidth(400)
        splitter.addWidget(right)

        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)
        splitter.setSizes([210, 760, 480])
        self.setCentralWidget(splitter)

        # Bottom: lint
        self.lint_tree = QTreeWidget()
        self.lint_tree.setColumnCount(3)
        self.lint_tree.setHeaderLabels(["Where", "Problem", "Suggestion"])
        self.lint_tree.setRootIsDecorated(False)
        self.lint_tree.itemDoubleClicked.connect(self._on_lint_activated)

        from PyQt6.QtWidgets import QDockWidget
        dock = QDockWidget("Checks", self)
        dock.setWidget(self.lint_tree)
        dock.setAllowedAreas(Qt.DockWidgetArea.BottomDockWidgetArea)
        self.addDockWidget(Qt.DockWidgetArea.BottomDockWidgetArea, dock)
        self.lint_dock = dock

        self.statusBar().showMessage("Ready")

    def _build_actions(self):
        toolbar = QToolBar("Main")
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        def add(text, slot, shortcut=None, tip=""):
            action = QAction(text, self)
            action.triggered.connect(slot)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            if tip:
                action.setToolTip(tip)
            toolbar.addAction(action)
            return action

        add("Open", self.open_file, "Ctrl+O", "Open a definitions.lua")
        self.save_action = add("Save", self.save_file, "Ctrl+S",
                               "Review the diff, then write the file")
        add("Reload", self.reload_file, "Ctrl+R", "Discard changes and re-read from disk")
        toolbar.addSeparator()
        self.undo_action = add("Undo", self.undo, "Ctrl+Z")
        self.redo_action = add("Redo", self.redo, "Ctrl+Shift+Z")
        toolbar.addSeparator()
        add("Preview Lua", self.preview_lua, tip="See the file that would be written")

    # -- file operations ---------------------------------------------------

    def load_definitions(self, path):
        try:
            self.document = Document.load(path)
        except LuaSyntaxError as error:
            QMessageBox.critical(
                self, "Cannot parse definitions.lua",
                f"{path}\n\n{error}\n\n"
                "The editor only understands the data subset (tables, numbers, "
                "strings, booleans, Vector.new and math.*). It refuses to load "
                "rather than risk destroying content it cannot represent.")
            return False

        self.viewport.editStarted.disconnect()
        self.viewport.editStarted.connect(self.document.begin_edit)
        self.inspector.editStarted.disconnect()
        self.inspector.editStarted.connect(self.document.begin_edit)

        if self.project is None:
            self.project = Project.discover(os.path.dirname(path))
        self.viewport.set_project(self.project)
        self.inspector.set_project(self.project)

        self.refresh_prefab_list()
        self.setWindowTitle(f"RAY prefab editor - {path}")
        self.statusBar().showMessage(
            f"Loaded {len(self.document.library.prefabs)} prefabs from {path}")
        return True

    def open_file(self):
        start = self.project.root if self.project else os.getcwd()
        path, _ = QFileDialog.getOpenFileName(
            self, "Open definitions.lua", start, "Lua (*.lua)")
        if path:
            self.load_definitions(path)

    def reload_file(self):
        if not self.document.path:
            return
        if self.document.modified:
            answer = QMessageBox.question(
                self, "Discard changes?",
                "Reloading throws away unsaved edits. Continue?")
            if answer != QMessageBox.StandardButton.Yes:
                return
        self.load_definitions(self.document.path)

    def save_file(self):
        if not self.document.path:
            path, _ = QFileDialog.getSaveFileName(
                self, "Save definitions.lua", os.getcwd(), "Lua (*.lua)")
            if not path:
                return
            self.document.path = path

        before = self.document.saved_text()
        after = self.document.preview_text()
        if before == after:
            self.statusBar().showMessage("No changes to save")
            return

        dialog = DiffDialog(before, after, self.document.path, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return

        self.document.save()
        self.statusBar().showMessage(
            f"Saved {self.document.path} (previous version kept as .bak)")

    def preview_lua(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Generated Lua")
        dialog.resize(880, 700)
        layout = QVBoxLayout(dialog)
        view = QPlainTextEdit()
        view.setReadOnly(True)
        view.setStyleSheet("font-family: monospace;")
        view.setPlainText(self.document.preview_text())
        layout.addWidget(view)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout.addWidget(buttons)
        dialog.exec()

    # -- prefab list -------------------------------------------------------

    def refresh_prefab_list(self, select=None):
        current = select or self.prefab_list.currentItem()
        current_name = current if isinstance(current, str) else (
            current.text() if current else None)

        self.prefab_list.blockSignals(True)
        self.prefab_list.clear()
        self.prefab_list.addItems(self.document.library.names())
        self.prefab_list.blockSignals(False)

        if current_name and current_name in self.document.library.names():
            items = self.prefab_list.findItems(current_name, Qt.MatchFlag.MatchExactly)
            if items:
                self.prefab_list.setCurrentItem(items[0])
        elif self.prefab_list.count():
            self.prefab_list.setCurrentRow(0)
        else:
            self._on_prefab_selected(None)

        self.run_lint()

    def current_prefab(self):
        item = self.prefab_list.currentItem()
        if item is None:
            return None
        return self.document.library.find(item.text())

    def _on_prefab_selected(self, name):
        prefab = self.document.library.find(name) if name else None
        self.viewport.set_prefab(prefab)
        self.inspector.set_prefab(prefab)
        if prefab is not None:
            self.viewport.frame_content()

    def new_prefab(self):
        name, ok = QInputDialog.getText(self, "New prefab", "Name:")
        if not ok or not name.strip():
            return
        name = self.document.library.unique_name(name.strip())
        self.document.begin_edit()
        self.document.library.add(Prefab(name))
        self.refresh_prefab_list(select=name)

    def duplicate_prefab(self):
        prefab = self.current_prefab()
        if prefab is None:
            return
        name = self.document.library.unique_name(prefab.name + "Copy")
        self.document.begin_edit()
        self.document.library.add(prefab.clone(name))
        self.refresh_prefab_list(select=name)

    def rename_prefab(self):
        prefab = self.current_prefab()
        if prefab is None:
            return
        name, ok = QInputDialog.getText(
            self, "Rename prefab", "Name:", text=prefab.name)
        if not ok or not name.strip() or name.strip() == prefab.name:
            return
        new_name = name.strip()
        if self.document.library.find(new_name):
            QMessageBox.warning(self, "Name taken",
                                f"A prefab called {new_name!r} already exists.")
            return
        old_name = prefab.name
        self.document.begin_edit()
        prefab.name = new_name
        self.refresh_prefab_list(select=new_name)
        self._warn_about_references(old_name, new_name)

    def _warn_about_references(self, old_name, new_name):
        """Levels reference prefabs by string; renaming breaks them silently."""
        if self.project is None:
            return
        levels_dir = self.project.path("Frontend", "levels")
        hits = []
        for dirpath, _dirs, files in os.walk(levels_dir):
            for filename in files:
                if not filename.endswith(".lua"):
                    continue
                full = os.path.join(dirpath, filename)
                try:
                    with open(full, encoding="utf-8") as handle:
                        text = handle.read()
                except OSError:
                    continue
                if f'"{old_name}"' in text or f"'{old_name}'" in text:
                    hits.append(os.path.relpath(full, self.project.root))
        if hits:
            QMessageBox.information(
                self, "Level references",
                f"{old_name!r} is still referenced by:\n\n" + "\n".join(hits) +
                f"\n\nUpdate those to {new_name!r} or Prefab.Instantiate will assert.")

    def delete_prefab(self):
        prefab = self.current_prefab()
        if prefab is None:
            return
        answer = QMessageBox.question(
            self, "Delete prefab", f"Delete {prefab.name!r}?")
        if answer != QMessageBox.StandardButton.Yes:
            return
        self.document.begin_edit()
        self.document.library.remove(prefab.name)
        self.refresh_prefab_list()

    # -- generators --------------------------------------------------------

    def fit_collider(self):
        prefab = self.current_prefab()
        if prefab is None:
            return
        self.document.begin_edit()
        ok, message = generators.fit_collider_to_sprite(prefab, self.project)
        if ok:
            self.inspector.reload_values()
            self._on_model_changed()
        else:
            self.document.undo()
        self.statusBar().showMessage(message)

    def generate_segments(self):
        prefab = self.current_prefab()
        if prefab is None:
            return
        material = self.material_combo.currentText()
        settings = {
            "mirror": dict(reflective=1.0, absorption=0.0, refractive_index=1.0),
            "absorber": dict(reflective=0.0, absorption=1.0, refractive_index=1.0),
            "glass": dict(reflective=0.0, absorption=0.0, refractive_index=1.5),
        }[material]
        faces = "top" if self.face_combo.currentIndex() == 1 else "all"

        self.document.begin_edit()
        ok, message = generators.segments_from_collider(prefab, faces=faces, **settings)
        if ok:
            self.inspector.rebuild()
            self._on_model_changed()
        else:
            self.document.undo()
        self.statusBar().showMessage(message)

    # -- reactions ---------------------------------------------------------

    def _set_viewport_flag(self, attribute, state):
        setattr(self.viewport, attribute, bool(state))
        self.viewport.update()

    def _on_rotation(self, degrees):
        self.viewport.preview_rotation = math.radians(degrees)
        self.rotation_label.setText(f"{degrees}deg")
        self.viewport.update()

    def _on_snap(self, value):
        self.viewport.snap_step = float(value)
        self.viewport.snap_enabled = value > 0
        self.viewport.update()

    def _on_model_changed(self):
        self.viewport.update()
        self.inspector.reload_values()
        self.run_lint()
        self._update_actions()

    def _on_structure_changed(self):
        self.inspector.rebuild()
        self.viewport.update()
        self.run_lint()
        self._update_actions()

    def _on_segment_selected(self, index):
        self.viewport.selected_segment = index if index is not None and index >= 0 else None
        self.viewport.update()

    def _update_actions(self):
        self.undo_action.setEnabled(self.document.can_undo)
        self.redo_action.setEnabled(self.document.can_redo)

    def undo(self):
        if self.document.undo():
            self.refresh_prefab_list()
            self.inspector.set_prefab(self.current_prefab())
            self.viewport.set_prefab(self.current_prefab())
            self.statusBar().showMessage("Undo")
        self._update_actions()

    def redo(self):
        if self.document.redo():
            self.refresh_prefab_list()
            self.inspector.set_prefab(self.current_prefab())
            self.viewport.set_prefab(self.current_prefab())
            self.statusBar().showMessage("Redo")
        self._update_actions()

    # -- lint --------------------------------------------------------------

    def run_lint(self):
        self.lint_tree.clear()
        issues = lint.lint_library(self.document.library, self.project)

        for issue in issues:
            item = QTreeWidgetItem([issue.location(), issue.message, issue.hint])
            color = SEVERITY_COLORS.get(issue.severity)
            if color:
                item.setForeground(0, color)
            item.setData(0, Qt.ItemDataRole.UserRole, issue.prefab)
            self.lint_tree.addTopLevelItem(item)

        for column in range(3):
            self.lint_tree.resizeColumnToContents(column)

        errors = sum(1 for i in issues if i.severity == lint.ERROR)
        warnings = sum(1 for i in issues if i.severity == lint.WARNING)
        self.lint_dock.setWindowTitle(
            f"Checks - {errors} error(s), {warnings} warning(s)"
            if issues else "Checks - all clear")

    def _on_lint_activated(self, item, _column):
        name = item.data(0, Qt.ItemDataRole.UserRole)
        if not name:
            return
        matches = self.prefab_list.findItems(name, Qt.MatchFlag.MatchExactly)
        if matches:
            self.prefab_list.setCurrentItem(matches[0])

    # -- close -------------------------------------------------------------

    def closeEvent(self, event):
        if self.document.modified:
            answer = QMessageBox.question(
                self, "Unsaved changes",
                "Save before closing?",
                QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save:
                self.save_file()
        event.accept()
