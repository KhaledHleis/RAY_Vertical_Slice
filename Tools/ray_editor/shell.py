"""One window, two modes.

The level editor and the prefab editor already agree on everything that matters
-- the same `Project`, the same Lua reader/writer, the same `PrefabLibrary`
type -- so merging them is not a rewrite. It is a shell that hosts both
existing `MainWindow`s in a stack and makes three things true that were not
true when they were separate processes:

  * one prefab library, live. The prefab editor's document is the single owner.
    Switching back to the level re-points the level viewport at it, so a
    collider you just resized shows up under every instance in the level
    immediately -- before `definitions.lua` is even saved.
  * one keyboard. Both windows bind Ctrl+S, Ctrl+Z, Ctrl+O... Nested in one
    window those would be ambiguous shortcuts and neither would fire, so the
    duplicates are stripped from the children and re-bound here, dispatching to
    whichever mode is on screen.
  * two clicks to fix a prefab. Double-click a palette entry or a hierarchy row
    and you land in the prefab editor on that prefab; F1 puts you back where you
    were, selection intact.

Nothing in `level_editor/` or `prefab_editor/` is modified. Both still run
standalone.
"""

from __future__ import annotations

import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QKeySequence
from PyQt6.QtWidgets import (QLabel, QMainWindow, QMessageBox, QStackedWidget,
                             QToolBar, QWidget)

from level_editor.ui.main_window import MainWindow as LevelWindow
from prefab_editor.ui.main_window import MainWindow as PrefabWindow

LEVEL, PREFAB = 0, 1

# Commands both windows implement. The shell owns the shortcut; the children
# keep the menu/toolbar entry but lose the key binding.
UNIFIED = (
    ("&Save", "Ctrl+S", "save_file"),
    ("&Open...", "Ctrl+O", "open_file"),
    ("&Reload", "Ctrl+R", "reload_file"),
    ("&Undo", "Ctrl+Z", "undo"),
    ("&Redo", "Ctrl+Shift+Z", "redo"),
    ("Run &checks", "Ctrl+L", "run_lint"),
    ("&Preview Lua", None, "preview_lua"),
)


