"""A faithful Python port of the engine's light propagation.

This mirrors, line for line, `Libraries/light_engine/utils/ray_math.lua`,
`LightWorld.raycast` and `LightSource:castRay`. Keeping the same epsilon, the
same normal-flipping rule and the same recursion order matters: the preview is
only useful if a bounce that appears in the editor also appears in the game.

If you change the Lua, change this too -- `tests/test_raytrace_parity.py`
cross-checks the two implementations with a real Lua interpreter when one is
available.
"""

from __future__ import annotations

import math

EPSILON = 1e-9
MAX_RAY_DISTANCE = 2000.0


class V:
    """Minimal 2D vector matching Libraries/transform/vector.lua."""

    __slots__ = ("x", "y")

    def __init__(self, x=0.0, y=0.0):
        self.x = float(x)
        self.y = float(y)

    def __add__(self, other):
        return V(self.x + other.x, self.y + other.y)

    def __sub__(self, other):
        return V(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar):
        return V(self.x * scalar, self.y * scalar)

    def dot(self, other):
        return self.x * other.x + self.y * other.y

    def cross(self, other):
        return self.x * other.y - self.y * other.x

    def length(self):
        return math.sqrt(self.x * self.x + self.y * self.y)

    def normalized(self):
        length = self.length()
        if length == 0:
            return V(0.0, 0.0)
        return V(self.x / length, self.y / length)

    def as_tuple(self):
        return (self.x, self.y)

    def __repr__(self):
        return f"V({self.x:.6g}, {self.y:.6g})"


class Segment:
    """A world-space light segment with its material parameters."""

    __slots__ = ("a", "b", "reflective", "refractive_index", "absorption", "owner")

    def __init__(self, a, b, reflective=0.0, refractive_index=1.0, absorption=0.0, owner=None):
        self.a = a
        self.b = b
        self.reflective = float(reflective)
        self.refractive_index = float(refractive_index)
        self.absorption = float(absorption)
        self.owner = owner


class RayNode:
    """One link in the ray tree, matching the `node` table in castRay."""

    __slots__ = ("origin", "direction", "intensity", "depth",
                 "hit_point", "segment", "reflected", "refracted")

    def __init__(self, origin, direction, intensity, depth):
        self.origin = origin
        self.direction = direction
        self.intensity = intensity
        self.depth = depth
        self.hit_point = None
        self.segment = None
        self.reflected = None
        self.refracted = None

    def end_point(self, fallback_length=MAX_RAY_DISTANCE):
        """Where to draw this ray to: the hit point, or off into the distance."""
        if self.hit_point is not None:
            return self.hit_point
        return self.origin + self.direction * fallback_length

    def walk(self):
        yield self
        if self.reflected is not None:
            yield from self.reflected.walk()
        if self.refracted is not None:
            yield from self.refracted.walk()


def segment_intersect(origin, direction, max_distance, a, b):
    """Ray/segment intersection. Returns (t, point, normal) or None."""
    edge = b - a
    denominator = direction.cross(edge)

    if abs(denominator) < EPSILON:
        return None

    q = a - origin
    t = q.cross(edge) / denominator
    u = q.cross(direction) / denominator

    if t <= EPSILON or t > max_distance or u < 0 or u > 1:
        return None

    hit_point = origin + direction * t
    normal = V(-edge.y, edge.x).normalized()
    if normal.dot(direction) > 0:
        normal = normal * -1

    return t, hit_point, normal


def reflect(direction, normal):
    return direction - normal * (2 * direction.dot(normal))


def refract(direction, normal, n1, n2):
    ratio = n1 / n2
    cos_i = -direction.dot(normal)
    sin2_t = ratio * ratio * (1 - cos_i * cos_i)
    if sin2_t > 1:
        return None  # total internal reflection
    cos_t = math.sqrt(1 - sin2_t)
    return direction * ratio + normal * (ratio * cos_i - cos_t)


def raycast(segments, origin, direction, max_distance=MAX_RAY_DISTANCE):
    """Closest hit among `segments`, matching LightWorld.raycast."""
    closest = None
    closest_t = max_distance
    for segment in segments:
        result = segment_intersect(origin, direction, closest_t, segment.a, segment.b)
        if result is None:
            continue
        t, point, normal = result
        closest = (t, point, normal, segment)
        closest_t = t
    return closest


def cast_ray(segments, origin, direction, intensity, depth,
             max_depth=4, min_intensity=0.05):
    """Recursive ray propagation, matching LightSource:castRay."""
    node = RayNode(origin, direction, intensity, depth)

    if depth >= max_depth or intensity < min_intensity:
        return node

    hit = raycast(segments, origin, direction)
    if hit is None:
        return node

    _, point, normal, segment = hit
    node.hit_point = point
    node.segment = segment

    remaining = intensity * (1 - segment.absorption)

    if segment.reflective > 0:
        node.reflected = cast_ray(
            segments, point, reflect(direction, normal),
            remaining * segment.reflective, depth + 1, max_depth, min_intensity,
        )

    if segment.refractive_index != 1:
        refracted_direction = refract(direction, normal, 1, segment.refractive_index)
        if refracted_direction is not None:
            node.refracted = cast_ray(
                segments, point, refracted_direction,
                remaining * (1 - segment.reflective), depth + 1, max_depth, min_intensity,
            )

    return node


def cast_fan(segments, position, base_angle, ray_count=16,
             cone_angle=2 * math.pi, max_depth=4, min_intensity=0.05):
    """The full fan a LightSource emits in one frame, matching LightSource:Update."""
    fan = []
    if ray_count < 2:
        ray_count = 2
    for index in range(ray_count):
        angle = base_angle - cone_angle / 2 + (cone_angle * index / (ray_count - 1))
        direction = V(math.cos(angle), math.sin(angle))
        fan.append(
            cast_ray(segments, position, direction, 1.0, 0, max_depth, min_intensity)
        )
    return fan


def world_segments(prefab, position=V(0.0, 0.0), rotation=0.0, scale=1.0):
    """Build world-space Segments from a prefab's LightCollider component.

    Mirrors LightCollider:syncSegments -- scale each local endpoint by the
    object's world scale, rotate it by the object's angle, then translate by
    its position. Unlike RigidBody, light segments are rebuilt every frame, so
    scale reaches them with no baking involved.
    """
    from ..model import schema  # local import keeps this module UI-free

    component = prefab.find("LightCollider")
    if component is None:
        return []

    cos_a, sin_a = math.cos(rotation), math.sin(rotation)
    defaults = {f.name: f.default for f in schema.SEGMENT_FIELDS}

    def to_world(vec):
        x, y = float(vec.x) * scale, float(vec.y) * scale
        return V(position.x + x * cos_a - y * sin_a,
                 position.y + x * sin_a + y * cos_a)

    result = []
    for segment in component.get("segments", []) or []:
        a = segment.get("a") or defaults["a"]
        b = segment.get("b") or defaults["b"]
        result.append(
            Segment(
                to_world(a),
                to_world(b),
                float(segment.get("reflective", 0.0) or 0.0),
                float(segment.get("refractiveIndex", 1.0) or 1.0),
                float(segment.get("absorption", 0.0) or 0.0),
                owner=prefab,
            )
        )
    return result
