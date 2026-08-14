"""Self-tests. Standard library only, so they run on the handheld and in CI.

    python -m level_editor.tests.run_tests
    python -m level_editor.tests.run_tests --project /path/to/RAY

The interesting ones are the round-trip tests. A level editor that silently
drops a hand-written comment, turns `math.pi / 2` into 1.5707963267948966, or
rewrites `Vector.new(100, 100)` as a table is worse than editing the file by
hand, because you only notice in the diff after you have already saved.
"""

from __future__ import annotations

import argparse
import math
import os
import sys

from ..luaio import level_writer, reader
from ..luaio.types import LuaSyntaxError, Num, Vec2
from ..model import schema
from ..model.level import (ExtraComponent, Level, LevelObject, level_from_table,
                           orphan_overrides, resolve)
from ..model.library import library_from_table
from ..model.tilemap import TilemapBinding
from ..model.project import Project
from ..preview import scene_light
from ..preview.raytrace import V
from ..validate import lint

FAILURES = []
CHECKS = [0]


def check(condition, message):
    CHECKS[0] += 1
    if not condition:
        FAILURES.append(message)


def check_equal(actual, expected, message):
    check(actual == expected, f"{message}: expected {expected!r}, got {actual!r}")


SAMPLE = """
local Vector = require('Libraries.transform.vector')

return {{
    id = "floor",
    prefab = "Box",
    position = { x = 160, y = 220 },
    components = {
        RigidBody = { bodyType = "static", width = 320, height = 16 }
    }
}, {
    -- a hand-written note
    id = "mirror",
    prefab = "Mirror",
    position = Vector.new(200, 40),
    rotation = math.pi / 6
}, {
    id = "lamp",
    prefab = "Box",
    position = { x = 300, y = 60 },
    extraComponents = {{
        type = "HingeJoint",
        args = { connectedObjectId = "floor", anchor = { x = 260, y = 20 } }
    }}
}}
"""


def parse_sample():
    return level_from_table(reader.parse(SAMPLE))


# -- parsing -----------------------------------------------------------------


def test_parse():
    level = parse_sample()
    check_equal(len(level.objects), 3, "object count")

    floor = level.objects[0]
    check_equal(floor.id, "floor", "id")
    check_equal(floor.prefab, "Box", "prefab")
    check_equal(floor.position.as_tuple(), (160.0, 220.0), "position")
    check_equal(floor.rotation, None, "absent rotation stays absent")
    check_equal(floor.overrides["RigidBody"]["bodyType"], "static", "override value")
    check_equal(floor.overrides["RigidBody"]["width"], 320.0, "numeric override")

    mirror = level.objects[1]
    check(mirror.position.style == Vec2.CALL, "Vector.new style remembered")
    check(abs(float(mirror.rotation) - math.pi / 6) < 1e-12, "rotation value")
    check_equal(getattr(mirror.rotation, "src", None), "math.pi / 6",
                "rotation expression preserved")
    check("hand-written note" in (mirror.key_comments.get("id") or ""),
          "comment captured")

    lamp = level.objects[2]
    check_equal(len(lamp.extra_components), 1, "extra component count")
    check_equal(lamp.extra_components[0].type, "HingeJoint", "extra type")
    check_equal(lamp.extra_components[0].args["connectedObjectId"], "floor",
                "connectedObjectId")


def test_rejects_prefab_file():
    failed = False
    try:
        level_from_table(reader.parse("return { Box = { components = {} } }"))
    except ValueError:
        failed = True
    check(failed, "a keyed table is rejected as a level")


def test_rejects_bad_syntax():
    failed = False
    try:
        reader.parse("return { prefab = someFunction() }")
    except LuaSyntaxError:
        failed = True
    check(failed, "unsupported syntax raises rather than loading partially")


# -- writing -----------------------------------------------------------------


