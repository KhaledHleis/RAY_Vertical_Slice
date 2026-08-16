"""The single source of truth for what a component looks like.

Every entry here mirrors a `Component.new(args)` signature in the engine. This
one table drives the Add Component menu, the property inspector widgets, the
default values, the "is this field still default" check used by the writer, and
the lint rules. Adding a new engine component means adding one entry below and
touching no UI code at all.

Keep the field defaults identical to the `args.x or <default>` fallbacks in the
Lua source -- the writer relies on them to decide what it can leave out.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Optional

from ..luaio.types import Vec2

# Field kinds understood by the inspector widget factory.
NUMBER = "number"
INTEGER = "integer"
BOOLEAN = "boolean"
STRING = "string"
PATH = "path"
ENUM = "enum"
VEC2 = "vec2"
COLOR = "color"
SEGMENTS = "segments"
STRING_LIST = "string_list"
TILES = "tiles"

# Gizmo kinds understood by the viewport.
GIZMO_SPRITE = "sprite"
GIZMO_BODY = "body"
GIZMO_SEGMENTS = "segments"
GIZMO_LIGHT = "light"
GIZMO_DETECTOR = "detector"
GIZMO_TILEMAP = "tilemap"


@dataclass
class Field:
    name: str
    kind: str
    default: Any = None
    label: Optional[str] = None
    minimum: Optional[float] = None
    maximum: Optional[float] = None
    step: float = 1.0
    decimals: int = 3
    options: Optional[list] = None
    suffix: str = ""
    tooltip: str = ""
    visible_if: Optional[Callable[[dict], bool]] = None
    optional: bool = False

    def display_label(self):
        return self.label or self.name

    def is_visible(self, args):
        return self.visible_if is None or self.visible_if(args)

    def make_default(self):
        if isinstance(self.default, Vec2):
            return self.default.copy()
        if isinstance(self.default, list):
            return list(self.default)
        return self.default


@dataclass
class ComponentSpec:
    name: str
    fields: list = field(default_factory=list)
    gizmos: list = field(default_factory=list)
    allowed_in_prefab: bool = True
    reason: str = ""
    doc: str = ""

    def field_map(self):
        return {f.name: f for f in self.fields}

    def defaults(self):
        return {f.name: f.make_default() for f in self.fields}


def _is_rectangle(args):
    return args.get("shape", "rectangle") != "circle"


def _is_circle(args):
    return args.get("shape", "rectangle") == "circle"


def _uses_atlas(args):
    return args.get("frameWidth") is not None or args.get("frameHeight") is not None


SEGMENT_FIELDS = [
    Field("a", VEC2, Vec2(-32.0, 0.0), label="Start",
          tooltip="Local-space endpoint, relative to the object origin."),
    Field("b", VEC2, Vec2(32.0, 0.0), label="End",
          tooltip="Local-space endpoint, relative to the object origin."),
    Field("reflective", NUMBER, 0.0, minimum=0.0, maximum=1.0, step=0.05,
          tooltip="Fraction of remaining intensity bounced off this surface."),
    Field("refractiveIndex", NUMBER, 1.0, minimum=0.1, maximum=4.0, step=0.05,
          label="Refractive index",
          tooltip="1.0 disables refraction entirely. Glass is around 1.5."),
    Field("absorption", NUMBER, 0.0, minimum=0.0, maximum=1.0, step=0.05,
          tooltip="Fraction of intensity swallowed on contact."),
]


COMPONENTS = {
    "SpriteRenderer": ComponentSpec(
        name="SpriteRenderer",
        doc="Draws an image centred on the transform, rotated by its angle.",
        gizmos=[GIZMO_SPRITE],
        fields=[
            Field("path", PATH, None, tooltip="Path relative to the project root."),
            Field("offset", VEC2, Vec2(0.0, 0.0),
                  tooltip="Shifts the drawn image away from the transform origin."),
            Field("scale", VEC2, Vec2(1.0, 1.0), step=0.5,
                  tooltip="Pixel-art sprites are usually scaled by a whole number."),
            Field("color", COLOR, [1.0, 1.0, 1.0, 1.0], label="Tint"),
            Field("frameWidth", INTEGER, None, optional=True, minimum=1,
                  label="Frame width", tooltip="Set both frame sizes to use a sprite atlas."),
            Field("frameHeight", INTEGER, None, optional=True, minimum=1,
                  label="Frame height"),
            Field("frameX", INTEGER, 0, minimum=0, label="Frame column",
                  visible_if=_uses_atlas),
            Field("frameY", INTEGER, 0, minimum=0, label="Frame row",
                  visible_if=_uses_atlas),
        ],
    ),
    "Tilemap": ComponentSpec(
        name="Tilemap",
        doc=("A grid of tiles from one tileset, drawn as a single SpriteBatch. "
             "The transform position is the TOP-LEFT of cell (0, 0), not the "
             "centre -- a map that grew from the middle would move every tile "
             "in it each time you widened it. Registers nothing with the "
             "physics world or LightWorld: collision and light segments stay "
             "hand-placed."),
        gizmos=[GIZMO_TILEMAP],
        fields=[
            Field("tileset", PATH, None, label="Tileset",
                  tooltip="Tileset image, project-relative."),
            Field("tileWidth", INTEGER, 16, minimum=1, label="Tile width",
                  suffix=" px"),
            Field("tileHeight", INTEGER, 16, minimum=1, label="Tile height",
                  suffix=" px"),
            Field("columns", INTEGER, None, optional=True, minimum=1,
                  label="Tileset columns",
                  tooltip="Tiles per row in the source image. Derived from the "
                          "image width when empty; set it only for a sheet with "
                          "padding."),
            Field("width", INTEGER, 0, minimum=0, label="Map width",
                  suffix=" tiles"),
            Field("height", INTEGER, 0, minimum=0, label="Map height",
                  suffix=" tiles"),
            Field("color", COLOR, [1.0, 1.0, 1.0, 1.0], label="Tint"),
            Field("tiles", TILES, [],
                  tooltip="Row-major, 0 = empty, 1 = first tile in the sheet."),
        ],
    ),
    "RigidBody": ComponentSpec(
        name="RigidBody",
        doc="A Box2D body plus one fixture. Sizes are in game pixels.",
        gizmos=[GIZMO_BODY],
        fields=[
            Field("bodyType", ENUM, "dynamic", label="Body type",
                  options=["static", "dynamic", "kinematic"]),
            Field("shape", ENUM, "rectangle", options=["rectangle", "circle"]),
            Field("width", NUMBER, 16.0, minimum=0.0, suffix=" px",
                  visible_if=_is_rectangle),
            Field("height", NUMBER, 16.0, minimum=0.0, suffix=" px",
                  visible_if=_is_rectangle),
            Field("radius", NUMBER, None, minimum=0.0, suffix=" px", optional=True,
                  visible_if=_is_circle,
                  tooltip="Required when shape is circle; there is no fallback."),
            Field("offset", VEC2, Vec2(0.0, 0.0),
                  tooltip="Moves the collider inside the body, away from the sprite pivot."),
            Field("angle", NUMBER, 0.0, suffix=" rad", step=0.05,
                  tooltip="Tilts the collider inside the body. Rectangles only."),
            Field("density", NUMBER, 1.0, minimum=0.0),
            Field("friction", NUMBER, 0.3, minimum=0.0, maximum=1.0, step=0.05),
            Field("restitution", NUMBER, 0.0, minimum=0.0, maximum=1.0, step=0.05,
                  label="Restitution", tooltip="Bounciness. 0 is a dead stop."),
            Field("fixedRotation", BOOLEAN, False, label="Fixed rotation",
                  tooltip="Locks the angle permanently. No torque can ever turn it."),
            Field("sensor", BOOLEAN, False, label="Sensor",
                  tooltip="A trigger volume: overlaps are reported on the EventBus "
                          "but never solved, so nothing is pushed and nothing stops."),
        ],
    ),
    "LightCollider": ComponentSpec(
        name="LightCollider",
        doc="Line segments that light can reflect off, refract through or be absorbed by.",
        gizmos=[GIZMO_SEGMENTS],
        fields=[
            Field("dynamic", BOOLEAN, False,
                  tooltip="Recompute world segments every frame. Required if the object moves."),
            Field("segments", SEGMENTS, []),
        ],
    ),
    "LightSource": ComponentSpec(
        name="LightSource",
        doc="Casts a fan of rays, recursing through reflections and refractions.",
        gizmos=[GIZMO_LIGHT],
        fields=[
            Field("rayCount", INTEGER, 16, minimum=2, maximum=256, label="Ray count"),
            Field("coneAngle", NUMBER, 2.0 * math.pi, minimum=0.0,
                  maximum=2.0 * math.pi, step=0.05, suffix=" rad", label="Cone angle"),
            Field("maxDepth", INTEGER, 4, minimum=1, maximum=16, label="Max bounces"),
            Field("minIntensity", NUMBER, 0.05, minimum=0.0, maximum=1.0, step=0.01,
                  label="Min intensity", tooltip="Rays dimmer than this stop propagating."),
        ],
    ),
    "LightDetector": ComponentSpec(
        name="LightDetector",
        doc=("Fires OnHit/OnLost when the owner's light segments are struck, and "
             "swaps the sibling renderer between a dark and a lit sprite. Declare "
             "the SpriteRenderer first -- the target is resolved on attach."),
        gizmos=[GIZMO_DETECTOR],
        fields=[
            Field("channel", STRING, None, label="Channel",
                  tooltip="Name other systems filter on. A Door with the same "
                          "channel opens for this detector; a Door with no "
                          "channel opens for any of them."),
            Field("litSprite", PATH, None, label="Lit sprite",
                  tooltip="Swapped in while light is landing on this object."),
            Field("unlitSprite", PATH, None, label="Unlit sprite",
                  tooltip="Swapped back in when the light is lost. Defaults to "
                          "whatever the SpriteRenderer already draws."),
            Field("litColor", COLOR, None, label="Lit tint", optional=True),
            Field("unlitColor", COLOR, None, label="Unlit tint", optional=True),
        ],
    ),
    "Door": ComponentSpec(
        name="Door",
        doc=("Opens when a matching LightDetector lights up, and loads the next "
             "level when the player walks into the open doorway. Needs a sibling "
             "AnimationPlayer declared before it, and a sensor RigidBody for the "
             "doorway trigger."),
        fields=[
            Field("channel", STRING, None, label="Channel",
                  tooltip="Only detectors carrying this channel open the door. "
                          "Empty means any detector will."),
            Field("openClip", STRING, "DoorOpen", label="Open clip"),
            Field("closeClip", STRING, None, label="Close clip",
                  tooltip="Played on closing. With none, closing snaps back to "
                          "the first frame of the open clip."),
            Field("autoClose", BOOLEAN, False, label="Auto close",
                  tooltip="Shut again when the last matching detector goes dark."),
            Field("startsOpen", BOOLEAN, False, label="Starts open"),
            Field("nextLevel", STRING, None, label="Next level",
                  tooltip="Module path loaded on entry, e.g. "
                          "Frontend.levels.level_complete. Empty for a door that "
                          "is only a gate."),
            Field("requireInput", BOOLEAN, False, label="Require up",
                  tooltip="Wait for up/W instead of firing on contact."),
            Field("trigger", STRING, "PlayerController", label="Trigger component",
                  tooltip="Component that marks an object as 'the player'."),
            Field("animator", STRING, "AnimationPlayer", label="Animator",
                  tooltip="Sibling component playing the door clips."),
        ],
    ),
    "GodrayRenderer": ComponentSpec(
        name="GodrayRenderer",
        doc="Fills the volume between adjacent rays of a LightSource on the same object.",
        fields=[],
    ),
    "CollisionRenderer": ComponentSpec(
        name="CollisionRenderer",
        doc="Debug overlay drawing the RigidBody outline and light segments.",
        fields=[],
    ),
    "DebugLightRenderer": ComponentSpec(
        name="DebugLightRenderer",
        doc="Debug overlay colouring segments by material and drawing raw ray lines.",
        fields=[],
    ),
    "AnimationPlayer": ComponentSpec(
        name="AnimationPlayer",
        doc=("Advances a clip and writes frames into a sibling renderer. "
             "Declare the renderer first -- the target is resolved on attach."),
        fields=[
            Field("clips", STRING_LIST, [], label="Clips",
                  tooltip="Clip names from Frontend/animations/definitions.lua, "
                          "resolved up front so a missing sheet fails on load."),
            Field("autoPlay", STRING, None, label="Auto play",
                  tooltip="Clip to start on attach. Leave empty to start stopped."),
            Field("target", STRING, "SpriteRenderer",
                  tooltip="Sibling component receiving frames. Needs SetSheet and SetFrame."),
            Field("speed", NUMBER, 1.0, minimum=0.0, step=0.1,
                  tooltip="Playback multiplier, on top of the clip's own speed."),
        ],
    ),
    "HingeJoint": ComponentSpec(
        name="HingeJoint",
        allowed_in_prefab=False,
        reason=(
            "HingeJoint needs a live object reference (connectedObject), which only "
            "Level.load resolves from extraComponents + connectedObjectId. A prefab-level "
            "HingeJoint fails the assert in OnAttach. Add it to the level instead."
        ),
        doc="Revolute joint pinning this body to another.",
        fields=[
            Field("anchor", VEC2, Vec2(0.0, 0.0)),
            Field("enableLimit", BOOLEAN, False, label="Enable limit"),
            Field("lowerAngle", NUMBER, 0.0, suffix=" rad", label="Lower angle"),
            Field("upperAngle", NUMBER, 0.0, suffix=" rad", label="Upper angle"),
            Field("enableMotor", BOOLEAN, False, label="Enable motor"),
            Field("motorSpeed", NUMBER, 0.0, label="Motor speed"),
            Field("maxMotorTorque", NUMBER, 0.0, label="Max motor torque"),
        ],
    ),
}


def spec_for(component_type):
    return COMPONENTS.get(component_type)


def prefab_component_types():
    """Component types that may legally appear inside a prefab definition."""
    return [name for name, spec in COMPONENTS.items() if spec.allowed_in_prefab]
