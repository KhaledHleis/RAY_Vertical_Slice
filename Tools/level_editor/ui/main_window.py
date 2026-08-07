"""Window layout and the actions that mutate the document.

Left: the prefab palette (click to arm, click in the viewport to place) above
the object list, which is the draw order and is reorderable because reordering
it is the only layering control the engine has.

Right: the inspector. Bottom: lint.

Every mutation goes through `_begin_edit`, which pushes an undo snapshot, and
ends with `_touch`, which marks the light solve dirty and refreshes the panels.
Keeping those two in one place is what stops undo from quietly missing a path.
"""

from __future__ import annotations

import difflib
import os
import subprocess
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QCheckBox, QComboBox, QDialog, QDialogButtonBox,
                             QDoubleSpinBox, QFileDialog, QHBoxLayout, QLabel,
                             QListWidget, QListWidgetItem, QMainWindow,
                             QMessageBox, QPlainTextEdit, QPushButton,
                             QSpinBox, QSplitter, QToolBar, QTreeWidget,
                             QTreeWidgetItem, QVBoxLayout, QWidget)

from ..luaio.types import LuaSyntaxError
from ..model.document import Document
from ..validate import lint
from .inspector import Inspector
from .viewport import Viewport

SEVERITY_COLOR = {lint.ERROR: "#e06a6a", lint.WARNING: "#e0b46a",
                  lint.INFO: "#8a9ae0"}