def test_round_trip():
    level = parse_sample()
    first = level_writer.write_level(level)
    second = level_writer.write_level(level_from_table(reader.parse(first)))
    check_equal(first, second, "write is idempotent")

    check("math.pi / 6" in first, "expression survives the round trip")
    check("Vector.new(200, 40)" in first, "call-style vector survives")
    check("{ x = 160, y = 220 }" in first, "table-style vector survives")
    check("hand-written note" in first, "comment survives")
    check("connectedObjectId = \"floor\"" in first, "joint reference survives")


def test_moving_drops_the_expression():
    level = parse_sample()
    level.objects[1].move_to(96, 96)
    text = level_writer.write_level(level)
    check("Vector.new(96, 96)" in text, "moved object keeps its vector style")


def test_only_overrides_are_written():
    level = Level([LevelObject("Box", Vec2(10.0, 20.0, Vec2.TABLE))])
    text = level_writer.write_level(level)
    check("components" not in text, "an object with no overrides writes no block")

    level.objects[0].override("RigidBody", "restitution", 0.3)
    text = level_writer.write_level(level)
    check("restitution = 0.3" in text, "an override is written")

    level.objects[0].clear_override("RigidBody", "restitution")
    text = level_writer.write_level(level)
    check("components" not in text, "reverting removes the block entirely")


def test_rotation_absent_when_zero():
    obj = LevelObject("Box")
    obj.set_angle(0.0)
    check("rotation" not in level_writer.write_level(Level([obj])),
          "zero rotation is omitted")
    obj.set_angle(math.pi / 2)
    check("rotation" in level_writer.write_level(Level([obj])),
          "non-zero rotation is written")


# -- model -------------------------------------------------------------------


def test_unique_id():
    level = parse_sample()
    check_equal(level.unique_id("floor"), "floor2", "unique_id increments")
    check_equal(level.unique_id("new"), "new", "unique_id leaves free names alone")


def test_draw_order():
    level = parse_sample()
    first = level.objects[0]
    level.move(first, 2)
    check_equal(level.index_of(first), 2, "move reorders")
    check_equal([o.id for o in level.objects], ["mirror", "lamp", "floor"],
                "the rest keep their order")


def test_resolution(library):
    level = parse_sample()
    floor = level.objects[0]
    resolved = resolve(floor, library)
    check(resolved is not None, "Box resolves")
    body = resolved.find("RigidBody")
    check_equal(body.get("bodyType"), "static", "override wins over the prefab")
    check_equal(float(body.get("width")), 320.0, "override width")
    check_equal(float(body.get("height")), 16.0, "override height")

    sprite = resolved.find("SpriteRenderer")
    check(sprite is not None, "un-overridden components come from the prefab")
    check_equal(float(sprite.get("scale").x), 4.0, "prefab value is untouched")

    check(resolve(LevelObject("NoSuchPrefab"), library) is None,
          "an unknown prefab resolves to None")

    stray = LevelObject("Anchor")
    stray.override("SpriteRenderer", "path", "x.png")
    check_equal(orphan_overrides(stray, library), ["SpriteRenderer"],
                "an override for a component the prefab lacks is reported")


def test_resolution_does_not_mutate_the_prefab(library):
    level = parse_sample()
    before = float(library.find("Box").find("RigidBody").get("width"))
    resolve(level.objects[0], library)
    after = float(library.find("Box").find("RigidBody").get("width"))
    check_equal(after, before, "resolving leaves the library alone")


# -- light -------------------------------------------------------------------


def test_scene_light(library):
    """A mirror between a source and nothing should produce a bounce."""
    source = LevelObject("LightCone", Vec2(0.0, 0.0, Vec2.TABLE))
    source.set_angle(0.0)                      # pointing +x
    source.override("LightSource", "coneAngle", 0.0)
    source.override("LightSource", "rayCount", 2)

    mirror = LevelObject("LightWall", Vec2(100.0, 0.0, Vec2.TABLE))
    mirror.set_angle(math.pi / 4)

    level = Level([source, mirror])
    solution = scene_light.solve(level, library)

    check_equal(len(solution.segments), 1, "one segment in the scene")
    check_equal(len(solution.fans), 1, "one fan")

    node = solution.fans[0][1][0]
    check(node.hit_point is not None, "the ray hits the mirror")
    check(node.reflected is not None, "and reflects")
    if node.hit_point is not None:
        check(abs(node.hit_point.x - 100.0) < 1.0,
              f"hit near x=100, got {node.hit_point.x}")


