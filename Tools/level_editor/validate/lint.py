"""Checks that encode things you would otherwise only find by running the game.

Every rule here corresponds to a specific line in the engine. Where that line is
an `assert`, the issue is an ERROR: the level will not load. Where the engine
silently does nothing useful instead, it is a WARNING -- those are the expensive
ones, because nothing tells you at runtime that the override you typed was
dropped on the floor.
"""

from __future__ import annotations

import math

from ..model import level as level_model
from ..model import schema
from ..model import tilemap as tilemap_model

ERROR = "error"
WARNING = "warning"
INFO = "info"

# Box2D is tuned for shapes between 0.1 and 10 metres. Outside that band bodies
# behave strangely -- most visibly, they come to rest slightly above the floor.
MIN_METERS = 0.1
MAX_METERS = 10.0


class Issue:
    def __init__(self, severity, message, index=None, obj=None, hint=None):
        self.severity = severity
        self.message = message
        self.index = index
        self.obj = obj
        self.hint = hint

    def location(self):
        if self.obj is None:
            return "level"
        label = self.obj.label()
        return f"[{self.index}] {label}" if self.index is not None else label

    def __repr__(self):
        return f"Issue({self.severity}, {self.location()}, {self.message!r})"


def lint_level(level, library=None, project=None):
    issues = []
    registered = project.registered_components() if project else set()
    pixels_per_meter = project.pixels_per_meter() if project else 64.0
    screen = project.screen_size() if project else (320, 240)

    _check_ids(level, issues)

    for index, obj in enumerate(level.objects):
        _check_prefab(level, obj, index, library, issues)
        _check_overrides(obj, index, library, issues)
        _check_extra_components(level, obj, index, library, registered, issues)
        _check_bounds(obj, index, screen, issues)
        _check_parent(level, obj, index, library, issues)
        _check_tilemap(obj, index, library, project, issues)

        resolved = level_model.resolve(obj, library) if library else None
        if resolved is not None:
            _check_resolved(obj, index, resolved, pixels_per_meter, issues)

    order = {ERROR: 0, WARNING: 1, INFO: 2}
    issues.sort(key=lambda i: (order.get(i.severity, 3),
                               i.index if i.index is not None else -1))
    return issues


# ---------------------------------------------------------------------------


def _check_ids(level, issues):
    seen = {}
    for index, obj in enumerate(level.objects):
        if not obj.id:
            continue
        if obj.id in seen:
            issues.append(Issue(
                ERROR,
                f"duplicate id '{obj.id}', already used by entry [{seen[obj.id]}]",
                index, obj,
                hint="Level.load builds objectsById by assignment, so the second "
                     "entry silently wins and any joint pointing here attaches "
                     "to the wrong object.",
            ))
        else:
            seen[obj.id] = index


def _check_parent(level, obj, index, library, issues):
    """The three ways parenting goes wrong, all caught before the game runs."""
    if not obj.parent:
        return

    parent = level.find_by_id(obj.parent)
    if parent is None:
        issues.append(Issue(
            ERROR, f"unknown parent id '{obj.parent}'", index, obj,
            hint="Level.load asserts on this; the level will not load.",
        ))
        return

    if parent is obj:
        issues.append(Issue(ERROR, "object is its own parent", index, obj))
        return

    # Walk up and see whether we come back round.
    seen = {id(obj)}
    node = parent
    while node is not None:
        if id(node) in seen:
            issues.append(Issue(
                ERROR, f"parent cycle through '{node.id or node.prefab}'", index, obj,
                hint="Transform:SetParent rejects cycles at load.",
            ))
            return
        seen.add(id(node))
        node = node.parent_object()

    # The rule: a child may not have a RigidBody. Box2D writes the transform of
    # anything with a body every frame, so a parented body has two writers.
    if library is not None:
        definition = library.find(obj.prefab)
        if definition is not None and definition.has("RigidBody"):
            issues.append(Issue(
                ERROR,
                f"'{obj.prefab}' has a RigidBody and cannot be a child",
                index, obj,
                hint="Box2D owns its transform. Use a HingeJoint to attach one "
                     "body to another, as the lamp does.",
            ))


def _check_prefab(level, obj, index, library, issues):
    if library is None:
        return
    if library.find(obj.prefab) is None:
        issues.append(Issue(
            ERROR, f"unknown prefab '{obj.prefab}'", index, obj,
            hint="Prefab.Instantiate asserts on this; the level will not load.",
        ))


