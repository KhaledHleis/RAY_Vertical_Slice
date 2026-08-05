"""Author-time checks for the failure modes this engine actually has.

Every rule here corresponds to something that either crashes on load, silently
does nothing, or produces a body that looks wrong on screen. They are cheap to
run, so the editor runs the whole set on every edit.
"""

from __future__ import annotations

import math
import os

from ..model import schema

ERROR = "error"
WARNING = "warning"
INFO = "info"

_SEVERITY_ORDER = {ERROR: 0, WARNING: 1, INFO: 2}

# Box2D is tuned for shapes between these sizes, in metres.
BOX2D_MIN_METERS = 0.1
BOX2D_MAX_METERS = 10.0


class Issue:
    __slots__ = ("severity", "prefab", "component", "field", "message", "hint")

    def __init__(self, severity, prefab, message, component=None, field=None, hint=""):
        self.severity = severity
        self.prefab = prefab
        self.component = component
        self.field = field
        self.message = message
        self.hint = hint

    def location(self):
        parts = [self.prefab]
        if self.component:
            parts.append(self.component)
        if self.field:
            parts.append(self.field)
        return " / ".join(p for p in parts if p)

    def __repr__(self):
        return f"<{self.severity} {self.location()}: {self.message}>"


def lint_library(library, project=None):
    issues = []
    registered = project.registered_components() if project else None
    pixels_per_meter = project.pixels_per_meter() if project else 64.0

    seen_names = {}
    for prefab in library.prefabs:
        if prefab.name in seen_names:
            issues.append(Issue(
                ERROR, prefab.name,
                "Duplicate prefab name; the later definition silently wins.",
            ))
        seen_names[prefab.name] = prefab
        issues.extend(lint_prefab(prefab, registered, pixels_per_meter, project))

    issues.sort(key=lambda i: (_SEVERITY_ORDER[i.severity], i.prefab))
    return issues


def lint_prefab(prefab, registered=None, pixels_per_meter=64.0, project=None):
    issues = []
    body = prefab.find("RigidBody")
    light = prefab.find("LightCollider")
    sprite = prefab.find("SpriteRenderer")
    source = prefab.find("LightSource")

    _check_component_set(prefab, registered, issues)
    if body is not None:
        _check_body(prefab, body, pixels_per_meter, issues)
    if light is not None:
        _check_light_collider(prefab, light, body, issues)
    if sprite is not None:
        _check_sprite(prefab, sprite, body, project, issues)
    if source is not None:
        _check_light_source(prefab, source, issues)
    _check_cross_component(prefab, body, light, source, issues)
    return issues


# ---------------------------------------------------------------------------


def _check_component_set(prefab, registered, issues):
    if not prefab.components:
        issues.append(Issue(
            WARNING, prefab.name,
            "Prefab has no components; instantiating it produces an empty object.",
        ))

    seen = set()
    for component in prefab.components:
        spec = schema.spec_for(component.type)

        if component.type in seen:
            issues.append(Issue(
                ERROR, prefab.name,
                f"Two {component.type} components. Object:AddComponent keys by type, "
                f"so the second silently overwrites the first.",
                component=component.type,
            ))
        seen.add(component.type)

        if spec is None:
            issues.append(Issue(
                ERROR, prefab.name,
                f"Unknown component type {component.type!r}.",
                component=component.type,
            ))
            continue

        if not spec.allowed_in_prefab:
            issues.append(Issue(
                ERROR, prefab.name,
                f"{component.type} cannot live in a prefab.",
                component=component.type, hint=spec.reason,
            ))

        if registered is not None and component.type not in registered:
            issues.append(Issue(
                ERROR, prefab.name,
                f"{component.type} is not in component_registry.lua; "
                f"Prefab.Instantiate will assert on this prefab.",
                component=component.type,
                hint=f"Add `{component.type} = require('...')` to the registry.",
            ))