def test_zero_cone_angle_is_not_a_full_burst(library):
    """Lua keeps a coneAngle of 0; Python's `or` idiom would replace it."""
    source = LevelObject("LightCone", Vec2(0.0, 0.0, Vec2.TABLE))
    source.override("LightSource", "coneAngle", 0.0)
    source.override("LightSource", "rayCount", 2)
    solution = scene_light.solve(Level([source]), library)
    for node in solution.fans[0][1]:
        check(node.direction.x > 0.99,
              f"a 0-degree cone points along +x, got {node.direction}")


def test_light_respects_position(library):
    """Moving an object moves its segments -- the whole point of the overlay."""
    mirror = LevelObject("LightWall", Vec2(50.0, 60.0, Vec2.TABLE))
    level = Level([mirror])
    before = scene_light.collect_segments(level, library)[0]
    mirror.move_to(50.0, 200.0)
    after = scene_light.collect_segments(level, library)[0]
    check(abs(after.a.y - before.a.y - 140.0) < 1e-9,
          "segments follow the object")


# -- lint --------------------------------------------------------------------


def test_lint_duplicate_ids(library):
    level = Level([LevelObject("Box", object_id="a"),
                   LevelObject("Box", object_id="a")])
    issues = lint.lint_level(level, library)
    check(any("duplicate id" in i.message and i.severity == lint.ERROR
              for i in issues), "duplicate ids are an error")


def test_lint_unknown_prefab(library):
    issues = lint.lint_level(Level([LevelObject("Nope")]), library)
    check(any("unknown prefab" in i.message and i.severity == lint.ERROR
              for i in issues), "unknown prefab is an error")


def test_lint_dangling_joint(library):
    obj = LevelObject("Box", object_id="lamp")
    obj.extra_components.append(
        ExtraComponent("HingeJoint", {"connectedObjectId": "ghost",
                                      "anchor": Vec2(0.0, 0.0)}))
    issues = lint.lint_level(Level([obj]), library)
    check(any("unknown id" in i.message and i.severity == lint.ERROR
              for i in issues), "a joint pointing nowhere is an error")


def test_lint_orphan_override(library):
    obj = LevelObject("Anchor")
    obj.override("SpriteRenderer", "path", "x.png")
    issues = lint.lint_level(Level([obj]), library)
    check(any("does not have" in i.message for i in issues),
          "an ignored override is reported")


def test_lint_fractional_position(library):
    obj = LevelObject("Box", Vec2(10.5, 20.0, Vec2.TABLE))
    issues = lint.lint_level(Level([obj]), library)
    check(any("fractional position" in i.message for i in issues),
          "a fractional coordinate is reported")


def test_lint_clean_demo(project, library):
    """The shipped demo level should not contain any errors."""
    path = os.path.join(project.levels_path, "demo.lua")
    if not os.path.exists(path):
        return
    level = level_from_table(reader.parse_file(path))
    issues = lint.lint_level(level, library, project)
    errors = [i for i in issues if i.severity == lint.ERROR]
    check(not errors, f"demo.lua has no errors, got {[i.message for i in errors]}")


def test_real_file_round_trip(project):
    """Every level on disk must survive load -> save -> load unchanged."""
    for path in project.level_files():
        level = level_from_table(reader.parse_file(path))
        first = level_writer.write_level(level)
        second = level_writer.write_level(level_from_table(reader.parse(first)))
        check_equal(first, second, f"{os.path.basename(path)} round trips")


# -- tilemaps ----------------------------------------------------------------


