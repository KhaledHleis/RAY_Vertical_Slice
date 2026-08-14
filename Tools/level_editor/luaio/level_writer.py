"""Serializes a Level back into a `Frontend/levels/*.lua` file.

Same three round-trip rules as the prefab writer: `Num` re-emits the expression
it was parsed from so `math.pi / 6` survives, `Vec2` re-emits in the style it
was read in, and comments attached to an entry come back out.

The fourth rule is specific to levels: an override is written if and only if it
is in `LevelObject.overrides`, with no default-comparison step. The model only
ever puts a key there when the designer changed it, so "did this differ from the
prefab" was already decided at edit time and does not need re-deriving here.

The emitted array is one entry per indented block rather than the `{{ ... }, {`
run-on style a previous formatter left in `demo.lua`. Both are the same Lua; the
block form is what makes a two-line move show up as a two-line diff.
"""

from __future__ import annotations

import os
import shutil

from ..model import schema
from .types import LuaTable, Num, Vec2, num_src
from .writer import (INDENT, format_color, format_number, format_string,
                     format_tiles, format_vec2)

HEADER = """-- Level definition, loaded by Level.load('Frontend.levels.<name>', scene).
--
-- Edited with Tools/level_editor. The list order is the draw order: Scene:Draw
-- walks it with ipairs, so later entries paint over earlier ones.
"""


def _emit_comment(lines, comment, indent):
    if not comment:
        return
    for line in comment.split("\n"):
        lines.append(f"{indent}-- {line}".rstrip())


def _needs_vector(value):
    if isinstance(value, Vec2):
        return (value.style or Vec2.TABLE) == Vec2.CALL
    if isinstance(value, list):
        return any(_needs_vector(v) for v in value)
    if isinstance(value, dict):
        return any(_needs_vector(v) for k, v in value.items() if k != "_explicit")
    return False


def _needs_math(value):
    if isinstance(value, Num):
        return bool(value.src and "math." in value.src)
    if isinstance(value, Vec2):
        return _needs_math(value.x) or _needs_math(value.y)
    if isinstance(value, list):
        return any(_needs_math(v) for v in value)
    if isinstance(value, dict):
        return any(_needs_math(v) for k, v in value.items() if k != "_explicit")
    return False


def _walk_values(level):
    for obj in level.objects:
        yield obj.position
        if obj.rotation is not None:
            yield obj.rotation
        if obj.scale is not None:
            yield obj.scale
        for bucket in obj.overrides.values():
            for value in bucket.values():
                yield value
        for extra in obj.extra_components:
            for value in extra.args.values():
                yield value
        for value in obj.extra_keys.values():
            yield value


def format_segment(segment):
    parts = []
    for field in schema.SEGMENT_FIELDS:
        value = segment.get(field.name)
        if value is None:
            continue
        explicit = field.name in (segment.get("_explicit") or set())
        default = field.make_default()
        if not explicit:
            if isinstance(value, Vec2) and isinstance(default, Vec2):
                if value.as_tuple() == default.as_tuple():
                    continue
            elif isinstance(value, (int, float)) and isinstance(default, (int, float)):
                if float(value) == float(default):
                    continue
        if field.kind == schema.VEC2:
            parts.append(f"{field.name} = {format_vec2(value, Vec2.CALL)}")
        else:
            parts.append(f"{field.name} = {format_number(value)}")
    return "{ " + ", ".join(parts) + " }"


def emit_value(lines, key, value, indent, field_spec=None, row_width=None):
    """Write `key = value,` at `indent`, recursing into tables.

    `row_width` only matters for a TILES field: the grid is stored flat, so the
    map width has to be handed down from the sibling key for the writer to know
    where to break the lines.
    """
    kind = field_spec.kind if field_spec else None

    if kind == schema.TILES:
        format_tiles(lines, key, value, indent, row_width)
        return

    if kind == schema.SEGMENTS or (field_spec is None and _is_segment_list(value)):
        if not value:
            lines.append(f"{indent}{key} = {{}},")
            return
        lines.append(f"{indent}{key} = {{")
        for segment in value:
            lines.append(f"{indent}{INDENT}{format_segment(segment)},")
        lines.append(f"{indent}}},")
        return

    if kind == schema.COLOR and isinstance(value, list):
        lines.append(f"{indent}{key} = {format_color(value)},")
        return

    if isinstance(value, Vec2):
        lines.append(f"{indent}{key} = {format_vec2(value)},")
        return
    if isinstance(value, bool):
        lines.append(f"{indent}{key} = {'true' if value else 'false'},")
        return
    if isinstance(value, str):
        lines.append(f"{indent}{key} = {format_string(value)},")
        return
    if isinstance(value, (int, float, Num)):
        lines.append(f"{indent}{key} = {format_number(value)},")
        return
    if isinstance(value, LuaTable):
        lines.append(f"{indent}{key} = {{")
        _emit_lua_table(lines, value, indent + INDENT)
        lines.append(f"{indent}}},")
        return
    if value is None:
        return
    raise ValueError(f"cannot serialize {key} = {value!r}")


def _is_segment_list(value):
    return (isinstance(value, list) and value
            and all(isinstance(v, dict) for v in value))


