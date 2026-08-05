"""One-click derivations between components.

These exist because doing them by hand is tedious enough that you end up not
making light-reactive props at all.
"""

from __future__ import annotations

import os

from ..luaio.types import Vec2
from ..validate.lint import _image_size


def sprite_drawn_size(sprite, project):
    """The on-screen pixel size of a SpriteRenderer, or None if unknowable."""
    path = sprite.get("path")
    if not path or project is None:
        return None

    frame_w = sprite.get("frameWidth")
    frame_h = sprite.get("frameHeight")
    if frame_w and frame_h:
        source = (float(frame_w), float(frame_h))
    else:
        absolute = project.resolve(path)
        if not absolute or not os.path.exists(absolute):
            return None
        size = _image_size(absolute)
        if size is None:
            return None
        source = (float(size[0]), float(size[1]))

    scale = sprite.get("scale")
    scale_x = abs(float(scale.x)) if scale is not None else 1.0
    scale_y = abs(float(scale.y)) if scale is not None else 1.0
    return (source[0] * scale_x, source[1] * scale_y)


def fit_collider_to_sprite(prefab, project):
    """Resize the RigidBody rectangle to match the drawn sprite footprint."""
    sprite = prefab.find("SpriteRenderer")
    body = prefab.find("RigidBody")
    if sprite is None or body is None:
        return False, "Needs both a SpriteRenderer and a RigidBody."

    size = sprite_drawn_size(sprite, project)
    if size is None:
        return False, "Could not determine the sprite's pixel size."

    if body.get("shape", "rectangle") == "circle":
        body.set("radius", round(max(size) / 2.0, 4))
    else:
        body.set("width", round(size[0], 4))
        body.set("height", round(size[1], 4))

    # The sprite's offset is applied in world space by SpriteRenderer:Draw,
    # so only mirror it into the collider when the body is axis aligned.
    offset = sprite.get("offset")
    if offset is not None and (float(offset.x) or float(offset.y)):
        body.set("offset", Vec2(float(offset.x), float(offset.y), Vec2.TABLE))

    return True, f"Collider fitted to {size[0]:g} x {size[1]:g} px."


def segments_from_collider(prefab, reflective=1.0, absorption=0.0,
                           refractive_index=1.0, faces="all"):
    """Emit light segments tracing the RigidBody rectangle's edges.

    `faces` is "all" for the full box or "top" for a single upward surface,
    which is what a flat mirror usually wants.
    """
    body = prefab.find("RigidBody")
    light = prefab.find("LightCollider")
    if body is None:
        return False, "Needs a RigidBody to derive edges from."
    if light is None:
        return False, "Needs a LightCollider to write the segments into."
    if body.get("shape", "rectangle") == "circle":
        return False, "Circle colliders have no edges; add segments manually."

    half_w = float(body.get("width", 0) or 0) / 2.0
    half_h = float(body.get("height", 0) or 0) / 2.0
    if half_w <= 0 or half_h <= 0:
        return False, "Collider has no size."

    offset = body.get("offset")
    cx = float(offset.x) if offset is not None else 0.0
    cy = float(offset.y) if offset is not None else 0.0

    top_left = Vec2(cx - half_w, cy - half_h, Vec2.CALL)
    top_right = Vec2(cx + half_w, cy - half_h, Vec2.CALL)
    bottom_right = Vec2(cx + half_w, cy + half_h, Vec2.CALL)
    bottom_left = Vec2(cx - half_w, cy + half_h, Vec2.CALL)

    if faces == "top":
        edges = [(top_left, top_right)]
    else:
        edges = [
            (top_left, top_right),
            (top_right, bottom_right),
            (bottom_right, bottom_left),
            (bottom_left, top_left),
        ]

    segments = []
    for a, b in edges:
        segments.append({
            "a": a,
            "b": b,
            "reflective": float(reflective),
            "refractiveIndex": float(refractive_index),
            "absorption": float(absorption),
            "_explicit": {"a", "b", "reflective", "absorption"},
        })

    light.set("segments", segments)
    if prefab.find("RigidBody").get("bodyType") in ("dynamic", "kinematic"):
        light.set("dynamic", True)
    return True, f"Generated {len(segments)} segment(s) from the collider."


def new_segment(after=None):
    """A fresh horizontal segment, placed below the previous one if given."""
    y = 0.0
    if after is not None:
        y = max(float(after["a"].y), float(after["b"].y)) + 16.0
    return {
        "a": Vec2(-32.0, y, Vec2.CALL),
        "b": Vec2(32.0, y, Vec2.CALL),
        "reflective": 1.0,
        "refractiveIndex": 1.0,
        "absorption": 0.0,
        "_explicit": {"a", "b", "reflective"},
    }