def _tilemap_object(library, width=4, height=3, tiles=None):
    obj = LevelObject("Tilemap", Vec2(0.0, 0.0, Vec2.TABLE), object_id="tiles")
    binding = TilemapBinding(obj, library)
    binding.set("tileWidth", 16)
    binding.set("tileHeight", 16)
    binding.set("width", width)
    binding.set("height", height)
    binding.set("tiles", tiles if tiles is not None else [0] * (width * height))
    return obj, binding


def test_tilemap_paint(library):
    if library.find("Tilemap") is None:
        return
    _obj, binding = _tilemap_object(library)
    check(binding.paint(1, 2, 7), "painting an empty cell reports a change")
    check_equal(binding.tile_at(1, 2), 7, "the painted cell holds the tile")
    check(not binding.paint(1, 2, 7), "repainting the same value is a no-op")
    check(not binding.paint(99, 99, 7), "painting outside the map is refused")
    check_equal(binding.tile_at(0, 0), 0, "neighbouring cells are untouched")


def test_tilemap_row_major(library):
    """The editor and `Tilemap:GetTile` must agree on the index formula."""
    if library.find("Tilemap") is None:
        return
    _obj, binding = _tilemap_object(library, width=4, height=3)
    binding.paint(3, 0, 5)
    # row * width + col, 0-based, so (3, 0) is the fourth entry.
    check_equal(binding.tiles[3], 5, "column 3 of row 0 is index 3")
    binding.paint(0, 1, 6)
    check_equal(binding.tiles[4], 6, "column 0 of row 1 is index width")


def test_tilemap_resize_keeps_the_top_left(library):
    if library.find("Tilemap") is None:
        return
    _obj, binding = _tilemap_object(library, width=3, height=2,
                                    tiles=[1, 2, 3, 4, 5, 6])
    binding.resize(4, 3)
    check_equal(binding.tile_at(0, 0), 1, "the origin tile survives a grow")
    check_equal(binding.tile_at(2, 1), 6, "the far corner keeps its tile")
    check_equal(binding.tile_at(3, 2), 0, "new cells are empty")
    binding.resize(2, 2)
    check_equal(binding.tile_at(1, 1), 5, "shrinking keeps what still fits")
    check_equal(len(binding.tiles), 4, "the array matches the new size")


def test_tilemap_flood_fill(library):
    if library.find("Tilemap") is None:
        return
    _obj, binding = _tilemap_object(library, width=3, height=3,
                                    tiles=[0, 1, 0,
                                           0, 1, 0,
                                           0, 1, 0])
    binding.flood_fill(0, 0, 4)
    check_equal(binding.tiles[:3], [4, 1, 0], "the fill stops at the wall")
    check_equal(binding.tile_at(2, 0), 0, "the far side is not reached")


def test_tilemap_normalises_a_short_array(library):
    """A hand-edited file with too few values still reads as a rectangle."""
    if library.find("Tilemap") is None:
        return
    _obj, binding = _tilemap_object(library, width=4, height=2, tiles=[1, 2])
    check_equal(len(binding.tiles), 8, "the grid is padded to width * height")
    check_equal(binding.tile_at(0, 1), 0, "the padding is empty")


def test_tilemap_cell_at_world(library):
    """The editor's hit test must match `Tilemap:CellAt`: top-left origin."""
    if library.find("Tilemap") is None:
        return
    obj, binding = _tilemap_object(library, width=4, height=3)
    obj.position = Vec2(32.0, 16.0, Vec2.TABLE)
    check_equal(binding.cell_at_world(32.0, 16.0), (0, 0),
                "the object position is the corner of cell (0, 0)")
    check_equal(binding.cell_at_world(47.9, 16.0), (0, 0),
                "a point inside the first cell stays in it")
    check_equal(binding.cell_at_world(48.0, 32.0), (1, 1),
                "one tile right and down is cell (1, 1)")
    check(binding.cell_at_world(0.0, 0.0) is None,
          "a point before the origin is off the map")


