"""In-memory model of a level file such as `Frontend/levels/demo.lua`.

A level is a flat, ordered list of object entries. Order matters twice over:
`Scene:Draw` walks `self.objects` with `ipairs`, so the list index *is* the draw
order, and `Level.load` instantiates in the same order before resolving
`extraComponents` in a second pass.

The one idea worth stating up front is **override storage**. `Prefab.Instantiate`
merges `entry.components[Type]` over the prefab's own `args` key by key, so an
override that happens to equal the prefab value is a no-op that only makes the
level file noisier. `LevelObject.overrides` therefore holds *only* keys the
designer actually changed; reverting a field deletes the key rather than writing
the prefab value back. `resolve()` is the other half: it produces the effective
Prefab the engine would build, which is what the viewport draws, what the
raytracer traces, and what the inspector shows greyed-out defaults from.

Nested tables replace wholesale, matching `mergeArgs`: overriding
`SpriteRenderer.scale` replaces the whole `{x, y}`, it does not merge into it.
"""

from __future__ import annotations

import copy
import math

from ..luaio.types import LuaTable, Num, Vec2, num_src
from . import schema
from .library import Component, Prefab, _convert_value

# Keys `Level.load` reads off an entry. Anything else is carried through
# untouched so a hand-written field the editor does not understand survives.
KNOWN_KEYS = ("id", "prefab", "position", "rotation", "scale", "parent",
              "components", "extraComponents")


class ExtraComponent:
    """An entry in `extraComponents` -- a component added per-instance.

    Distinct from an override because it is *added* to the object rather than
    merged into a component the prefab already has, and because it is the only
    place cross-object references (`connectedObjectId`) are resolved.
    """

    def __init__(self, type_name, args=None, comment=None):
        self.type = type_name
        self.args = args if args is not None else {}
        self.comment = comment

    def spec(self):
        return schema.spec_for(self.type)

    def get(self, name, default=None):
        value = self.args.get(name)
        if value is None:
            spec = self.spec()
            if spec:
                field = spec.field_map().get(name)
                if field is not None:
                    return field.make_default() if default is None else default
            return default
        return value

    def set(self, name, value):
        self.args[name] = value

    def clone(self):
        return ExtraComponent(self.type, copy.deepcopy(self.args), self.comment)

    def __repr__(self):
        return f"ExtraComponent({self.type})"


