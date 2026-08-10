"""The light solution for a whole level, not a single prefab.

`raytrace.world_segments` already takes a position and a rotation, so the only
thing missing was the collection step: every object's LightCollider contributes
to one shared segment list, exactly as `LightWorld` accumulates them at runtime,
and then every object carrying a LightSource traces a fan through all of them.

This is the part that makes the tool worth having. A mirror in a level is not a
thing you can judge in isolation -- what matters is where the beam lands three
bounces later, and that is only visible once every collider in the room is in
the same list.
"""

from __future__ import annotations

import math

from ..model import level as level_model
from .raytrace import V, cast_fan, world_segments


def _number(value, fallback):
    """Read a numeric arg the way Lua's `args.x or default` actually behaves.

    Python and Lua disagree about zero. `args.coneAngle or math.pi * 2` in Lua
    keeps a coneAngle of 0 -- only nil and false are falsy there -- while the
    same idiom in Python silently replaces it with the default. A collimated
    emitter (`coneAngle = 0`, as in light_test_prefabs.lua) would have been
    drawn as a full 360-degree burst.
    """
    return float(fallback) if value is None else float(value)


class SceneLight:
    """The result of solving one level: segments, plus a fan per source."""

    __slots__ = ("segments", "fans")

    def __init__(self, segments, fans):
        self.segments = segments          # list[Segment], owner = LevelObject
        self.fans = fans                  # list[(LevelObject, list[RayNode])]

    def is_empty(self):
        return not self.segments and not self.fans


def collect_segments(level, library):
    """Every light segment in the level, in world space."""
    segments = []
    for obj in level.objects:
        resolved = level_model.resolve(obj, library)
        if resolved is None or resolved.find("LightCollider") is None:
            continue
        owned = world_segments(resolved, V(obj.x, obj.y), obj.angle(),
                               obj.world_scale())
        for segment in owned:
            # world_segments tags the prefab; the viewport wants the instance,
            # so it can highlight the segments of the selected object.
            segment.owner = obj
        segments.extend(owned)
    return segments


def solve(level, library, max_rays=4000):
    """Trace every LightSource in the level through every LightCollider.

    `max_rays` is a budget, not a correctness knob: a level with a dozen 64-ray
    sources would otherwise re-trace a few thousand rays on every mouse move.
    Sources are traced in list order and the budget stops the trace early, which
    is visible as a source simply not lighting rather than as a stall.
    """
    segments = collect_segments(level, library)

    fans = []
    spent = 0
    for obj in level.objects:
        resolved = level_model.resolve(obj, library)
        if resolved is None:
            continue
        source = resolved.find("LightSource")
        if source is None:
            continue

        ray_count = int(_number(source.get("rayCount"), 16))
        if ray_count < 2:
            ray_count = 2
        if spent + ray_count > max_rays:
            break
        spent += ray_count

        fan = cast_fan(
            segments,
            V(obj.x, obj.y),
            obj.angle(),
            ray_count=ray_count,
            cone_angle=_number(source.get("coneAngle"), 2 * math.pi),
            max_depth=int(_number(source.get("maxDepth"), 4)),
            min_intensity=_number(source.get("minIntensity"), 0.05),
        )
        fans.append((obj, fan))

    return SceneLight(segments, fans)


def detector_hits(level, library, scene_light):
    """Which LightDetector objects the current solution actually illuminates.

    Mirrors `LightWorld.resolveDetectors`: a detector fires when one of its own
    segments is the one a ray terminated on.
    """
    hit_owners = set()

    def walk(node):
        if node.segment is not None:
            hit_owners.add(id(node.segment.owner))
        if node.reflected is not None:
            walk(node.reflected)
        if node.refracted is not None:
            walk(node.refracted)

    for _obj, fan in scene_light.fans:
        for node in fan:
            walk(node)

    lit = []
    for obj in level.objects:
        resolved = level_model.resolve(obj, library)
        if resolved is None or resolved.find("LightDetector") is None:
            continue
        lit.append((obj, id(obj) in hit_owners))
    return lit
