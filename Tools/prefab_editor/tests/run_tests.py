"""Self-tests. Run with:  python -m prefab_editor.tests.run_tests

No pytest dependency and no Qt: everything here is headless so it can run on the
handheld or in CI. The Lua parity checks are skipped automatically when no `lua`
interpreter is on PATH.
"""

from __future__ import annotations

import math
import os
import shutil
import subprocess
import sys
import tempfile

from ..luaio import reader, writer
from ..luaio.types import LuaSyntaxError, Num, Vec2
from ..model import generators, schema
from ..model.library import Component, Prefab, PrefabLibrary, library_from_table
from ..model.project import Project
from ..preview import raytrace
from ..preview.raytrace import V
from ..validate import lint

PASSED = []
FAILED = []


def check(name, condition, detail=""):
    if condition:
        PASSED.append(name)
        print(f"  pass  {name}")
    else:
        FAILED.append(name)
        print(f"  FAIL  {name} {detail}")


# ---------------------------------------------------------------------------


def test_parser_basics():
    table = reader.parse("""
        local Vector = require('Libraries.transform.vector')
        return {
            -- a leading comment
            Thing = {
                components = {
                    { type = "LightSource", args = { coneAngle = math.pi / 3, rayCount = 8 } },
                },
            },
        }
    """)
    thing = table.get("Thing")
    check("parser: comment attached to prefab",
          table.comments.get("Thing") == "a leading comment")
    args = thing.get("components").array[0].get("args")
    check("parser: math expression evaluated",
          abs(float(args.get("coneAngle")) - math.pi / 3) < 1e-12)
    check("parser: math expression source preserved",
          args.get("coneAngle").src == "math.pi / 3")

    for source in ("return { x = someGlobal }", "return { x = 1 } extra", "{ x = 1 }"):
        try:
            reader.parse(source)
            check(f"parser: rejects {source!r}", False)
        except (LuaSyntaxError, ValueError):
            check(f"parser: rejects {source!r}", True)


def test_vec_styles():
    table = reader.parse("""
        local Vector = require('Libraries.transform.vector')
        return { P = { components = { { type = "LightCollider", args = {
            segments = { { a = Vector.new(-4, 0), b = Vector.new(4, 0), reflective = 1 } } } } } } }
    """)
    library = library_from_table(table)
    segment = library.find("P").find("LightCollider").get("segments")[0]
    check("vec2: call style detected", segment["a"].style == Vec2.CALL)
    text = writer.write_library(library)
    check("vec2: call style re-emitted", "Vector.new(-4, 0)" in text)

    table_style = reader.parse('return { P = { components = { { type = "SpriteRenderer",'
                               ' args = { scale = { x = 4, y = 2 } } } } } }')
    library = library_from_table(table_style)
    scale = library.find("P").find("SpriteRenderer").get("scale")
    check("vec2: table style detected", scale.style == Vec2.TABLE)
    check("vec2: table style re-emitted",
          "{ x = 4, y = 2 }" in writer.write_library(library))


def test_defaults_are_omitted():
    library = PrefabLibrary([Prefab("Fresh", [Component.create("RigidBody")])])
    text = writer.write_library(library)
    check("writer: pure-default component emits empty args", "args = {}" in text)

    component = Component.create("RigidBody")
    component.set("restitution", 0.4)
    library = PrefabLibrary([Prefab("Bouncy", [component])])
    text = writer.write_library(library)
    check("writer: changed value emitted", "restitution = 0.4" in text)
    check("writer: unchanged sibling omitted", "friction" not in text)


def test_explicit_keys_survive():
    source = ('return { P = { components = { { type = "RigidBody",'
              ' args = { friction = 0.3 } } } } }')
    library = library_from_table(reader.parse(source))
    text = writer.write_library(library)
    check("writer: explicit default-valued key kept", "friction = 0.3" in text)


def test_project_roundtrip(project):
    if project is None:
        return
    library = library_from_table(reader.parse_file(project.definitions_path))
    text = writer.write_library(library)
    again = library_from_table(reader.parse(text))

    check("roundtrip: prefab names stable", library.names() == again.names())
    check("roundtrip: component order stable",
          [p.component_types() for p in library.prefabs]
          == [p.component_types() for p in again.prefabs])
    check("roundtrip: second pass is a fixed point",
          writer.write_library(again) == text)