def _check_body(prefab, body, pixels_per_meter, issues):
    shape = body.get("shape", "rectangle")

    if shape == "circle":
        radius = body.get("radius")
        if radius is None or float(radius) <= 0:
            issues.append(Issue(
                ERROR, prefab.name,
                "shape is circle but radius is unset; RigidBody:OnAttach has no fallback.",
                component="RigidBody", field="radius",
            ))
            extents = []
        else:
            extents = [("radius", float(radius) * 2)]
    else:
        extents = [("width", float(body.get("width", 0) or 0)),
                   ("height", float(body.get("height", 0) or 0))]
        for name, value in extents:
            if value <= 0:
                issues.append(Issue(
                    ERROR, prefab.name,
                    f"{name} must be greater than zero.",
                    component="RigidBody", field=name,
                ))

    for name, pixels in extents:
        if pixels <= 0:
            continue
        meters = pixels / pixels_per_meter
        if meters < BOX2D_MIN_METERS:
            issues.append(Issue(
                WARNING, prefab.name,
                f"{name} is {pixels:g} px = {meters:.3f} m, below Box2D's tuned range. "
                f"Box2D's fixed collision skin will show as a visible resting gap.",
                component="RigidBody", field=name,
                hint=f"At {pixels_per_meter:g} px/m, keep extents above "
                     f"{BOX2D_MIN_METERS * pixels_per_meter:g} px.",
            ))
        elif meters > BOX2D_MAX_METERS:
            issues.append(Issue(
                WARNING, prefab.name,
                f"{name} is {pixels:g} px = {meters:.1f} m, above Box2D's tuned range; "
                f"expect solver jitter.",
                component="RigidBody", field=name,
                hint=f"Keep extents below {BOX2D_MAX_METERS * pixels_per_meter:g} px.",
            ))

    if float(body.get("density", 1) or 0) <= 0 and body.get("bodyType") == "dynamic":
        issues.append(Issue(
            WARNING, prefab.name,
            "A dynamic body with zero density gets no mass from this fixture.",
            component="RigidBody", field="density",
        ))

    if shape == "circle" and abs(float(body.get("angle", 0) or 0)) > 1e-9:
        issues.append(Issue(
            INFO, prefab.name,
            "angle has no effect on a circle shape.",
            component="RigidBody", field="angle",
        ))


def _check_light_collider(prefab, light, body, issues):
    segments = light.get("segments") or []

    if not segments:
        issues.append(Issue(
            WARNING, prefab.name,
            "LightCollider has no segments, so it blocks and reflects nothing.",
            component="LightCollider", field="segments",
        ))

    for index, segment in enumerate(segments):
        a, b = segment.get("a"), segment.get("b")
        if a is None or b is None:
            continue
        length = math.hypot(float(b.x) - float(a.x), float(b.y) - float(a.y))
        if length < 1e-6:
            issues.append(Issue(
                ERROR, prefab.name,
                f"Segment {index + 1} has zero length; segmentIntersect can never hit it.",
                component="LightCollider", field=f"segments[{index + 1}]",
            ))

        reflective = float(segment.get("reflective", 0) or 0)
        absorption = float(segment.get("absorption", 0) or 0)
        index_of_refraction = float(segment.get("refractiveIndex", 1) or 1)

        if reflective == 0 and absorption == 0 and index_of_refraction == 1:
            issues.append(Issue(
                WARNING, prefab.name,
                f"Segment {index + 1} is inert: it stops the ray but neither "
                f"reflects, refracts nor absorbs.",
                component="LightCollider", field=f"segments[{index + 1}]",
            ))

        if absorption >= 1 and reflective > 0:
            issues.append(Issue(
                INFO, prefab.name,
                f"Segment {index + 1} absorbs everything, so its reflectivity "
                f"produces a zero-intensity bounce.",
                component="LightCollider", field=f"segments[{index + 1}]",
            ))

    if body is not None and not light.get("dynamic"):
        if body.get("bodyType") in ("dynamic", "kinematic"):
            issues.append(Issue(
                ERROR, prefab.name,
                "LightCollider on a moving body without dynamic = true. The segments "
                "are computed once at spawn and stay frozen while the body moves.",
                component="LightCollider", field="dynamic",
                hint="Set dynamic = true so syncSegments runs every frame.",
            ))

    if body is not None and body.get("fixedRotation") and segments:
        issues.append(Issue(
            INFO, prefab.name,
            "fixedRotation locks the angle permanently, so these light segments can "
            "never change orientation in play.",
            component="RigidBody", field="fixedRotation",
            hint="Clear it for a tumbling mirror, or add a HingeJoint at level "
                 "scope for a pivoting one.",
        ))