def _check_overrides(obj, index, library, issues):
    if library is None:
        return
    definition = library.find(obj.prefab)
    if definition is None:
        return

    for component_type, values in obj.overrides.items():
        component = definition.find(component_type)
        if component is None:
            issues.append(Issue(
                WARNING,
                f"override for '{component_type}', which prefab '{obj.prefab}' "
                f"does not have",
                index, obj,
                hint="mergeArgs only walks the components the prefab declares, "
                     "so this whole block is ignored at runtime. Add the "
                     "component to the prefab, or use extraComponents.",
            ))
            continue

        spec = schema.spec_for(component_type)
        if spec is None:
            continue
        known = set(spec.field_map())
        for name in values:
            if name not in known:
                issues.append(Issue(
                    WARNING,
                    f"{component_type}.{name} is not an argument the engine reads",
                    index, obj,
                    hint="It will be merged into args and then ignored by "
                         f"{component_type}.new.",
                ))


def _check_extra_components(level, obj, index, library, registered, issues):
    for extra in obj.extra_components:
        if registered and extra.type not in registered:
            issues.append(Issue(
                ERROR,
                f"extra component '{extra.type}' is not in component_registry.lua",
                index, obj,
                hint="Level.load asserts on an unknown component type.",
            ))

        if library is not None:
            definition = library.find(obj.prefab)
            if definition is not None and definition.find(extra.type) is not None:
                issues.append(Issue(
                    WARNING,
                    f"'{extra.type}' is both on prefab '{obj.prefab}' and in "
                    f"extraComponents",
                    index, obj,
                    hint="Object:AddComponent keys by tostring(component), so "
                         "the second one replaces the first rather than stacking.",
                ))

        if extra.type == "HingeJoint":
            _check_hinge(level, obj, index, extra, library, issues)


def _check_hinge(level, obj, index, extra, library, issues):
    target_id = extra.args.get("connectedObjectId")
    if not target_id:
        issues.append(Issue(
            ERROR, "HingeJoint has no connectedObjectId", index, obj,
            hint="OnAttach indexes connectedObject:GetComponent, which fails on nil.",
        ))
    else:
        target = level.find_by_id(target_id)
        if target is None:
            issues.append(Issue(
                ERROR, f"HingeJoint points at unknown id '{target_id}'", index, obj,
                hint="Level.load asserts on an unresolved connectedObjectId.",
            ))
        elif library is not None:
            target_def = library.find(target.prefab)
            if target_def is not None and not target_def.has("RigidBody"):
                issues.append(Issue(
                    ERROR,
                    f"HingeJoint target '{target_id}' has no RigidBody",
                    index, obj,
                    hint="OnAttach asserts that the connected object carries one.",
                ))

    if library is not None:
        definition = library.find(obj.prefab)
        if definition is not None and not definition.has("RigidBody"):
            issues.append(Issue(
                ERROR,
                f"HingeJoint on '{obj.prefab}', which has no RigidBody",
                index, obj,
                hint="OnAttach asserts the owning object has one attached first.",
            ))

    anchor = extra.args.get("anchor")
    if anchor is None:
        issues.append(Issue(
            ERROR, "HingeJoint has no anchor", index, obj,
            hint="OnAttach reads anchor.x directly; nil crashes on attach.",
        ))
    else:
        distance = math.hypot(float(anchor.x) - obj.x, float(anchor.y) - obj.y)
        if distance > 400:
            issues.append(Issue(
                WARNING,
                f"HingeJoint anchor is {distance:.0f} px from the object",
                index, obj,
                hint="The anchor is in world pixels, not local. This far out the "
                     "body will swing from off-screen.",
            ))