class UnifiedWindow(QMainWindow):
    def __init__(self, project, level_path=None, parent=None):
        super().__init__(parent)
        self.project = project
        self.setWindowTitle("RAY editor")
        self.resize(1520, 950)

        self.level = LevelWindow(project, level_path)
        self.prefabs = PrefabWindow(project)

        self.stack = QStackedWidget()
        self.stack.addWidget(self.level)
        self.stack.addWidget(self.prefabs)
        self.setCentralWidget(self.stack)

        self._tame_child_shortcuts()
        self._build_toolbar()
        self._wire_cross_navigation()

        self.status_label = QLabel("")
        self.statusBar().addPermanentWidget(self.status_label)

        self._sync_library_into_level()
        self.set_mode(LEVEL)

        # Dirty flags live inside two documents that mutate through a dozen
        # paths. Polling twice a second is cheaper to maintain than hooking
        # every one of them, and nobody can perceive the lag.
        self._ticker = QTimer(self)
        self._ticker.timeout.connect(self._refresh_status)
        self._ticker.start(500)

    # -- construction ------------------------------------------------------

    def _tame_child_shortcuts(self):
        """Strip duplicated bindings, scope what remains to its own mode."""
        taken = {QKeySequence(s).toString() for _, s, _ in UNIFIED if s}
        taken.add(QKeySequence("Ctrl+Q").toString())
        for window in (self.level, self.prefabs):
            for action in window.findChildren(QAction):
                if action.shortcut().toString() in taken:
                    action.setShortcut(QKeySequence())
                action.setShortcutContext(
                    Qt.ShortcutContext.WidgetWithChildrenShortcut)
                # The level editor's File > Quit closes the child, which would
                # only hide a page of the stack.
                if action.text().replace("&", "") == "Quit":
                    try:
                        action.triggered.disconnect()
                    except TypeError:
                        pass
                    action.triggered.connect(self.close)

    def _build_toolbar(self):
        bar = QToolBar("Mode")
        bar.setMovable(False)
        self.addToolBar(bar)

        self.level_action = self._mode_action(bar, "Level  (F1)", LEVEL, "F1")
        self.prefab_action = self._mode_action(bar, "Prefabs  (F2)", PREFAB, "F2")
        bar.addSeparator()

        self.edit_prefab_action = self._add(
            bar, "Edit this prefab", self.edit_selected_prefab, "Ctrl+E",
            "Open the selected object's prefab in the prefab editor")
        self.place_action = self._add(
            bar, "Place in level", self.place_current_prefab, "Ctrl+Shift+E",
            "Go back to the level with this prefab armed for placement")

        spacer = QWidget()
        spacer.setSizePolicy(spacer.sizePolicy().horizontalPolicy().Expanding,
                             spacer.sizePolicy().verticalPolicy().Preferred)
        bar.addWidget(spacer)

        # Shortcut-only, no visible entry: the children already show these in
        # their own menus and toolbars.
        for label, shortcut, method in UNIFIED:
            if shortcut:
                self._add(None, label, lambda _=False, m=method: self._dispatch(m),
                          shortcut)
        self._add(None, "Quit", self.close, "Ctrl+Q")

    def _mode_action(self, bar, text, mode, shortcut):
        action = QAction(text, self)
        action.setCheckable(True)
        action.setShortcut(QKeySequence(shortcut))
        action.triggered.connect(lambda _=False, m=mode: self.set_mode(m))
        bar.addAction(action)
        return action

    def _add(self, bar, text, slot, shortcut=None, tip=None):
        action = QAction(text, self)
        if shortcut:
            action.setShortcut(QKeySequence(shortcut))
        if tip:
            action.setToolTip(tip)
        action.triggered.connect(slot)
        if bar is not None:
            bar.addAction(action)
        else:
            self.addAction(action)
        return action

    def _wire_cross_navigation(self):
        self.level.palette.itemDoubleClicked.connect(
            lambda item: self.edit_prefab(item.text()))
        self.level.hierarchy.itemDoubleClicked.connect(self._on_hierarchy_double)
        self.prefabs.prefab_list.itemDoubleClicked.connect(
            lambda _item: self.place_current_prefab())

    # -- modes -------------------------------------------------------------

    def set_mode(self, mode):
        # Unconditional: an undo in prefab mode swaps the library object out
        # from under the level even when the mode never changed.
        if mode == LEVEL:
            self._sync_library_into_level()

        self.stack.setCurrentIndex(mode)
        self.level_action.setChecked(mode == LEVEL)
        self.prefab_action.setChecked(mode == PREFAB)
        self.edit_prefab_action.setEnabled(mode == LEVEL)
        self.place_action.setEnabled(mode == PREFAB)

        # Child shortcuts are widget-scoped, so the active page must hold focus
        # or Del, F, Ctrl+D and friends go nowhere.
        focus = (self.level.viewport if mode == LEVEL else self.prefabs.viewport)
        focus.setFocus(Qt.FocusReason.OtherFocusReason)
        self._refresh_status()

    def _dispatch(self, method):
        target = self.level if self.stack.currentIndex() == LEVEL else self.prefabs
        getattr(target, method)()

    # -- the shared library ------------------------------------------------

    def _sync_library_into_level(self):
        """Point the level at the prefab editor's live library.

        Undo in the prefab editor replaces `document.library` wholesale with a
        deep copy, so the level cannot just hold a reference once and forget --
        it has to be re-pointed on every switch.
        """
        library = self.prefabs.document.library
        if library is None:
            return

        self.level.library = library
        self.level.document.library = library
        self.level.viewport.set_library(library)
        self.level.refresh_palette()

        level = self.level.document.level
        self.level.inspector.set_context(self.project, level, library)
        self.level.inspector.set_object(self.level.viewport.selected())
        self.level.viewport.update()

    # -- cross navigation --------------------------------------------------

    def edit_prefab(self, name):
        if not name:
            return
        items = self.prefabs.prefab_list.findItems(
            name, Qt.MatchFlag.MatchExactly)
        if not items:
            QMessageBox.information(
                self, "Unknown prefab",
                f"`{name}` is not in definitions.lua.\n\n"
                "The level references a prefab the library does not define -- "
                "Run checks (Ctrl+L) in level mode lists these.")
            return
        self.prefabs.prefab_list.setCurrentItem(items[0])
        self.set_mode(PREFAB)
        self.statusBar().showMessage(f"Editing prefab {name} - F1 goes back", 5000)

    def edit_selected_prefab(self):
        obj = self.level.viewport.selected()
        name = getattr(obj, "prefab", None)
        if not name:
            self.statusBar().showMessage(
                "Select an object in the level first", 3000)
            return
        self.edit_prefab(name)

    def place_current_prefab(self):
        prefab = self.prefabs.current_prefab()
        name = getattr(prefab, "name", None)
        self.set_mode(LEVEL)
        if not name:
            return
        items = self.level.palette.findItems(name, Qt.MatchFlag.MatchExactly)
        if items:
            self.level.palette.setCurrentItem(items[0])
        self.level.viewport.arm_placement(name)
        self.statusBar().showMessage(
            f"Click in the viewport to place {name} (Esc cancels)", 6000)

    def _on_hierarchy_double(self, item, _column):
        obj = item.data(0, Qt.ItemDataRole.UserRole)
        self.edit_prefab(getattr(obj, "prefab", None))

    # -- status ------------------------------------------------------------

    def _refresh_status(self):
        level_doc, prefab_doc = self.level.document, self.prefabs.document
        # `modified` re-serialises both documents; a value the writer chokes on
        # must not take the whole window down every half second.
        try:
            level_dirty, prefab_dirty = level_doc.modified, prefab_doc.modified
        except (ValueError, TypeError) as error:
            self.status_label.setText(f"cannot serialise: {error}")
            return
        level_name = (os.path.basename(level_doc.path) if level_doc.path
                      else "untitled level")
        prefab_name = (os.path.basename(prefab_doc.path) if prefab_doc.path
                       else "definitions.lua")
        level_mark = "*" if level_dirty else ""
        prefab_mark = "*" if prefab_dirty else ""

        mode = "level" if self.stack.currentIndex() == LEVEL else "prefabs"
        self.setWindowTitle(
            f"RAY editor [{mode}] - {level_name}{level_mark} - "
            f"{prefab_name}{prefab_mark}")
        self.status_label.setText(
            f"level {level_name}{level_mark}   |   prefabs {prefab_name}{prefab_mark}")

    # -- shutdown ----------------------------------------------------------

    def closeEvent(self, event):
        if not self.level._confirm_discard():
            event.ignore()
            return

        if self.prefabs.document.modified:
            answer = QMessageBox.question(
                self, "Unsaved prefabs",
                "definitions.lua has unsaved changes. Save before closing?",
                QMessageBox.StandardButton.Save
                | QMessageBox.StandardButton.Discard
                | QMessageBox.StandardButton.Cancel)
            if answer == QMessageBox.StandardButton.Cancel:
                event.ignore()
                return
            if answer == QMessageBox.StandardButton.Save:
                self.prefabs.save_file()
        event.accept()