def test_lua_semantic_equivalence(project):
    lua = shutil.which("lua5.3") or shutil.which("lua") or shutil.which("lua5.4")
    if lua is None or project is None:
        print("  skip  lua semantic equivalence (no lua interpreter)")
        return

    dump = r'''
package.path = "%s/?.lua;" .. package.path
local defs = assert(loadfile(arg[1]))()
local function ser(v, ind)
  ind = ind or ""
  if type(v) == "table" then
    local keys = {}
    for k in pairs(v) do keys[#keys+1] = k end
    table.sort(keys, function(a,b) return tostring(a) < tostring(b) end)
    local out = {}
    for _, k in ipairs(keys) do
      out[#out+1] = ind .. "  " .. tostring(k) .. " = " .. ser(v[k], ind .. "  ")
    end
    return "{\n" .. table.concat(out, ",\n") .. "\n" .. ind .. "}"
  elseif type(v) == "number" then return string.format("%%.10g", v)
  elseif type(v) == "string" then return string.format("%%q", v)
  else return tostring(v) end
end
print(ser(defs))
''' % project.root

    with tempfile.TemporaryDirectory() as tmp:
        dump_path = os.path.join(tmp, "dump.lua")
        with open(dump_path, "w") as handle:
            handle.write(dump)

        library = library_from_table(reader.parse_file(project.definitions_path))
        regen_path = os.path.join(tmp, "regen.lua")
        with open(regen_path, "w") as handle:
            handle.write(writer.write_library(library))

        def run(target):
            return subprocess.run([lua, dump_path, target], capture_output=True,
                                  text=True, cwd=project.root).stdout

        original = run(project.definitions_path)
        regenerated = run(regen_path)
        check("lua: regenerated file is semantically identical",
              bool(original) and original == regenerated)


def test_raytrace_parity():
    segments = [
        raytrace.Segment(V(-40, 60), V(60, -20), 1.0, 1.0, 0.0),
        raytrace.Segment(V(120, -80), V(120, 120), 0.5, 1.5, 0.2),
        raytrace.Segment(V(-100, 150), V(200, 150), 0.8, 1.0, 0.1),
    ]
    fan = raytrace.cast_fan(segments, V(-80, 20), 0.3, 24, math.pi / 2, 5, 0.02)
    hits = [node for root in fan for node in root.walk() if node.hit_point]
    check("raytrace: fan produces bounces", len(hits) > len(fan))

    # Total internal reflection: past the critical angle refract must give up.
    dense_to_thin = raytrace.refract(V(1, 1).normalized(), V(0, -1), 1.5, 1.0)
    check("raytrace: total internal reflection returns None", dense_to_thin is None)

    # A normal-incidence bounce must come straight back.
    bounced = raytrace.reflect(V(0, 1), V(0, -1))
    check("raytrace: normal incidence reflects straight back",
          abs(bounced.x) < 1e-12 and abs(bounced.y + 1) < 1e-12)