class LevelObject:
    """One entry in the level array."""

    def __init__(self, prefab, position=None, rotation=None, object_id=None,
                 overrides=None, extra_components=None, comment=None, extra_keys=None,
                 key_comments=None, parent=None, scale=None):
        self.prefab = prefab
        # LOCAL to the parent when `parent` is set, exactly as Level.load reads
        # it. The world value is derived -- see `x`/`y` below.
        self.position = position if position is not None else Vec2(0.0, 0.0, Vec2.TABLE)
        self.rotation = rotation           # None means "absent from the file"
        self.scale = scale                 # None means "absent", i.e. 1
        self.parent = parent               # id of the parent entry, or None
        self.id = object_id
        # Set by Level.add / level_from_table. Needed to resolve `parent`,
        # which is an id rather than a reference so that the file stays the
        # source of truth and reordering entries cannot break a link.
        self.level = None
        self.overrides = overrides if overrides is not None else {}
        self.extra_components = extra_components if extra_components is not None else []
        self.comment = comment
        self.extra_keys = extra_keys if extra_keys is not None else {}
        # Comments the source attached to a specific key inside the entry, as
        # `demo.lua` does above `id = "mirror"`. Kept keyed so they stay with
        # the line they were written for.
        self.key_comments = key_comments if key_comments is not None else {}

    # -- overrides ---------------------------------------------------------

    def override(self, component_type, name, value):
        self.overrides.setdefault(component_type, {})[name] = value

    def clear_override(self, component_type, name):
        bucket = self.overrides.get(component_type)
        if not bucket:
            return
        bucket.pop(name, None)
        if not bucket:
            del self.overrides[component_type]

    def is_overridden(self, component_type, name):
        return name in self.overrides.get(component_type, {})

    def override_count(self):
        return sum(len(bucket) for bucket in self.overrides.values())

    # -- geometry ----------------------------------------------------------
    #
    # `position`, `rotation` and `scale` are stored LOCAL, because that is what
    # the file holds and what Level.load applies. `x`, `y`, `angle()` and
    # `world_scale()` are WORLD, because that is what the viewport draws and
    # what a drag gesture produces. Every existing call site in the viewport
    # therefore keeps working unchanged and becomes hierarchy-aware for free;
    # the conversion happens once, here.

    def parent_object(self):
        if not self.parent or self.level is None:
            return None
        found = self.level.find_by_id(self.parent)
        return found if found is not self else None

    def local_angle(self):
        return float(self.rotation) if self.rotation is not None else 0.0

    def local_scale(self):
        return float(self.scale) if self.scale is not None else 1.0

    def _chain(self):
        """This object and its ancestors, root last. Cycle-safe."""
        chain = []
        seen = set()
        node = self
        while node is not None and id(node) not in seen:
            seen.add(id(node))
            chain.append(node)
            node = node.parent_object()
        return chain

    def world(self):
        """(x, y, angle, scale) in world space."""
        wx = wy = 0.0
        wa = 0.0
        ws = 1.0
        for node in reversed(self._chain()):
            lx = float(node.position.x) * ws
            ly = float(node.position.y) * ws
            cos_a, sin_a = math.cos(wa), math.sin(wa)
            wx, wy = wx + lx * cos_a - ly * sin_a, wy + lx * sin_a + ly * cos_a
            wa += node.local_angle()
            ws *= node.local_scale()
        return wx, wy, wa, ws

    @property
    def x(self):
        return self.world()[0]

    @property
    def y(self):
        return self.world()[1]

    def world_scale(self):
        return self.world()[3]

    def move_to(self, x, y):
        # A moved object gets plain floats, dropping any preserved expression,
        # which is right: the number no longer means what the source said.
        parent = self.parent_object()
        if parent is not None:
            px, py, pa, ps = parent.world()
            dx, dy = x - px, y - py
            cos_a, sin_a = math.cos(-pa), math.sin(-pa)
            x = (dx * cos_a - dy * sin_a) / (ps or 1.0)
            y = (dx * sin_a + dy * cos_a) / (ps or 1.0)
        self.position = Vec2(x, y, self.position.style or Vec2.TABLE)

    def angle(self):
        return self.world()[2]

    def set_angle(self, radians, keep_zero=False):
        parent = self.parent_object()
        if parent is not None:
            radians = radians - parent.world()[2]
        if abs(radians) < 1e-9 and not keep_zero:
            self.rotation = None
        else:
            self.rotation = radians

    def clone(self):
        return LevelObject(
            self.prefab,
            self.position.copy(),
            self.rotation,
            self.id,
            copy.deepcopy(self.overrides),
            [e.clone() for e in self.extra_components],
            self.comment,
            copy.deepcopy(self.extra_keys),
            dict(self.key_comments),
            self.parent,
            self.scale,
        )

    def label(self):
        return self.id or self.prefab

    def __repr__(self):
        return f"LevelObject({self.prefab!r}, id={self.id!r})"


class Level:
    def __init__(self, objects=None, header=None):
        self.objects = objects if objects is not None else []
        self.header = header
        for obj in self.objects:
            obj.level = self

    def index_of(self, obj):
        for index, candidate in enumerate(self.objects):
            if candidate is obj:
                return index
        return -1

    def add(self, obj, index=None):
        obj.level = self
        if index is None:
            self.objects.append(obj)
        else:
            self.objects.insert(index, obj)
        return obj

    def remove(self, obj):
        index = self.index_of(obj)
        if index >= 0:
            removed = self.objects.pop(index)
            # Anything that was parented to it is now dangling. Left as-is
            # rather than silently reparented: lint reports the broken link,
            # and undo has to be able to put it back exactly.
            removed.level = None
            return removed
        return None

    def move(self, obj, new_index):
        index = self.index_of(obj)
        if index < 0:
            return False
        new_index = max(0, min(len(self.objects) - 1, new_index))
        if new_index == index:
            return False
        self.objects.insert(new_index, self.objects.pop(index))
        return True

    def find_by_id(self, object_id):
        for obj in self.objects:
            if obj.id == object_id:
                return obj
        return None

    def ids(self):
        return [o.id for o in self.objects if o.id]

    def unique_id(self, base):
        base = base or "object"
        taken = set(self.ids())
        if base not in taken:
            return base
        index = 2
        while f"{base}{index}" in taken:
            index += 1
        return f"{base}{index}"