def _check_sprite(prefab, sprite, body, project, issues):
    path = sprite.get("path")
    if not path:
        issues.append(Issue(
            ERROR, prefab.name,
            "SpriteRenderer has no path, so nothing is drawn.",
            component="SpriteRenderer", field="path",
        ))
        return

    size = None
    if project is not None:
        absolute = project.resolve(path)
        if not absolute or not os.path.exists(absolute):
            issues.append(Issue(
                ERROR, prefab.name,
                f"Sprite file not found: {path}",
                component="SpriteRenderer", field="path",
            ))
            return
        size = _image_size(absolute)

    frame_w = sprite.get("frameWidth")
    frame_h = sprite.get("frameHeight")
    if (frame_w is None) != (frame_h is None):
        issues.append(Issue(
            WARNING, prefab.name,
            "frameWidth and frameHeight must both be set for the quad to be built; "
            "with only one, SpriteRenderer falls back to the whole image.",
            component="SpriteRenderer",
        ))

    if size is None or body is None:
        return

    scale = sprite.get("scale")
    scale_x = float(scale.x) if scale is not None else 1.0
    scale_y = float(scale.y) if scale is not None else 1.0
    source_w = float(frame_w) if frame_w else size[0]
    source_h = float(frame_h) if frame_h else size[1]
    drawn = (abs(source_w * scale_x), abs(source_h * scale_y))

    if body.get("shape", "rectangle") == "circle":
        return

    body_w = float(body.get("width", 0) or 0)
    body_h = float(body.get("height", 0) or 0)
    if body_w <= 0 or body_h <= 0:
        return

    tolerance = 0.25
    if (abs(drawn[0] - body_w) > tolerance * max(drawn[0], body_w)
            or abs(drawn[1] - body_h) > tolerance * max(drawn[1], body_h)):
        issues.append(Issue(
            WARNING, prefab.name,
            f"Sprite draws at {drawn[0]:g}x{drawn[1]:g} px but the collider is "
            f"{body_w:g}x{body_h:g} px.",
            component="RigidBody",
            hint="Use Fit collider to sprite if the mismatch is unintentional.",
        ))


def _check_light_source(prefab, source, issues):
    ray_count = int(source.get("rayCount", 16) or 16)
    if ray_count < 2:
        issues.append(Issue(
            ERROR, prefab.name,
            "rayCount below 2 divides by zero in LightSource:Update "
            "(coneAngle * i / (rayCount - 1)).",
            component="LightSource", field="rayCount",
        ))

    cone = float(source.get("coneAngle", 2 * math.pi) or 0)
    if cone > 2 * math.pi + 1e-9:
        issues.append(Issue(
            WARNING, prefab.name,
            "coneAngle beyond 2pi makes rays overlap.",
            component="LightSource", field="coneAngle",
        ))

    if not prefab.has("GodrayRenderer") and not prefab.has("DebugLightRenderer"):
        issues.append(Issue(
            INFO, prefab.name,
            "LightSource with no GodrayRenderer or DebugLightRenderer: it will "
            "light detectors but stay invisible.",
            component="LightSource",
        ))


def _check_cross_component(prefab, body, light, source, issues):
    if prefab.has("GodrayRenderer") and source is None:
        issues.append(Issue(
            WARNING, prefab.name,
            "GodrayRenderer needs a LightSource on the same object; "
            "OnAttach finds none and it draws nothing.",
            component="GodrayRenderer",
        ))

    if prefab.has("LightDetector") and light is None:
        issues.append(Issue(
            WARNING, prefab.name,
            "LightDetector reports hits on its owner's light segments, but this "
            "prefab has no LightCollider, so it can never fire.",
            component="LightDetector",
        ))

    if prefab.has("CollisionRenderer") and body is None and light is None:
        issues.append(Issue(
            INFO, prefab.name,
            "CollisionRenderer has neither a RigidBody nor a LightCollider to draw.",
            component="CollisionRenderer",
        ))

    types = prefab.component_types()
    if "RigidBody" in types and "HingeJoint" in types:
        if types.index("HingeJoint") < types.index("RigidBody"):
            issues.append(Issue(
                ERROR, prefab.name,
                "HingeJoint is ordered before RigidBody; its OnAttach assert requires "
                "the body to exist first.",
                component="HingeJoint",
            ))


def _image_size(path):
    """Read a PNG/BMP/JPEG header without importing an image library."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(32)
            if head[:8] == b"\x89PNG\r\n\x1a\n":
                width = int.from_bytes(head[16:20], "big")
                height = int.from_bytes(head[20:24], "big")
                return (width, height)
    except OSError:
        return None
    return None
