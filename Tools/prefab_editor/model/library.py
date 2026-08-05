"""In-memory model of `definitions.lua`.

`explicit` on a Component is what keeps diffs small. A key that was present in
the source file stays in the output even if it happens to equal the default, so
opening a file and saving it without edits produces no semantic churn. Keys the
editor adds are only written when they actually differ from the engine default.
"""

from __future__ import annotations

import copy

from ..luaio.types import LuaTable, Num, Vec2
from . import schema


class Component:
    def __init__(self, type_name, args=None, comment=None, explicit=None):
        self.type = type_name
        self.args = args if args is not None else {}
        self.comment = comment
        self.explicit = set(explicit) if explicit else set()

    @classmethod
    def create(cls, type_name):
        """A brand-new component holding only the engine defaults."""
        spec = schema.spec_for(type_name)
        args = {}
        if spec:
            for f in spec.fields:
                value = f.make_default()
                if value is not None:
                    args[f.name] = value
        return cls(type_name, args)

    def spec(self):
        return schema.spec_for(self.type)

    def get(self, name, default=None):
        value = self.args.get(name, None)
        if value is None:
            spec = self.spec()
            if spec:
                f = spec.field_map().get(name)
                if f is not None:
                    return f.make_default() if default is None else default
            return default
        return value

    def set(self, name, value):
        self.args[name] = value
        self.explicit.add(name)

    def clone(self):
        return Component(self.type, copy.deepcopy(self.args), self.comment, set(self.explicit))

    def __repr__(self):
        return f"Component({self.type})"


class Prefab:
    def __init__(self, name, components=None, comment=None):
        self.name = name
        self.components = components if components is not None else []
        self.comment = comment

    def component_types(self):
        return [c.type for c in self.components]

    def find(self, type_name):
        for component in self.components:
            if component.type == type_name:
                return component
        return None

    def has(self, type_name):
        return self.find(type_name) is not None

    def clone(self, new_name=None):
        return Prefab(
            new_name or self.name,
            [c.clone() for c in self.components],
            self.comment,
        )

    def __repr__(self):
        return f"Prefab({self.name!r}, {self.component_types()})"


class PrefabLibrary:
    def __init__(self, prefabs=None, header=None):
        self.prefabs = prefabs if prefabs is not None else []
        self.header = header

    def names(self):
        return [p.name for p in self.prefabs]

    def find(self, name):
        for prefab in self.prefabs:
            if prefab.name == name:
                return prefab
        return None

    def unique_name(self, base):
        if self.find(base) is None:
            return base
        index = 2
        while self.find(f"{base}{index}") is not None:
            index += 1
        return f"{base}{index}"

    def add(self, prefab, index=None):
        if index is None:
            self.prefabs.append(prefab)
        else:
            self.prefabs.insert(index, prefab)

    def remove(self, name):
        prefab = self.find(name)
        if prefab is not None:
            self.prefabs.remove(prefab)
        return prefab


# ---------------------------------------------------------------------------
# LuaTable -> model
# ---------------------------------------------------------------------------


def _convert_value(value, field_spec):
    """Coerce a parsed Lua value into what the schema says the field holds."""
    if field_spec is None:
        return value

    kind = field_spec.kind

    if kind == schema.VEC2:
        if isinstance(value, Vec2):
            return value
        if isinstance(value, LuaTable):
            return Vec2(value.get("x", Num(0.0)), value.get("y", Num(0.0)), Vec2.TABLE)
        return field_spec.make_default()

    if kind == schema.COLOR:
        if isinstance(value, LuaTable):
            channels = list(value.array)
            while len(channels) < 4:
                channels.append(Num(1.0))
            return channels[:4]
        return field_spec.make_default()

    if kind == schema.SEGMENTS:
        return _convert_segments(value)

    if kind == schema.BOOLEAN:
        return bool(value)

    return value


def _convert_segments(value):
    segments = []
    if not isinstance(value, LuaTable):
        return segments

    field_map = {f.name: f for f in schema.SEGMENT_FIELDS}
    for entry in value.array:
        if not isinstance(entry, LuaTable):
            continue
        segment = {}
        explicit = set()
        for key, raw in entry.items():
            segment[key] = _convert_value(raw, field_map.get(key))
            explicit.add(key)
        for f in schema.SEGMENT_FIELDS:
            segment.setdefault(f.name, f.make_default())
        segment["_explicit"] = explicit
        segments.append(segment)
    return segments


def component_from_table(table, comment=None):
    type_name = table.get("type")
    if not isinstance(type_name, str):
        raise ValueError("component entry is missing a string `type`")

    spec = schema.spec_for(type_name)
    field_map = spec.field_map() if spec else {}

    args = {}
    explicit = set()
    raw_args = table.get("args")
    if isinstance(raw_args, LuaTable):
        for key, raw in raw_args.items():
            args[key] = _convert_value(raw, field_map.get(key))
            explicit.add(key)

    # Fill in anything the schema knows about but the file omitted.
    if spec:
        for f in spec.fields:
            args.setdefault(f.name, f.make_default())

    return Component(type_name, args, comment, explicit)


def prefab_from_table(name, table, comment=None):
    components = []
    raw_components = table.get("components")
    if isinstance(raw_components, LuaTable):
        for index, entry in enumerate(raw_components.array):
            if isinstance(entry, LuaTable):
                components.append(
                    component_from_table(entry, raw_components.comments.get(index))
                )
    return Prefab(name, components, comment)


def library_from_table(table):
    if not isinstance(table, LuaTable):
        raise ValueError("definitions.lua must return a table")

    prefabs = []
    for name, entry in table.items():
        if not isinstance(entry, LuaTable):
            continue
        prefabs.append(prefab_from_table(name, entry, table.comments.get(name)))
    return PrefabLibrary(prefabs)