# ---------------------------------------------------------------------------
# Instance resolution
# ---------------------------------------------------------------------------


def resolve(obj, library):
    """The effective Prefab the engine would build for `obj`.

    Mirrors `Prefab.Instantiate`: start from the prefab definition, then merge
    the instance overrides key by key. Returns None when the prefab name is not
    in the library -- which is exactly the case that makes `Level.load` assert.
    """
    definition = library.find(obj.prefab) if library is not None else None
    if definition is None:
        return None

    resolved = definition.clone()
    for component_type, values in obj.overrides.items():
        component = resolved.find(component_type)
        if component is None:
            # The engine silently ignores this: mergeArgs only walks the
            # components the prefab declares. Lint flags it.
            continue
        for name, value in values.items():
            component.set(name, copy.deepcopy(value))

    for extra in obj.extra_components:
        if resolved.find(extra.type) is None:
            resolved.components.append(
                Component(extra.type, copy.deepcopy(extra.args))
            )

    return resolved


def orphan_overrides(obj, library):
    """Override buckets naming a component the prefab does not declare."""
    definition = library.find(obj.prefab) if library is not None else None
    if definition is None:
        return []
    return [name for name in obj.overrides if definition.find(name) is None]


# ---------------------------------------------------------------------------
# LuaTable -> model
# ---------------------------------------------------------------------------


def _to_vec2(value, fallback_style=Vec2.TABLE):
    if isinstance(value, Vec2):
        return value
    if isinstance(value, LuaTable):
        return Vec2(value.get("x", Num(0.0)), value.get("y", Num(0.0)), fallback_style)
    return Vec2(0.0, 0.0, fallback_style)


def _args_from_table(type_name, table):
    """Convert an `args`/override table using the schema's field kinds."""
    spec = schema.spec_for(type_name)
    field_map = spec.field_map() if spec else {}
    args = {}
    if isinstance(table, LuaTable):
        for key, raw in table.items():
            args[key] = _convert_value(raw, field_map.get(key))
    return args


def object_from_table(entry, comment=None):
    prefab = entry.get("prefab")
    if not isinstance(prefab, str):
        raise ValueError("level entry is missing a string `prefab`")

    object_id = entry.get("id")
    if object_id is not None and not isinstance(object_id, str):
        raise ValueError(f"level entry `id` must be a string, got {object_id!r}")

    position = _to_vec2(entry.get("position"))
    rotation = entry.get("rotation")
    scale = entry.get("scale")
    parent = entry.get("parent")
    if parent is not None and not isinstance(parent, str):
        raise ValueError(f"level entry `parent` must be an id string, got {parent!r}")

    overrides = {}
    raw_overrides = entry.get("components")
    if isinstance(raw_overrides, LuaTable):
        for component_type, table in raw_overrides.items():
            values = _args_from_table(component_type, table)
            if values:
                overrides[component_type] = values

    extras = []
    raw_extras = entry.get("extraComponents")
    if isinstance(raw_extras, LuaTable):
        for index, item in enumerate(raw_extras.array):
            if not isinstance(item, LuaTable):
                continue
            type_name = item.get("type")
            if not isinstance(type_name, str):
                raise ValueError("extraComponents entry is missing a string `type`")
            args = _args_from_table(type_name, item.get("args"))
            # connectedObjectId is not in the schema (it exists only in the
            # level file; Level.load swaps it for a live object), so it comes
            # through _args_from_table as a plain string, which is what we want.
            extras.append(ExtraComponent(type_name, args,
                                         raw_extras.comments.get(index)))

    unknown = {k: v for k, v in entry.items() if k not in KNOWN_KEYS}

    return LevelObject(prefab, position, rotation, object_id,
                       overrides, extras, comment, unknown,
                       dict(entry.comments), parent, scale)


def level_from_table(table):
    if not isinstance(table, LuaTable):
        raise ValueError("a level file must return a table")
    if table.hash and not table.array:
        raise ValueError(
            "a level file must return an array of object entries, not a keyed "
            "table -- this looks like a prefab definitions file"
        )

    objects = []
    for index, entry in enumerate(table.array):
        if not isinstance(entry, LuaTable):
            continue
        objects.append(object_from_table(entry, table.comments.get(index)))
    level = Level()
    for obj in objects:
        level.add(obj)          # sets the back-reference `parent` needs
    return level
