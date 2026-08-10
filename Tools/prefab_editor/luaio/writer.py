"""Serializes a PrefabLibrary back into `definitions.lua`.

Three rules keep the output reviewable in a diff:

* an argument is written if it was present in the source file, or if it now
  differs from the engine default -- so a load/save cycle with no edits is a
  no-op, and newly added components stay terse;
* `Num` values re-emit the expression they were parsed from, so `math.pi / 3`
  survives instead of decaying into a long decimal;
* `Vec2` values re-emit in the style they were read in, call form or table form.
"""

from __future__ import annotations

from ..model import schema
from .types import Num, Vec2, num_src

INDENT = "    "

HEADER = """-- Prefab definitions.
--
-- Edited with Tools/prefab_editor. Hand edits are preserved on the next load
-- as long as they stay inside the supported data subset (tables, numbers,
-- strings, booleans, Vector.new and math.*).
"""


def format_number(value):
    src = num_src(value)
    if src:
        return src
    as_float = float(value)
    if as_float != as_float or as_float in (float("inf"), float("-inf")):
        raise ValueError(f"cannot serialize non-finite number {as_float}")
    if as_float.is_integer() and abs(as_float) < 1e15:
        return str(int(as_float))
    text = repr(round(as_float, 10))
    return text


def format_string(value):
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    escaped = escaped.replace("\n", "\\n").replace("\t", "\\t")
    return f'"{escaped}"'


def format_vec2(value, style_hint=None):
    style = value.style or style_hint or Vec2.TABLE
    x = format_number(value.x)
    y = format_number(value.y)
    if style == Vec2.CALL:
        return f"Vector.new({x}, {y})"
    return f"{{ x = {x}, y = {y} }}"


def format_color(channels):
    return "{" + ", ".join(format_number(c) for c in channels) + "}"


def _emit_comment(lines, comment, indent):
    if not comment:
        return
    for line in comment.split("\n"):
        lines.append(f"{indent}-- {line}".rstrip())


def _values_equal(left, right):
    if isinstance(left, Vec2) or isinstance(right, Vec2):
        if not (isinstance(left, Vec2) and isinstance(right, Vec2)):
            return False
        return left.as_tuple() == right.as_tuple()
    if isinstance(left, list) and isinstance(right, list):
        if len(left) != len(right):
            return False
        return all(_values_equal(a, b) for a, b in zip(left, right))
    if isinstance(left, bool) or isinstance(right, bool):
        return bool(left) == bool(right)
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return float(left) == float(right)
    return left == right


def _should_write(component, field_spec, value):
    if value is None:
        return False
    if field_spec is None:
        return True
    if field_spec.name in component.explicit:
        return True
    return not _values_equal(value, field_spec.make_default())


def _segment_should_write(segment, field_spec):
    value = segment.get(field_spec.name)
    if value is None:
        return False
    if field_spec.name in segment.get("_explicit", set()):
        return True
    return not _values_equal(value, field_spec.make_default())


def _emit_segments(lines, segments, indent):
    if not segments:
        lines.append(f"{indent}segments = {{}},")
        return

    lines.append(f"{indent}segments = {{")
    inner = indent + INDENT
    for segment in segments:
        parts = []
        for field_spec in schema.SEGMENT_FIELDS:
            if not _segment_should_write(segment, field_spec):
                continue
            value = segment[field_spec.name]
            if field_spec.kind == schema.VEC2:
                parts.append(f"{field_spec.name} = {format_vec2(value, Vec2.CALL)}")
            else:
                parts.append(f"{field_spec.name} = {format_number(value)}")
        lines.append(f"{inner}{{ " + ", ".join(parts) + " },")
    lines.append(f"{indent}}},")


def _emit_args(lines, component, indent):
    spec = component.spec()
    field_map = spec.field_map() if spec else {}

    ordered = []
    if spec:
        ordered.extend(f.name for f in spec.fields)
    for name in component.args:
        if name not in ordered:
            ordered.append(name)

    written = []
    for name in ordered:
        value = component.args.get(name)
        field_spec = field_map.get(name)
        if not _should_write(component, field_spec, value):
            continue
        written.append((name, value, field_spec))

    if not written:
        lines.append(f"{indent}args = {{}},")
        return

    lines.append(f"{indent}args = {{")
    inner = indent + INDENT
    for name, value, field_spec in written:
        kind = field_spec.kind if field_spec else None
        if kind == schema.SEGMENTS:
            _emit_segments(lines, value, inner)
        elif kind == schema.STRING_LIST:
            items = ", ".join(format_string(item) for item in value)
            lines.append(f"{inner}{name} = {{ {items} }}," if items
                         else f"{inner}{name} = {{}},")
        elif kind == schema.COLOR:
            lines.append(f"{inner}{name} = {format_color(value)},")
        elif isinstance(value, Vec2):
            lines.append(f"{inner}{name} = {format_vec2(value)},")
        elif isinstance(value, bool):
            lines.append(f"{inner}{name} = {'true' if value else 'false'},")
        elif isinstance(value, str):
            lines.append(f"{inner}{name} = {format_string(value)},")
        elif isinstance(value, (int, float, Num)):
            lines.append(f"{inner}{name} = {format_number(value)},")
        else:
            raise ValueError(f"cannot serialize {name} = {value!r}")
    lines.append(f"{indent}}},")


def _uses_vector(library):
    for prefab in library.prefabs:
        for component in prefab.components:
            for value in component.args.values():
                if isinstance(value, Vec2) and (value.style or Vec2.TABLE) == Vec2.CALL:
                    return True
                if isinstance(value, list) and value and isinstance(value[0], dict):
                    return True
    return False


def _uses_math(library):
    for prefab in library.prefabs:
        for component in prefab.components:
            for value in component.args.values():
                if isinstance(value, Num) and value.src and "math." in value.src:
                    return True
                if isinstance(value, list):
                    for segment in value:
                        if not isinstance(segment, dict):
                            continue
                        for inner in segment.values():
                            if isinstance(inner, Num) and inner.src and "math." in inner.src:
                                return True
    return False


def write_library(library):
    lines = [HEADER.rstrip(), ""]

    if _uses_vector(library):
        lines.append("local Vector = require('Libraries.transform.vector')")
    if _uses_math(library):
        lines.append("local math = require('math')")
    if lines[-1] != "":
        lines.append("")

    lines.append("return {")

    for position, prefab in enumerate(library.prefabs):
        if position:
            lines.append("")
        _emit_comment(lines, prefab.comment, INDENT)
        lines.append(f"{INDENT}{prefab.name} = {{")
        lines.append(f"{INDENT * 2}components = {{")

        for component in prefab.components:
            _emit_comment(lines, component.comment, INDENT * 3)
            lines.append(f"{INDENT * 3}{{")
            lines.append(f'{INDENT * 4}type = "{component.type}",')
            _emit_args(lines, component, INDENT * 4)
            lines.append(f"{INDENT * 3}}},")

        lines.append(f"{INDENT * 2}}},")
        lines.append(f"{INDENT}}},")

    lines.append("}")
    lines.append("")
    return "\n".join(lines)


def write_file(library, path, make_backup=True):
    import shutil
    import os

    text = write_library(library)
    if make_backup and os.path.exists(path):
        shutil.copy2(path, path + ".bak")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)
    return text
