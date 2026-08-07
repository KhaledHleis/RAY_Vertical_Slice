"""Editing session state: the level, the prefab library it draws from, and undo.

Undo is snapshot based, as in the prefab editor: a level file is a few kilobytes,
so deep-copying it per edit costs nothing measurable and every mutation path --
inspector field, viewport drag, reorder, delete -- gets undo for free.

The prefab library is loaded read-only. A level editor that could also rewrite
`definitions.lua` would be two tools wearing one coat, and changing a prefab
under a level you are mid-edit on is how you lose work.
"""

from __future__ import annotations

import copy
import os

from ..luaio import level_writer, reader
from .level import Level, level_from_table
from .library import PrefabLibrary, library_from_table

MAX_HISTORY = 200


class Document:
    def __init__(self, level=None, path=None, library=None):
        self.level = level if level is not None else Level()
        self.library = library if library is not None else PrefabLibrary()
        self.path = path
        self._undo = []
        self._redo = []
        self._saved_state = self._snapshot()

    # -- load / save -------------------------------------------------------

    @classmethod
    def load(cls, path, library=None):
        level = level_from_table(reader.parse_file(path))
        return cls(level, path, library)

    @staticmethod
    def load_library(path):
        return library_from_table(reader.parse_file(path))

    def save(self, path=None, make_backup=True):
        target = path or self.path
        if not target:
            raise ValueError("no path to save to")
        level_writer.write_file(self.level, target, make_backup=make_backup)
        self.path = target
        self._saved_state = self._snapshot()
        return target

    def preview_text(self):
        return level_writer.write_level(self.level)

    def saved_text(self):
        if self.path and os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as handle:
                return handle.read()
        return ""

    # -- history -----------------------------------------------------------

    def _snapshot(self):
        return copy.deepcopy(self.level)

    def begin_edit(self):
        """Record the current state so the edit that follows can be undone."""
        self._undo.append(self._snapshot())
        if len(self._undo) > MAX_HISTORY:
            self._undo.pop(0)
        self._redo.clear()

    def undo(self):
        if not self._undo:
            return False
        self._redo.append(self._snapshot())
        self.level = self._undo.pop()
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self.level = self._redo.pop()
        return True

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    @property
    def modified(self):
        return (level_writer.write_level(self.level)
                != level_writer.write_level(self._saved_state))
