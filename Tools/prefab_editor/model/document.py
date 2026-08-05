"""Editing session state: the library, the file it came from, and undo history.

Undo is snapshot based rather than command based. `definitions.lua` is a few
kilobytes, so deep-copying the whole library per edit costs nothing measurable,
and it means every mutation path -- inspector field, gizmo drag, generator,
component reorder -- gets undo for free without each one having to implement a
command class correctly.
"""

from __future__ import annotations

import copy
import os

from ..luaio import reader, writer
from .library import PrefabLibrary, library_from_table

MAX_HISTORY = 200


class Document:
    def __init__(self, library=None, path=None):
        self.library = library if library is not None else PrefabLibrary()
        self.path = path
        self._undo = []
        self._redo = []
        self._saved_state = self._snapshot()

    # -- load / save -------------------------------------------------------

    @classmethod
    def load(cls, path):
        library = library_from_table(reader.parse_file(path))
        return cls(library, path)

    def save(self, path=None, make_backup=True):
        target = path or self.path
        if not target:
            raise ValueError("no path to save to")
        writer.write_file(self.library, target, make_backup=make_backup)
        self.path = target
        self._saved_state = self._snapshot()
        return target

    def preview_text(self):
        return writer.write_library(self.library)

    def saved_text(self):
        if self.path and os.path.exists(self.path):
            with open(self.path, encoding="utf-8") as handle:
                return handle.read()
        return ""

    # -- history -----------------------------------------------------------

    def _snapshot(self):
        return copy.deepcopy(self.library)

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
        self.library = self._undo.pop()
        return True

    def redo(self):
        if not self._redo:
            return False
        self._undo.append(self._snapshot())
        self.library = self._redo.pop()
        return True

    @property
    def can_undo(self):
        return bool(self._undo)

    @property
    def can_redo(self):
        return bool(self._redo)

    @property
    def modified(self):
        return writer.write_library(self.library) != writer.write_library(self._saved_state)