def test_tilemap_writes_rows(library):
    """The grid is emitted one source line per map row, with its size."""
    if library.find("Tilemap") is None:
        return
    obj, binding = _tilemap_object(library, width=3, height=2,
                                   tiles=[1, 2, 3, 4, 5, 6])
    binding.set("tileset", "Resources/tilesets/cave.png")
    text = level_writer.write_level(Level([obj]))
    check("1, 2, 3," in text, "the first row is one line")
    check("4, 5, 6," in text, "the second row is the next line")
    check("-- 3 x 2" in text, "the dimensions are noted in the file")


def test_tilemap_round_trip(library):
    """Tile data must survive write -> parse -> write unchanged."""
    if library.find("Tilemap") is None:
        return
    obj, binding = _tilemap_object(library, width=4, height=2,
                                   tiles=[0, 1, 2, 3, 4, 5, 6, 0])
    binding.set("tileset", "Resources/tilesets/cave.png")
    first = level_writer.write_level(Level([obj]))
    second = level_writer.write_level(level_from_table(reader.parse(first)))
    check_equal(first, second, "a tilemap round trips")

    reloaded = TilemapBinding(level_from_table(reader.parse(first)).objects[0],
                              library)
    check_equal(reloaded.tiles, [0, 1, 2, 3, 4, 5, 6, 0],
                "the grid survives the round trip")
    check_equal(reloaded.width, 4, "so does the width")


def test_lint_tilemap_missing_tileset(library):
    if library.find("Tilemap") is None:
        return
    obj, _binding = _tilemap_object(library)
    issues = lint.lint_level(Level([obj]), library)
    check(any("no tileset" in i.message for i in issues),
          "a tilemap with no tileset is reported")


def test_lint_tilemap_size_mismatch(library):
    if library.find("Tilemap") is None:
        return
    obj, binding = _tilemap_object(library, width=4, height=4)
    binding.set("tiles", [1, 2, 3])
    issues = lint.lint_level(Level([obj]), library)
    check(any("tile array holds" in i.message for i in issues),
          "a short tile array is reported")


# -- runner ------------------------------------------------------------------


def main(argv=None):
    parser = argparse.ArgumentParser(prog="level_editor.tests.run_tests")
    parser.add_argument("--project", help="path to the RAY project root")
    args = parser.parse_args(argv)

    project = Project(args.project) if args.project else Project.discover(
        os.path.dirname(os.path.abspath(__file__)))

    test_parse()
    test_rejects_prefab_file()
    test_rejects_bad_syntax()
    test_round_trip()
    test_moving_drops_the_expression()
    test_only_overrides_are_written()
    test_rotation_absent_when_zero()
    test_unique_id()
    test_draw_order()

    if project is None or not os.path.exists(project.definitions_path):
        print("note: no project found, skipping the tests that need "
              "definitions.lua (pass --project)")
    else:
        library = library_from_table(reader.parse_file(project.definitions_path))
        test_resolution(library)
        test_resolution_does_not_mutate_the_prefab(library)
        test_scene_light(library)
        test_zero_cone_angle_is_not_a_full_burst(library)
        test_light_respects_position(library)
        test_lint_duplicate_ids(library)
        test_lint_unknown_prefab(library)
        test_lint_dangling_joint(library)
        test_lint_orphan_override(library)
        test_lint_fractional_position(library)
        test_lint_clean_demo(project, library)
        test_real_file_round_trip(project)
        test_tilemap_paint(library)
        test_tilemap_row_major(library)
        test_tilemap_resize_keeps_the_top_left(library)
        test_tilemap_flood_fill(library)
        test_tilemap_normalises_a_short_array(library)
        test_tilemap_cell_at_world(library)
        test_tilemap_writes_rows(library)
        test_tilemap_round_trip(library)
        test_lint_tilemap_missing_tileset(library)
        test_lint_tilemap_size_mismatch(library)

    if FAILURES:
        print(f"{len(FAILURES)} of {CHECKS[0]} checks failed:\n")
        for failure in FAILURES:
            print(f"  - {failure}")
        return 1

    print(f"all {CHECKS[0]} checks passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
