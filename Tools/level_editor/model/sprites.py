"""Sprite footprint, read from the file header rather than an image library.

Kept separate from the viewport so the lint and the tests can ask how big a
sprite is without importing Qt.
"""

from __future__ import annotations

import os


def image_size(path):
    """(width, height) of a PNG, or None. No image library required."""
    try:
        with open(path, "rb") as handle:
            head = handle.read(32)
    except OSError:
        return None
    if head[:8] == b"\x89PNG\r\n\x1a\n":
        return (int.from_bytes(head[16:20], "big"),
                int.from_bytes(head[20:24], "big"))
    return None


def sprite_drawn_size(sprite, project):
    """The on-screen pixel size of a SpriteRenderer, or None if unknowable."""
    if sprite is None:
        return None
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
        size = image_size(absolute)
        if size is None:
            return None
        source = (float(size[0]), float(size[1]))

    scale = sprite.get("scale")
    scale_x = abs(float(scale.x)) if scale is not None else 1.0
    scale_y = abs(float(scale.y)) if scale is not None else 1.0
    return (source[0] * scale_x, source[1] * scale_y)


def object_extent(resolved, project):
    """Half-width and half-height of whatever an object visibly occupies.

    Used for picking and for the selection box. Falls back to a small square so
    that a bare Anchor -- 4 px of collider and nothing else -- is still large
    enough to click on.
    """
    half_w = half_h = 6.0
    if resolved is None:
        return half_w, half_h

    body = resolved.find("RigidBody")
    if body is not None:
        if body.get("shape", "rectangle") == "circle":
            radius = float(body.get("radius") or 0)
            half_w = max(half_w, radius)
            half_h = max(half_h, radius)
        else:
            half_w = max(half_w, float(body.get("width") or 0) / 2)
            half_h = max(half_h, float(body.get("height") or 0) / 2)

    size = sprite_drawn_size(resolved.find("SpriteRenderer"), project)
    if size:
        half_w = max(half_w, size[0] / 2)
        half_h = max(half_h, size[1] / 2)

    light = resolved.find("LightCollider")
    if light is not None:
        for segment in light.get("segments") or []:
            for key in ("a", "b"):
                point = segment.get(key)
                if point is not None:
                    half_w = max(half_w, abs(float(point.x)))
                    half_h = max(half_h, abs(float(point.y)))

    return half_w, half_h