def test_lint_rules():
    body = Component.create("RigidBody")
    body.set("bodyType", "dynamic")
    body.set("width", 64.0)
    body.set("height", 8.0)
    light = Component.create("LightCollider")
    light.set("dynamic", False)
    light.set("segments", [{
        "a": Vec2(-32, 0, Vec2.CALL), "b": Vec2(32, 0, Vec2.CALL),
        "reflective": 1.0, "refractiveIndex": 1.0, "absorption": 0.0,
        "_explicit": {"a", "b", "reflective"},
    }])
    prefab = Prefab("Mover", [body, light])
    issues = lint.lint_prefab(prefab)
    check("lint: frozen segments on a moving body flagged",
          any("dynamic = true" in i.message for i in issues))

    tiny = Component.create("RigidBody")
    tiny.set("width", 4.0)
    tiny.set("height", 4.0)
    issues = lint.lint_prefab(Prefab("Tiny", [tiny]))
    check("lint: sub-Box2D-scale collider flagged",
          any("tuned range" in i.message for i in issues))

    circle = Component.create("RigidBody")
    circle.set("shape", "circle")
    issues = lint.lint_prefab(Prefab("Ball", [circle]))
    check("lint: circle without radius flagged",
          any(i.field == "radius" and i.severity == lint.ERROR for i in issues))

    joint = Prefab("Jointed", [Component.create("HingeJoint")])
    issues = lint.lint_prefab(joint)
    check("lint: HingeJoint rejected in a prefab",
          any("cannot live in a prefab" in i.message for i in issues))

    duplicated = Prefab("Twice", [Component.create("SpriteRenderer"),
                                  Component.create("SpriteRenderer")])
    issues = lint.lint_prefab(duplicated)
    check("lint: duplicate component type flagged",
          any("overwrites" in i.message for i in issues))

    # Door and LightDetector both resolve a sibling by name in OnAttach and
    # both fail silently when it is missing or ordered after them -- the door
    # simply never opens, the detector never changes sprite. Nothing crashes,
    # which is exactly why these need to be caught at author time.
    def door_prefab(*, sensor=True, with_body=True, animator_last=False):
        sprite = Component.create("SpriteRenderer")
        animation = Component.create("AnimationPlayer")
        door = Component.create("Door")
        door.set("nextLevel", "Frontend.levels.level_complete")
        components = [sprite]
        if not animator_last:
            components.append(animation)
        if with_body:
            body = Component.create("RigidBody")
            body.set("bodyType", "static")
            body.set("sensor", sensor)
            components.append(body)
        components.append(door)
        if animator_last:
            components.append(animation)
        return Prefab("TestDoor", components)

    issues = lint.lint_prefab(door_prefab())
    check("lint: a correct door is clean",
          not any(i.component == "Door" for i in issues))

    issues = lint.lint_prefab(door_prefab(sensor=False))
    check("lint: non-sensor door body flagged",
          any("not a sensor" in i.message for i in issues))

    issues = lint.lint_prefab(door_prefab(with_body=False))
    check("lint: door with nowhere to detect entry flagged",
          any("no RigidBody" in i.message for i in issues))

    issues = lint.lint_prefab(door_prefab(animator_last=True))
    check("lint: animator ordered after Door is an error",
          any("ordered after Door" in i.message and i.severity == lint.ERROR
              for i in issues))

    # A sensor is a region of interest, not the extent of the art, so the
    # sprite/collider size rule must not fire on one.
    issues = lint.lint_prefab(door_prefab())
    check("lint: sensor size mismatch is not warned about",
          not any("but the collider is" in i.message for i in issues))

    detector = Component.create("LightDetector")
    detector.set("litSprite", "Resources/sprites/detector/detector_on.png")
    issues = lint.lint_prefab(Prefab("Blind", [detector]))
    check("lint: lit sprite with no renderer flagged",
          any("swap it into" in i.message for i in issues))


def test_generators():
    body = Component.create("RigidBody")
    body.set("width", 64.0)
    body.set("height", 32.0)
    light = Component.create("LightCollider")
    prefab = Prefab("Crate", [body, light])

    ok, _message = generators.segments_from_collider(prefab, faces="all")
    segments = light.get("segments")
    check("generators: four edges produced", ok and len(segments) == 4)

    corners = {(float(s["a"].x), float(s["a"].y)) for s in segments}
    check("generators: edges trace the collider rectangle",
          corners == {(-32, -16), (32, -16), (32, 16), (-32, 16)})

    ok, _message = generators.segments_from_collider(prefab, faces="top")
    check("generators: top-only produces one segment",
          ok and len(light.get("segments")) == 1)

    body.set("bodyType", "dynamic")
    generators.segments_from_collider(prefab, faces="all")
    check("generators: dynamic body gets dynamic segments",
          light.get("dynamic") is True)


def test_schema_matches_engine(project):
    """Every schema component (bar HingeJoint) should exist in the registry."""
    if project is None:
        return
    registered = project.registered_components()
    if not registered:
        return
    missing = [name for name in schema.COMPONENTS
               if name not in registered and name != "DebugLightRenderer"]
    check("schema: every component is registered in the engine",
          not missing, f"missing: {missing}")


def main():
    project = Project.discover(os.path.dirname(os.path.abspath(__file__)))
    print(f"project: {project.root if project else 'not found'}\n")

    test_parser_basics()
    test_vec_styles()
    test_defaults_are_omitted()
    test_explicit_keys_survive()
    test_project_roundtrip(project)
    test_lua_semantic_equivalence(project)
    test_raytrace_parity()
    test_lint_rules()
    test_generators()
    test_schema_matches_engine(project)

    print(f"\n{len(PASSED)} passed, {len(FAILED)} failed")
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
