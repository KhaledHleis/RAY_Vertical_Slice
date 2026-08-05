"""Locates the RAY project on disk and reads the few facts the editor needs.

Rather than hard-coding 64 for the physics scale or a fixed component list, both
are read back out of the engine source. If you change `World.PIXELS_PER_METER`
or register a new component, the editor follows without being edited.
"""

from __future__ import annotations

import os
import re

MARKERS = ("main.lua", "conf.lua", os.path.join("Libraries", "universal", "prefab.lua"))

DEFAULT_PIXELS_PER_METER = 64.0

_PPM_RE = re.compile(r"PIXELS_PER_METER\s*=\s*([0-9.]+)")
_REGISTRY_RE = re.compile(r"^\s*(\w+)\s*=\s*require\(", re.MULTILINE)


class Project:
    def __init__(self, root):
        self.root = os.path.abspath(root)

    # -- discovery ---------------------------------------------------------

    @classmethod
    def discover(cls, start=None):
        """Walk upwards from `start` looking for the project root."""
        current = os.path.abspath(start or os.getcwd())
        while True:
            if all(os.path.exists(os.path.join(current, m)) for m in MARKERS):
                return cls(current)
            parent = os.path.dirname(current)
            if parent == current:
                return None
            current = parent

    def path(self, *parts):
        return os.path.join(self.root, *parts)

    @property
    def definitions_path(self):
        return self.path("Frontend", "prefabs", "definitions.lua")

    @property
    def registry_path(self):
        return self.path("Libraries", "universal", "component_registry.lua")

    @property
    def resources_path(self):
        return self.path("Resources")

    # -- engine facts ------------------------------------------------------

    def pixels_per_meter(self):
        try:
            with open(self.path("Libraries", "physics", "world.lua"), encoding="utf-8") as f:
                match = _PPM_RE.search(f.read())
            if match:
                return float(match.group(1))
        except OSError:
            pass
        return DEFAULT_PIXELS_PER_METER

    def registered_components(self):
        """Component names present in component_registry.lua."""
        try:
            with open(self.registry_path, encoding="utf-8") as f:
                return set(_REGISTRY_RE.findall(f.read()))
        except OSError:
            return set()

    def sprite_paths(self):
        """Every image under Resources/, as project-relative posix paths."""
        found = []
        for dirpath, _dirnames, filenames in os.walk(self.resources_path):
            for name in sorted(filenames):
                if name.lower().endswith((".png", ".jpg", ".jpeg", ".bmp")):
                    absolute = os.path.join(dirpath, name)
                    found.append(os.path.relpath(absolute, self.root).replace(os.sep, "/"))
        return sorted(found)

    def resolve(self, relative):
        """Turn a project-relative asset path into an absolute one."""
        if not relative:
            return None
        return self.path(*str(relative).split("/"))

    def __repr__(self):
        return f"Project({self.root!r})"