def _emit_lua_table(lines, table, indent):
    """Passthrough for a table the schema knows nothing about."""
    for item in table.array:
        if isinstance(item, LuaTable):
            lines.append(f"{indent}{{")
            _emit_lua_table(lines, item, indent + INDENT)
            lines.append(f"{indent}}},")
        else:
            emit_value(lines, "__item", item, indent)
            lines[-1] = lines[-1].replace("__item = ", "", 1)
    for key, item in table.items():
        emit_value(lines, key, item, indent)


def _prefab_component(obj, component_type):
    """The prefab's own component, when the level model has a library to ask.

    Levels are written without one in the tests, so this stays optional and
    silently gives up rather than making the writer depend on the library.
    """
    library = getattr(getattr(obj, "level", None), "library", None)
    if library is None:
        return None
    definition = library.find(obj.prefab)
    return definition.find(component_type) if definition else None


def _emit_overrides(lines, obj, indent):
    if not obj.overrides:
        return
    lines.append(f"{indent}components = {{")
    inner = indent + INDENT
    for component_type, values in obj.overrides.items():
        if not values:
            continue
        spec = schema.spec_for(component_type)
        field_map = spec.field_map() if spec else {}
        order = [f.name for f in spec.fields] if spec else []
        keys = [k for k in order if k in values]
        keys += [k for k in values if k not in order]

        # The tile grid is flat, so the row width it should be broken at lives
        # in a sibling key. Prefer the instance override; fall back to the
        # prefab's own value when only the tiles were overridden.
        row_width = values.get("width")
        if row_width is None and spec is not None:
            definition = _prefab_component(obj, component_type)
            row_width = definition.args.get("width") if definition else None

        lines.append(f"{inner}{component_type} = {{")
        for name in keys:
            emit_value(lines, name, values[name], inner + INDENT,
                       field_map.get(name), row_width)
        lines.append(f"{inner}}},")
    lines.append(f"{indent}}},")


def _emit_extra_components(lines, obj, indent):
    if not obj.extra_components:
        return
    lines.append(f"{indent}extraComponents = {{")
    inner = indent + INDENT
    for extra in obj.extra_components:
        _emit_comment(lines, extra.comment, inner)
        lines.append(f"{inner}{{")
        body = inner + INDENT
        lines.append(f'{body}type = {format_string(extra.type)},')

        spec = schema.spec_for(extra.type)
        field_map = spec.field_map() if spec else {}
        order = [f.name for f in spec.fields] if spec else []
        # connectedObjectId is not a schema field but must come first: it is the
        # thing a reader looks for to understand what the joint is attached to.
        keys = [k for k in ("connectedObjectId",) if k in extra.args]
        keys += [k for k in order if k in extra.args and k not in keys]
        keys += [k for k in extra.args if k not in keys]

        if not keys:
            lines.append(f"{body}args = {{}},")
        else:
            lines.append(f"{body}args = {{")
            for name in keys:
                emit_value(lines, name, extra.args[name], body + INDENT,
                           field_map.get(name), extra.args.get("width"))
            lines.append(f"{body}}},")
        lines.append(f"{inner}}},")
    lines.append(f"{indent}}},")


def write_level(level):
    lines = [HEADER.rstrip(), ""]

    values = list(_walk_values(level))
    if any(_needs_vector(v) for v in values):
        lines.append("local Vector = require('Libraries.transform.vector')")
    if any(_needs_math(v) for v in values):
        lines.append("local math = require('math')")
    if lines[-1] != "":
        lines.append("")

    lines.append("return {")

    for position, obj in enumerate(level.objects):
        if position:
            lines.append("")
        _emit_comment(lines, obj.comment, INDENT)
        lines.append(f"{INDENT}{{")
        body = INDENT * 2

        note = obj.key_comments.get

        if obj.id:
            _emit_comment(lines, note("id"), body)
            lines.append(f"{body}id = {format_string(obj.id)},")
        _emit_comment(lines, note("prefab"), body)
        lines.append(f"{body}prefab = {format_string(obj.prefab)},")
        _emit_comment(lines, note("position"), body)
        emit_value(lines, "position", obj.position, body)
        if obj.rotation is not None:
            _emit_comment(lines, note("rotation"), body)
            emit_value(lines, "rotation", obj.rotation, body)
        # Omitted when 1: uniform scale defaults to 1 in Transform.new, and a
        # level full of `scale = 1` is noise.
        if obj.scale is not None and float(obj.scale) != 1.0:
            _emit_comment(lines, note("scale"), body)
            emit_value(lines, "scale", obj.scale, body)
        if obj.parent:
            _emit_comment(lines, note("parent"), body)
            lines.append(f"{body}parent = {format_string(obj.parent)},")

        for key, value in obj.extra_keys.items():
            _emit_comment(lines, note(key), body)
            emit_value(lines, key, value, body)

        _emit_comment(lines, note("components"), body)
        _emit_overrides(lines, obj, body)
        _emit_comment(lines, note("extraComponents"), body)
        _emit_extra_components(lines, obj, body)

        lines.append(f"{INDENT}}},")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def write_file(level, path, make_backup=True):
    text = write_level(level)
    if make_backup and os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return text