def _check_tilemap(obj, index, library, project, issues):
    """Rules for a Tilemap object.

    The expensive one is the tileset path: `Tilemap.new` calls
    `love.graphics.newImage` straight from the argument, so a path that is
    merely wrong takes the game down on load rather than drawing nothing.
    """
    binding = tilemap_model.TilemapBinding(obj, library) if library else None
    if not binding:
        return

    if not binding.tileset:
        issues.append(Issue(
            WARNING, "tilemap has no tileset", index, obj,
            hint="Tilemap:Draw returns early without an image, so the grid "
                 "is invisible and the cells you paint go nowhere.",
        ))
    elif project is not None:
        import os
        absolute = project.resolve(binding.tileset)
        if not absolute or not os.path.exists(absolute):
            issues.append(Issue(
                ERROR, f"tileset '{binding.tileset}' is not on disk", index, obj,
                hint="Tilemap.new passes the path straight to "
                     "love.graphics.newImage, which errors on a missing file.",
            ))

    if binding.width <= 0 or binding.height <= 0:
        issues.append(Issue(
            INFO, f"tilemap is {binding.width} x {binding.height} cells",
            index, obj, hint="An empty grid draws nothing. Set the map size "
                             "in the Tiles panel.",
        ))
        return

    declared = binding.width * binding.height
    raw = binding.get("tiles") or []
    if len(raw) != declared:
        issues.append(Issue(
            WARNING,
            f"tile array holds {len(raw)} values for a {binding.width} x "
            f"{binding.height} grid ({declared} cells)",
            index, obj,
            hint="The editor pads or trims on read, so saving will rewrite "
                 "the array to match. Check the map size is the one you meant.",
        ))

    if obj.rotation:
        issues.append(Issue(
            WARNING, "tilemap has a rotation", index, obj,
            hint="The engine rotates the batch, but neither Tilemap:CellAt nor "
                 "the editor's brush accounts for it, so painting will land in "
                 "the wrong cells.",
        ))

    count = tilemap_model.tileset_tile_count(binding, project)
    if count:
        highest = max(binding.tiles) if binding.tiles else 0
        if highest > count:
            issues.append(Issue(
                WARNING,
                f"tile id {highest} is past the end of a {count}-tile sheet",
                index, obj,
                hint="_quadFor builds a quad outside the image, which draws "
                     "as a transparent or smeared cell depending on the driver.",
            ))


def _check_bounds(obj, index, screen, issues):
    width, height = screen
    margin = 64
    if not (-margin <= obj.x <= width + margin and -margin <= obj.y <= height + margin):
        issues.append(Issue(
            INFO,
            f"sits at ({obj.x:g}, {obj.y:g}), outside the {width}x{height} screen",
            index, obj,
            hint="There is no camera, so nothing here will ever be visible.",
        ))

    if obj.x != int(obj.x) or obj.y != int(obj.y):
        issues.append(Issue(
            WARNING,
            f"fractional position ({obj.x:g}, {obj.y:g})",
            index, obj,
            hint="At this resolution a fractional coordinate shows up as a "
                 "shimmering half-pixel seam.",
        ))


def _check_resolved(obj, index, resolved, pixels_per_meter, issues):
    body = resolved.find("RigidBody")
    light = resolved.find("LightCollider")
    source = resolved.find("LightSource")

    if body is not None and body.get("shape", "rectangle") != "circle":
        for name in ("width", "height"):
            value = float(body.get(name) or 0)
            if value <= 0:
                continue
            meters = value / pixels_per_meter
            if meters < MIN_METERS or meters > MAX_METERS:
                issues.append(Issue(
                    WARNING,
                    f"resolved RigidBody {name} is {value:g} px "
                    f"({meters:.2f} m), outside Box2D's 0.1-10 m band",
                    index, obj,
                    hint="Most visibly this makes the body rest slightly above "
                         "whatever it lands on.",
                ))

    if body is not None and light is not None:
        is_dynamic = body.get("bodyType", "dynamic") != "static"
        if is_dynamic and not light.get("dynamic", False):
            issues.append(Issue(
                WARNING,
                "moving body carries light segments but LightCollider.dynamic "
                "is false",
                index, obj,
                hint="syncSegments runs once at spawn, so the light surface "
                     "stays behind while the object falls.",
            ))

    if source is not None:
        ray_count = int(source.get("rayCount") or 0)
        if ray_count < 2:
            issues.append(Issue(
                ERROR,
                f"resolved LightSource rayCount is {ray_count}",
                index, obj,
                hint="LightSource:Update divides by (rayCount - 1).",
            ))

    if resolved.has("GodrayRenderer") and source is None:
        issues.append(Issue(
            WARNING, "GodrayRenderer with no LightSource on the same object",
            index, obj, hint="It has no fan to fill and draws nothing.",
        ))