class DiffDialog(QDialog):
    def __init__(self, before, after, path, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Save {os.path.basename(path)}")
        self.resize(820, 560)

        diff = "\n".join(difflib.unified_diff(
            before.splitlines(), after.splitlines(),
            fromfile=f"{os.path.basename(path)} (on disk)",
            tofile=f"{os.path.basename(path)} (about to write)",
            lineterm="",
        )) or "No changes."

        view = QPlainTextEdit(diff)
        view.setReadOnly(True)
        view.setStyleSheet("font-family: monospace;")

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Save
                                   | QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(view)
        layout.addWidget(buttons)


class MainWindow(QMainWindow):
    def __init__(self, project=None, level_path=None, parent=None):
        super().__init__(parent)
        self.project = project
        self.document = Document()
        self.library = None
        self._suspend_selection = False

        self.setWindowTitle("RAY level editor")
        self.resize(1420, 900)

        self._build_ui()
        self._build_actions()

        if project is not None:
            self._load_library()
            target = level_path or (project.level_files()[0]
                                    if project.level_files() else None)
            if target:
                self.load_level(target)
            else:
                self.new_level()

    # -- construction ------------------------------------------------------

    def _build_ui(self):
        self.viewport = Viewport()
        self.viewport.set_project(self.project)
        self.viewport.modelChanged.connect(self._on_model_changed)
        self.viewport.editStarted.connect(self._begin_edit)
        self.viewport.selectionChanged.connect(self._on_viewport_selection)
        self.viewport.placementFinished.connect(self._clear_palette_selection)
        self.viewport.statusMessage.connect(
            lambda text: self.statusBar().showMessage(text, 4000))

        self.palette = QListWidget()
        self.palette.setToolTip(
            "Click a prefab, then click in the viewport to place it.\n"
            "Hold Shift while placing to keep placing.")
        self.palette.itemSelectionChanged.connect(self._on_palette_selected)

        self.hierarchy = QTreeWidget()
        self.hierarchy.setHeaderLabels(["#", "Object", "Prefab"])
        self.hierarchy.setColumnWidth(0, 30)
        self.hierarchy.setColumnWidth(1, 120)
        self.hierarchy.setRootIsDecorated(False)
        self.hierarchy.setSelectionMode(
            QTreeWidget.SelectionMode.ExtendedSelection)
        self.hierarchy.itemSelectionChanged.connect(self._on_hierarchy_selected)
        self.hierarchy.setToolTip(
            "Draw order: Scene:Draw walks this list with ipairs, so entries "
            "lower down paint on top.")

        order_row = QHBoxLayout()
        for text, tip, delta in (("Raise", "Draw later (on top)", 1),
                                 ("Lower", "Draw earlier (behind)", -1)):
            button = QPushButton(text)
            button.setToolTip(tip)
            button.clicked.connect(lambda _c=False, d=delta: self.reorder(d))
            order_row.addWidget(button)
        order_holder = QWidget()
        order_holder.setLayout(order_row)
        order_row.setContentsMargins(0, 0, 0, 0)

        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(6, 6, 6, 6)
        left_layout.setSpacing(4)
        left_layout.addWidget(QLabel("Prefabs"))
        left_layout.addWidget(self.palette, 2)
        left_layout.addWidget(QLabel("Objects (draw order)"))
        left_layout.addWidget(self.hierarchy, 3)
        left_layout.addWidget(order_holder)

        self.inspector = Inspector()
        self.inspector.modelChanged.connect(self._on_model_changed)
        self.inspector.editStarted.connect(self._begin_edit)
        self.inspector.structureChanged.connect(self._on_structure_changed)

        self.lint_tree = QTreeWidget()
        self.lint_tree.setHeaderLabels(["Severity", "Object", "Issue", "Why"])
        self.lint_tree.setRootIsDecorated(False)
        self.lint_tree.setColumnWidth(0, 70)
        self.lint_tree.setColumnWidth(1, 160)
        self.lint_tree.setColumnWidth(2, 420)
        self.lint_tree.itemActivated.connect(self._on_lint_activated)

        centre = QSplitter(Qt.Orientation.Vertical)
        centre.addWidget(self.viewport)
        centre.addWidget(self.lint_tree)
        centre.setSizes([680, 180])

        splitter = QSplitter(Qt.Orientation.Horizontal)
        splitter.addWidget(left)
        splitter.addWidget(centre)
        splitter.addWidget(self.inspector)
        splitter.setSizes([230, 780, 410])
        self.setCentralWidget(splitter)

        self._build_toolbar()
        self.statusBar().showMessage("Ready")

    def _build_toolbar(self):
        bar = QToolBar("View")
        bar.setMovable(False)
        self.addToolBar(bar)

        self.level_box = QComboBox()
        self.level_box.setMinimumWidth(160)
        self.level_box.setToolTip("Level files under Frontend/levels")
        self.level_box.activated.connect(self._on_level_chosen)
        bar.addWidget(QLabel(" Level "))
        bar.addWidget(self.level_box)
        bar.addSeparator()

        width, height = (self.project.screen_size() if self.project else (320, 240))
        self.width_spin = QSpinBox()
        self.width_spin.setRange(16, 4096)
        self.width_spin.setValue(width)
        self.height_spin = QSpinBox()
        self.height_spin.setRange(16, 4096)
        self.height_spin.setValue(height)
        for spin in (self.width_spin, self.height_spin):
            spin.setToolTip(
                "The frame the game actually renders. Read from "
                "Libraries/renderer/screen.lua; change it here to design "
                "against a different resolution.")
            spin.valueChanged.connect(self._on_screen_size)
        bar.addWidget(QLabel(" Screen "))
        bar.addWidget(self.width_spin)
        bar.addWidget(QLabel(" x "))
        bar.addWidget(self.height_spin)
        bar.addSeparator()

        self.snap_check = QCheckBox("Snap")
        self.snap_check.setChecked(True)
        self.snap_check.toggled.connect(self._on_snap_toggled)
        bar.addWidget(self.snap_check)

        self.snap_spin = QDoubleSpinBox()
        self.snap_spin.setRange(0.0, 64.0)
        self.snap_spin.setDecimals(2)
        self.snap_spin.setSingleStep(1.0)
        self.snap_spin.setValue(8.0)
        self.snap_spin.setSuffix(" px")
        self.snap_spin.valueChanged.connect(self._on_snap_step)
        bar.addWidget(self.snap_spin)
        bar.addSeparator()

        for label, attribute, default in (
                ("Sprites", "show_sprites", True),
                ("Bodies", "show_bodies", True),
                ("Segments", "show_segments", True),
                ("Light", "show_light", True),
                ("Godrays", "show_godrays", True),
                ("Joints", "show_joints", True),
                ("Labels", "show_labels", False),
                ("Grid", "show_grid", True),
                ("Frame", "show_screen_frame", True)):
            check = QCheckBox(label)
            check.setChecked(default)
            check.toggled.connect(
                lambda state, a=attribute: self._set_viewport_flag(a, state))
            bar.addWidget(check)

    def _build_actions(self):
        file_menu = self.menuBar().addMenu("&File")
        edit_menu = self.menuBar().addMenu("&Edit")
        view_menu = self.menuBar().addMenu("&View")

        def add(menu, text, slot, shortcut=None, tip=None):
            action = QAction(text, self)
            if shortcut:
                action.setShortcut(QKeySequence(shortcut))
            if tip:
                action.setStatusTip(tip)
            action.triggered.connect(slot)
            menu.addAction(action)
            return action

        add(file_menu, "&New level", self.new_level, "Ctrl+N")
        add(file_menu, "&Open...", self.open_file, "Ctrl+O")
        add(file_menu, "&Reload", self.reload_file, "Ctrl+R")
        file_menu.addSeparator()
        add(file_menu, "&Save", self.save_file, "Ctrl+S")
        add(file_menu, "Save &as...", self.save_file_as, "Ctrl+Shift+S")
        add(file_menu, "&Preview Lua", self.preview_lua)
        file_menu.addSeparator()
        add(file_menu, "&Play this level", self.play_level, "Ctrl+P",
            "Launch LOVE with this level")
        file_menu.addSeparator()
        add(file_menu, "&Quit", self.close, "Ctrl+Q")

        self.undo_action = add(edit_menu, "&Undo", self.undo, "Ctrl+Z")
        self.redo_action = add(edit_menu, "&Redo", self.redo, "Ctrl+Shift+Z")
        edit_menu.addSeparator()
        add(edit_menu, "&Duplicate", self.viewport.duplicate_selection, "Ctrl+D")
        add(edit_menu, "De&lete", self.viewport.delete_selection, "Del")
        edit_menu.addSeparator()
        add(edit_menu, "Select &all", self.select_all, "Ctrl+A")

        add(view_menu, "&Frame screen", self.viewport.frame_screen, "Ctrl+0")
        add(view_menu, "Frame &selection", self.viewport.frame_selection, "F")
        add(view_menu, "Run &checks", self.run_lint, "Ctrl+L")

        self._update_actions()

    # -- loading -----------------------------------------------------------

    def _load_library(self):
        try:
            self.library = Document.load_library(self.project.definitions_path)
        except (LuaSyntaxError, OSError, ValueError) as error:
            QMessageBox.critical(
                self, "definitions.lua",
                f"Could not read the prefab definitions:\n\n{error}\n\n"
                "The level editor can still open a level, but it cannot draw "
                "or validate anything without them.")
            self.library = None
            return
        self.viewport.set_library(self.library)
        self.refresh_palette()

    def refresh_palette(self):
        self.palette.clear()
        if self.library is None:
            return
        for name in self.library.names():
            item = QListWidgetItem(name)
            prefab = self.library.find(name)
            item.setToolTip(", ".join(prefab.component_types()) or "no components")
            self.palette.addItem(item)

    def refresh_level_box(self):
        self.level_box.blockSignals(True)
        self.level_box.clear()
        if self.project is not None:
            for path in self.project.level_files():
                self.level_box.addItem(os.path.basename(path), path)
        if self.document.path:
            index = self.level_box.findData(self.document.path)
            if index < 0:
                self.level_box.addItem(os.path.basename(self.document.path),
                                       self.document.path)
                index = self.level_box.count() - 1
            self.level_box.setCurrentIndex(index)
        self.level_box.blockSignals(False)

    def load_level(self, path):
        try:
            document = Document.load(path, self.library)
        except (LuaSyntaxError, OSError, ValueError) as error:
            QMessageBox.critical(self, "Open level",
                                 f"Could not read {os.path.basename(path)}:\n\n{error}")
            return False

        self.document = document
        self.viewport.set_level(document.level, self.library)
        self.inspector.set_context(self.project, document.level, self.library)
        self.inspector.set_object(None)
        self.refresh_level_box()
        self.refresh_hierarchy()
        self.viewport.frame_screen()
        self.run_lint()
        self._update_title()
        self.statusBar().showMessage(
            f"Loaded {os.path.basename(path)} -- "
            f"{len(document.level.objects)} objects", 5000)
        return True

    def new_level(self):
        self.document = Document(library=self.library)
        if self.project is not None:
            self.document.path = None
        self.viewport.set_level(self.document.level, self.library)
        self.inspector.set_context(self.project, self.document.level, self.library)
        self.inspector.set_object(None)
        self.refresh_hierarchy()
        self.viewport.frame_screen()
        self.run_lint()
        self._update_title()

    def open_file(self):
        start = self.project.levels_path if self.project else os.getcwd()
        path, _ = QFileDialog.getOpenFileName(self, "Open level", start,
                                              "Lua files (*.lua)")
        if path:
            self.load_level(path)

    def reload_file(self):
        if self.document.path:
            self._load_library()
            self.load_level(self.document.path)

    def save_file(self):
        if not self.document.path:
            return self.save_file_as()
        after = self.document.preview_text()
        before = self.document.saved_text()
        dialog = DiffDialog(before, after, self.document.path, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return False
        self.document.save()
        self._update_title()
        self.statusBar().showMessage(
            f"Saved {os.path.basename(self.document.path)} "
            f"(previous version kept as .bak)", 6000)
        return True

    def save_file_as(self):
        start = self.project.levels_path if self.project else os.getcwd()
        path, _ = QFileDialog.getSaveFileName(self, "Save level as",
                                              os.path.join(start, "level.lua"),
                                              "Lua files (*.lua)")
        if not path:
            return False
        self.document.save(path)
        self.refresh_level_box()
        self._update_title()
        self.statusBar().showMessage(f"Saved {os.path.basename(path)}", 5000)
        return True

    def preview_lua(self):
        dialog = QDialog(self)
        dialog.setWindowTitle("Level Lua")
        dialog.resize(760, 620)
        view = QPlainTextEdit(self.document.preview_text())
        view.setReadOnly(True)
        view.setStyleSheet("font-family: monospace;")
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        layout = QVBoxLayout(dialog)
        layout.addWidget(view)
        layout.addWidget(buttons)
        dialog.exec()

    def play_level(self):
        if self.project is None:
            return
        if self.document.modified or not self.document.path:
            QMessageBox.information(
                self, "Play level",
                "Save the level first -- LOVE reads it from disk.")
            return

        module = self.project.level_module(self.document.path)
        command, extra_env = self._love_command()
        if command is None:
            QMessageBox.warning(
                self, "Play level",
                "Could not find a LOVE binary. Looked for `love` on PATH and "
                "for runtime/love inside the project.")
            return

        if not self._main_lua_reads_env():
            answer = QMessageBox.question(
                self, "Play level",
                "main.lua currently hard-codes the level:\n\n"
                "    Level.load('Frontend.levels.demo', scene)\n\n"
                "To make this button open the level you are editing, change "
                "that line to:\n\n"
                "    Level.load(os.getenv('RAY_LEVEL') or "
                "'Frontend.levels.demo', scene)\n\n"
                "Launch anyway? It will open whichever level main.lua names.",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
            if answer != QMessageBox.StandardButton.Yes:
                return

        try:
            subprocess.Popen(command + [self.project.root],
                             cwd=self.project.root,
                             env=dict(os.environ, RAY_LEVEL=module, **extra_env))
        except OSError as error:
            QMessageBox.warning(self, "Play level", str(error))
            return

        self.statusBar().showMessage(f"Launched LOVE with RAY_LEVEL={module}", 8000)

    def _main_lua_reads_env(self):
        try:
            with open(self.project.path("main.lua"), encoding="utf-8") as handle:
                return "RAY_LEVEL" in handle.read()
        except OSError:
            return False

    def _love_command(self):
        """Prefer the system LOVE. `runtime/love` is the aarch64 handheld
        binary the deploy script bundles, which will not run on a desktop."""
        from shutil import which
        found = which("love")
        if found:
            return [found], {}
        candidate = self.project.path("runtime", "love")
        if os.path.exists(candidate) and os.access(candidate, os.X_OK):
            libs = self.project.path("runtime", "libs")
            return [candidate], {
                "LD_LIBRARY_PATH": libs + os.pathsep
                + os.environ.get("LD_LIBRARY_PATH", "")
            }
        return None, {}

    # -- panels ------------------------------------------------------------

    def refresh_hierarchy(self):
        self._suspend_selection = True
        self.hierarchy.clear()
        selected = set(id(o) for o in self.viewport.selection)
        for index, obj in enumerate(self.document.level.objects):
            item = QTreeWidgetItem([str(index), obj.label(), obj.prefab])
            item.setData(0, Qt.ItemDataRole.UserRole, obj)
            if obj.override_count():
                item.setText(1, f"{obj.label()}  *")
                item.setToolTip(1, f"{obj.override_count()} component override(s)")
            self.hierarchy.addTopLevelItem(item)
            if id(obj) in selected:
                item.setSelected(True)
        self._suspend_selection = False

    def run_lint(self):
        self.lint_tree.clear()
        if self.document.level is None:
            return
        issues = lint.lint_level(self.document.level, self.library, self.project)
        for issue in issues:
            item = QTreeWidgetItem([issue.severity, issue.location(),
                                    issue.message, issue.hint or ""])
            item.setData(0, Qt.ItemDataRole.UserRole, issue.obj)
            self.lint_tree.addTopLevelItem(item)

        errors = sum(1 for i in issues if i.severity == lint.ERROR)
        warnings = sum(1 for i in issues if i.severity == lint.WARNING)
        if not issues:
            self.statusBar().showMessage("Checks: all clear", 4000)
        else:
            self.statusBar().showMessage(
                f"Checks: {errors} error(s), {warnings} warning(s)", 4000)

    def _on_lint_activated(self, item, _column):
        obj = item.data(0, Qt.ItemDataRole.UserRole)
        if obj is not None:
            self.viewport.set_selection([obj])
            self.viewport.frame_selection()

    # -- selection ---------------------------------------------------------

    def _on_palette_selected(self):
        items = self.palette.selectedItems()
        self.viewport.arm_placement(items[0].text() if items else None)
        if items:
            self.statusBar().showMessage(
                f"Click in the viewport to place {items[0].text()} "
                "(Shift-click to keep placing, Esc to cancel)", 8000)

    def _clear_palette_selection(self):
        self.palette.clearSelection()

    def _on_viewport_selection(self):
        self.inspector.set_object(self.viewport.selected())
        self._suspend_selection = True
        selected = set(id(o) for o in self.viewport.selection)
        for index in range(self.hierarchy.topLevelItemCount()):
            item = self.hierarchy.topLevelItem(index)
            obj = item.data(0, Qt.ItemDataRole.UserRole)
            item.setSelected(id(obj) in selected)
        self._suspend_selection = False

    def _on_hierarchy_selected(self):
        if self._suspend_selection:
            return
        objects = [item.data(0, Qt.ItemDataRole.UserRole)
                   for item in self.hierarchy.selectedItems()]
        self.viewport.set_selection([o for o in objects if o is not None])

    def select_all(self):
        if self.document.level is not None:
            self.viewport.set_selection(list(self.document.level.objects))

    def reorder(self, delta):
        obj = self.viewport.selected()
        if obj is None:
            return
        index = self.document.level.index_of(obj)
        self._begin_edit()
        if self.document.level.move(obj, index + delta):
            self._on_structure_changed()

    # -- edit plumbing -----------------------------------------------------

    def _begin_edit(self):
        self.document.begin_edit()
        self._update_actions()

    def _touch(self):
        self.viewport.mark_light_dirty()
        self.viewport.update()
        self._update_title()
        self._update_actions()

    def _on_model_changed(self):
        if self.viewport.is_interacting():
            # Mid-drag: keep the cheap feedback (viewport, position spinners)
            # and defer the rest to the release, which fires this again.
            self.inspector.refresh()
            self.viewport.update()
            return
        self.refresh_hierarchy()
        self.inspector.refresh()
        self.run_lint()
        self._touch()

    def _on_structure_changed(self):
        self.viewport.level = self.document.level
        self.refresh_hierarchy()
        self.inspector.set_context(self.project, self.document.level, self.library)
        self.inspector.set_object(self.viewport.selected())
        self.run_lint()
        self._touch()

    def undo(self):
        if not self.document.undo():
            return
        self._after_history()

    def redo(self):
        if not self.document.redo():
            return
        self._after_history()

    def _after_history(self):
        self.viewport.set_level(self.document.level, self.library)
        self.inspector.set_context(self.project, self.document.level, self.library)
        self.inspector.set_object(None)
        self.refresh_hierarchy()
        self.run_lint()
        self._touch()

    def _update_actions(self):
        self.undo_action.setEnabled(self.document.can_undo)
        self.redo_action.setEnabled(self.document.can_redo)

    def _update_title(self):
        name = os.path.basename(self.document.path) if self.document.path \
            else "untitled"
        mark = " *" if self.document.modified else ""
        self.setWindowTitle(f"RAY level editor -- {name}{mark}")

    # -- toolbar handlers --------------------------------------------------

    def _on_level_chosen(self, index):
        path = self.level_box.itemData(index)
        if path and path != self.document.path:
            if not self._confirm_discard():
                self.refresh_level_box()
                return
            self.load_level(path)

    def _on_screen_size(self):
        self.viewport.set_screen_size(self.width_spin.value(),
                                      self.height_spin.value())
        self.run_lint()

    def _on_snap_toggled(self, state):
        self.viewport.snap_enabled = state
        self.viewport.update()

    def _on_snap_step(self, value):
        self.viewport.snap_step = value
        self.viewport.update()

    def _set_viewport_flag(self, attribute, state):
        setattr(self.viewport, attribute, state)
        self.viewport.update()

    # -- shutdown ----------------------------------------------------------

    def _confirm_discard(self):
        if not self.document.modified:
            return True
        answer = QMessageBox.question(
            self, "Unsaved changes",
            "This level has unsaved changes. Save before continuing?",
            QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard
            | QMessageBox.StandardButton.Cancel)
        if answer == QMessageBox.StandardButton.Save:
            return self.save_file()
        return answer == QMessageBox.StandardButton.Discard

    def closeEvent(self, event):
        if self._confirm_discard():
            event.accept()
        else:
            event.ignore()
