"""The preview canvas: sprite, gizmos, draggable handles and a live light trace.

Coordinate spaces, in order:

    local   -- what you type into the prefab (collider offset, segment endpoints)
    world   -- local rotated by the preview rotation; where light is traced
    screen  -- world scaled by zoom and shifted by pan

One subtlety is faithfully reproduced rather than tidied up: `SpriteRenderer`
applies its `offset` in *world* space (`pos.x + offset.x`, before the rotation
is applied around the image centre), while a `RigidBody` offset is a Box2D shape
offset in *body-local* space and a `LightCollider` segment is rotated by
`syncSegments`. So the sprite offset does not orbit the origin when you rotate
the preview, and the other two do. That is what the engine does today.
"""

from __future__ import annotations

import math
import os

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
                         QPixmap, QPolygonF, QTransform)
from PyQt6.QtWidgets import QWidget

from ..luaio.types import Vec2
from ..model import generators, schema
from ..preview import raytrace
from ..preview.raytrace import V

BACKGROUND = QColor(24, 24, 28)
GRID_MINOR = QColor(40, 40, 48)
GRID_MAJOR = QColor(56, 56, 66)
AXIS = QColor(90, 90, 104)
ORIGIN = QColor(230, 230, 120)
BODY_COLOR = QColor(0, 235, 60)
BODY_FILL = QColor(0, 235, 60, 26)
HANDLE_FILL = QColor(255, 255, 255)
HANDLE_EDGE = QColor(20, 20, 20)
SPRITE_BOUNDS = QColor(150, 150, 210, 120)
RAY_COLOR = QColor(255, 255, 150, 170)
GODRAY_COLOR = QColor(255, 255, 230)
PROBE_COLOR = QColor(255, 200, 80)

# Matches Libraries/renderer/debug_light_renderer.lua so the editor and the
# in-game debug overlay agree at a glance.
MIRROR_COLOR = QColor(230, 230, 50)
GLASS_COLOR = QColor(75, 150, 255)
ABSORBER_COLOR = QColor(205, 50, 50)
INERT_COLOR = QColor(220, 220, 220)


def segment_color(segment):
    if float(segment.get("refractiveIndex", 1) or 1) != 1:
        return GLASS_COLOR
    if float(segment.get("reflective", 0) or 0) > 0:
        return MIRROR_COLOR
    if float(segment.get("absorption", 0) or 0) > 0:
        return ABSORBER_COLOR
    return INERT_COLOR


class Handle:
    """A draggable dot in world space."""

    __slots__ = ("key", "position", "on_drag", "color", "shape", "radius", "cursor")

    def __init__(self, key, position, on_drag, color=None, shape="square",
                 radius=4.5, cursor=Qt.CursorShape.SizeAllCursor):
        self.key = key
        self.position = position
        self.on_drag = on_drag
        self.color = color or HANDLE_FILL
        self.shape = shape
        self.radius = radius
        self.cursor = cursor


class Viewport(QWidget):
    modelChanged = pyqtSignal()
    editStarted = pyqtSignal()
    selectionChanged = pyqtSignal(object)
    statusMessage = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(420, 340)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.project = None
        self.prefab = None

        self.zoom = 2.0
        self.pan = QPointF(0.0, 0.0)
        self.preview_rotation = 0.0

        self.show_grid = True
        self.snap_enabled = True
        self.snap_step = 1.0
        self.show_sprite = True
        self.show_body = True
        self.show_segments = True
        self.show_light = True
        self.show_godrays = True

        self.probe_enabled = True
        self.probe_position = V(-140.0, -40.0)
        self.probe_angle = 0.35
        self.probe_ray_count = 24
        self.probe_cone = math.pi / 6
        self.probe_depth = 5

        self._handles = []
        self._active_handle = None
        self._hover_handle = None
        self._panning = False
        self._last_mouse = QPoint()
        self._pixmap_cache = {}
        self.selected_segment = None

    # -- external API ------------------------------------------------------

    def set_project(self, project):
        self.project = project
        self._pixmap_cache.clear()
        self.update()

    def set_prefab(self, prefab):
        self.prefab = prefab
        self.selected_segment = None
        self.update()

    def frame_content(self):
        """Zoom and centre so the prefab's extents fill the view."""
        extents = self._content_extent()
        if extents is None:
            self.zoom, self.pan = 2.0, QPointF(0.0, 0.0)
        else:
            half_w, half_h = extents
            margin = 1.35
            zoom_x = self.width() / max(1.0, half_w * 2 * margin)
            zoom_y = self.height() / max(1.0, half_h * 2 * margin)
            # Cap the zoom: filling the view with a 4 px anchor is disorienting,
            # and the light probe usually sits well outside the prefab bounds.
            self.zoom = max(0.25, min(6.0, min(zoom_x, zoom_y)))
            self.pan = QPointF(0.0, 0.0)
        self.update()

    def _content_extent(self):
        if self.prefab is None:
            return None
        half_w = half_h = 24.0
        body = self.prefab.find("RigidBody")
        if body is not None:
            if body.get("shape", "rectangle") == "circle":
                radius = float(body.get("radius") or 0)
                half_w = max(half_w, radius)
                half_h = max(half_h, radius)
            else:
                half_w = max(half_w, float(body.get("width") or 0) / 2)
                half_h = max(half_h, float(body.get("height") or 0) / 2)
        sprite = self.prefab.find("SpriteRenderer")
        if sprite is not None and self.project is not None:
            size = generators.sprite_drawn_size(sprite, self.project)
            if size:
                half_w = max(half_w, size[0] / 2)
                half_h = max(half_h, size[1] / 2)
        light = self.prefab.find("LightCollider")
        if light is not None:
            for segment in light.get("segments") or []:
                for key in ("a", "b"):
                    point = segment.get(key)
                    if point is not None:
                        half_w = max(half_w, abs(float(point.x)))
                        half_h = max(half_h, abs(float(point.y)))
        if self.probe_enabled and self.show_light:
            half_w = max(half_w, abs(self.probe_position.x))
            half_h = max(half_h, abs(self.probe_position.y))
        return half_w, half_h

    # -- transforms --------------------------------------------------------

    def _center(self):
        return QPointF(self.width() / 2.0, self.height() / 2.0)

    def local_to_world(self, x, y):
        cos_a, sin_a = math.cos(self.preview_rotation), math.sin(self.preview_rotation)
        return V(x * cos_a - y * sin_a, x * sin_a + y * cos_a)

    def world_to_local(self, x, y):
        cos_a, sin_a = math.cos(-self.preview_rotation), math.sin(-self.preview_rotation)
        return V(x * cos_a - y * sin_a, x * sin_a + y * cos_a)

    def world_to_screen(self, point):
        center = self._center()
        return QPointF(center.x() + self.pan.x() + point.x * self.zoom,
                       center.y() + self.pan.y() + point.y * self.zoom)

    def screen_to_world(self, point):
        center = self._center()
        return V((point.x() - center.x() - self.pan.x()) / self.zoom,
                 (point.y() - center.y() - self.pan.y()) / self.zoom)

    def snap(self, value):
        if not self.snap_enabled or self.snap_step <= 0:
            return round(float(value), 4)
        return round(round(float(value) / self.snap_step) * self.snap_step, 4)

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), BACKGROUND)

        if self.show_grid:
            self._draw_grid(painter)
        self._draw_axes(painter)

        self._handles = []
        if self.prefab is None:
            self._draw_placeholder(painter)
            painter.end()
            return

        if self.show_sprite:
            self._draw_sprite(painter)
        if self.show_light:
            self._draw_light(painter)
        if self.show_body:
            self._draw_body(painter)
        if self.show_segments:
            self._draw_segments(painter)

        self._draw_origin(painter)
        self._draw_handles(painter)
        self._draw_hud(painter)
        painter.end()

    def _draw_placeholder(self, painter):
        painter.setPen(QPen(QColor(120, 120, 130)))
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                         "Select a prefab to preview it")

    def _draw_grid(self, painter):
        step = self.snap_step if self.snap_step >= 1 else 1.0
        while step * self.zoom < 8:
            step *= 2
        major = step * 8

        top_left = self.screen_to_world(QPointF(0, 0))
        bottom_right = self.screen_to_world(QPointF(self.width(), self.height()))

        start_x = math.floor(top_left.x / step) * step
        start_y = math.floor(top_left.y / step) * step

        x = start_x
        while x <= bottom_right.x:
            is_major = abs(x % major) < 1e-6
            painter.setPen(QPen(GRID_MAJOR if is_major else GRID_MINOR, 1))
            sx = self.world_to_screen(V(x, 0)).x()
            painter.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
            x += step

        y = start_y
        while y <= bottom_right.y:
            is_major = abs(y % major) < 1e-6
            painter.setPen(QPen(GRID_MAJOR if is_major else GRID_MINOR, 1))
            sy = self.world_to_screen(V(0, y)).y()
            painter.drawLine(QPointF(0, sy), QPointF(self.width(), sy))
            y += step

    def _draw_axes(self, painter):
        painter.setPen(QPen(AXIS, 1))
        origin = self.world_to_screen(V(0, 0))
        painter.drawLine(QPointF(0, origin.y()), QPointF(self.width(), origin.y()))
        painter.drawLine(QPointF(origin.x(), 0), QPointF(origin.x(), self.height()))

    def _draw_origin(self, painter):
        origin = self.world_to_screen(V(0, 0))
        painter.setPen(QPen(ORIGIN, 1.4))
        painter.drawLine(origin + QPointF(-6, 0), origin + QPointF(6, 0))
        painter.drawLine(origin + QPointF(0, -6), origin + QPointF(0, 6))

    # -- sprite ------------------------------------------------------------

    def _pixmap_for(self, sprite):
        path = sprite.get("path")
        if not path or self.project is None:
            return None
        absolute = self.project.resolve(path)
        if not absolute or not os.path.exists(absolute):
            return None

        key = (absolute, sprite.get("frameWidth"), sprite.get("frameHeight"),
               sprite.get("frameX"), sprite.get("frameY"))
        if key in self._pixmap_cache:
            return self._pixmap_cache[key]

        pixmap = QPixmap(absolute)
        if pixmap.isNull():
            self._pixmap_cache[key] = None
            return None

        frame_w, frame_h = sprite.get("frameWidth"), sprite.get("frameHeight")
        if frame_w and frame_h:
            column = int(sprite.get("frameX") or 0)
            row = int(sprite.get("frameY") or 0)
            pixmap = pixmap.copy(int(column * frame_w), int(row * frame_h),
                                 int(frame_w), int(frame_h))

        self._pixmap_cache[key] = pixmap
        return pixmap

    def _draw_sprite(self, painter):
        sprite = self.prefab.find("SpriteRenderer")
        if sprite is None:
            return
        pixmap = self._pixmap_for(sprite)
        if pixmap is None:
            return

        scale = sprite.get("scale")
        scale_x = float(scale.x) if scale is not None else 1.0
        scale_y = float(scale.y) if scale is not None else 1.0
        offset = sprite.get("offset")
        # SpriteRenderer:Draw adds offset in world space, before rotating.
        centre = V(float(offset.x) if offset else 0.0,
                   float(offset.y) if offset else 0.0)

        color = sprite.get("color") or [1, 1, 1, 1]
        opacity = max(0.0, min(1.0, float(color[3]) if len(color) > 3 else 1.0))

        screen = self.world_to_screen(centre)
        transform = QTransform()
        transform.translate(screen.x(), screen.y())
        transform.rotate(math.degrees(self.preview_rotation))
        transform.scale(scale_x * self.zoom, scale_y * self.zoom)

        painter.save()
        painter.setOpacity(opacity)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.setTransform(transform, False)
        painter.drawPixmap(QPointF(-pixmap.width() / 2.0, -pixmap.height() / 2.0), pixmap)
        painter.restore()

        width = pixmap.width() * abs(scale_x)
        height = pixmap.height() * abs(scale_y)
        painter.save()
        painter.translate(screen)
        painter.rotate(math.degrees(self.preview_rotation))
        painter.setPen(QPen(SPRITE_BOUNDS, 1, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(-width * self.zoom / 2, -height * self.zoom / 2,
                                width * self.zoom, height * self.zoom))
        painter.restore()

        self._add_handle(Handle(
            ("sprite", "offset"), centre,
            lambda world: self._drag_sprite_offset(sprite, world),
            color=QColor(150, 150, 220), shape="circle", radius=4.0,
        ))

    def _drag_sprite_offset(self, sprite, world):
        sprite.set("offset", Vec2(self.snap(world.x), self.snap(world.y),
                                  _style_of(sprite.get("offset"), Vec2.TABLE)))

    # -- rigid body --------------------------------------------------------

    def _draw_body(self, painter):
        body = self.prefab.find("RigidBody")
        if body is None:
            return

        offset = body.get("offset")
        local_centre = V(float(offset.x) if offset else 0.0,
                         float(offset.y) if offset else 0.0)
        centre = self.local_to_world(local_centre.x, local_centre.y)
        screen_centre = self.world_to_screen(centre)

        if body.get("shape", "rectangle") == "circle":
            radius = float(body.get("radius") or 0)
            painter.setPen(QPen(BODY_COLOR, 1.6))
            painter.setBrush(QBrush(BODY_FILL))
            painter.drawEllipse(screen_centre, radius * self.zoom, radius * self.zoom)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            edge_local = V(local_centre.x + radius, local_centre.y)
            edge = self.local_to_world(edge_local.x, edge_local.y)
            self._add_handle(Handle(
                ("body", "radius"), edge,
                lambda world: self._drag_radius(body, local_centre, world),
                color=BODY_COLOR, cursor=Qt.CursorShape.SizeHorCursor,
            ))
        else:
            half_w = float(body.get("width") or 0) / 2.0
            half_h = float(body.get("height") or 0) / 2.0
            shape_angle = float(body.get("angle") or 0)
            total_angle = self.preview_rotation + shape_angle

            painter.save()
            painter.translate(screen_centre)
            painter.rotate(math.degrees(total_angle))
            painter.setPen(QPen(BODY_COLOR, 1.6))
            painter.setBrush(QBrush(BODY_FILL))
            painter.drawRect(QRectF(-half_w * self.zoom, -half_h * self.zoom,
                                    half_w * 2 * self.zoom, half_h * 2 * self.zoom))
            painter.restore()

            for name, (sx, sy) in _RESIZE_HANDLES.items():
                corner = _rotate(V(sx * half_w, sy * half_h), shape_angle)
                world = self.local_to_world(local_centre.x + corner.x,
                                            local_centre.y + corner.y)
                self._add_handle(Handle(
                    ("body", name), world,
                    lambda w, sx=sx, sy=sy: self._drag_resize(body, sx, sy, w),
                    color=BODY_COLOR, cursor=_RESIZE_CURSORS[name],
                ))

            arm = _rotate(V(0.0, -half_h - 18.0 / self.zoom), shape_angle)
            rotate_world = self.local_to_world(local_centre.x + arm.x,
                                               local_centre.y + arm.y)
            painter.setPen(QPen(BODY_COLOR, 1, Qt.PenStyle.DotLine))
            painter.drawLine(screen_centre, self.world_to_screen(rotate_world))
            self._add_handle(Handle(
                ("body", "angle"), rotate_world,
                lambda world: self._drag_body_angle(body, local_centre, world),
                color=BODY_COLOR, shape="circle", radius=4.5,
                cursor=Qt.CursorShape.CrossCursor,
            ))

        self._add_handle(Handle(
            ("body", "offset"), centre,
            lambda world: self._drag_body_offset(body, world),
            color=BODY_COLOR, shape="circle", radius=4.0,
        ))

    def _drag_body_offset(self, body, world):
        local = self.world_to_local(world.x, world.y)
        body.set("offset", Vec2(self.snap(local.x), self.snap(local.y),
                                _style_of(body.get("offset"), Vec2.TABLE)))

    def _drag_radius(self, body, local_centre, world):
        local = self.world_to_local(world.x, world.y)
        radius = math.hypot(local.x - local_centre.x, local.y - local_centre.y)
        body.set("radius", max(0.5, self.snap(radius)))

    def _drag_body_angle(self, body, local_centre, world):
        local = self.world_to_local(world.x, world.y)
        angle = math.atan2(local.y - local_centre.y, local.x - local_centre.x) + math.pi / 2
        if self.snap_enabled:
            step = math.radians(15)
            angle = round(angle / step) * step
        body.set("angle", round(angle, 5))

    def _drag_resize(self, body, sign_x, sign_y, world):
        """Resize about the opposite edge, so that edge stays put."""
        shape_angle = float(body.get("angle") or 0)
        offset = body.get("offset")
        centre = V(float(offset.x) if offset else 0.0,
                   float(offset.y) if offset else 0.0)
        half_w = float(body.get("width") or 0) / 2.0
        half_h = float(body.get("height") or 0) / 2.0

        local = self.world_to_local(world.x, world.y)
        in_shape = _rotate(V(local.x - centre.x, local.y - centre.y), -shape_angle)

        anchor = V(-sign_x * half_w, -sign_y * half_h)
        new_half_w, new_half_h = half_w, half_h

        if sign_x:
            new_half_w = max(0.5, abs(in_shape.x - anchor.x) / 2.0)
        if sign_y:
            new_half_h = max(0.5, abs(in_shape.y - anchor.y) / 2.0)

        new_half_w = max(0.5, self.snap(new_half_w * 2) / 2.0)
        new_half_h = max(0.5, self.snap(new_half_h * 2) / 2.0)

        moved = V(anchor.x + sign_x * new_half_w, anchor.y + sign_y * new_half_h)
        shift = _rotate(V(moved.x, moved.y), shape_angle)

        body.set("width", round(new_half_w * 2, 4))
        body.set("height", round(new_half_h * 2, 4))
        body.set("offset", Vec2(round(centre.x + shift.x, 4),
                                round(centre.y + shift.y, 4),
                                _style_of(offset, Vec2.TABLE)))

    # -- light segments ----------------------------------------------------

    def _draw_segments(self, painter):
        light = self.prefab.find("LightCollider")
        if light is None:
            return
        segments = light.get("segments") or []

        for index, segment in enumerate(segments):
            a_local, b_local = segment.get("a"), segment.get("b")
            if a_local is None or b_local is None:
                continue
            a = self.local_to_world(float(a_local.x), float(a_local.y))
            b = self.local_to_world(float(b_local.x), float(b_local.y))
            screen_a = self.world_to_screen(a)
            screen_b = self.world_to_screen(b)

            selected = (index == self.selected_segment)
            color = segment_color(segment)
            painter.setPen(QPen(color, 4.0 if selected else 2.6,
                                Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap))
            painter.drawLine(screen_a, screen_b)

            # Normal tick, showing which way segmentIntersect will flip it.
            mid = QPointF((screen_a.x() + screen_b.x()) / 2,
                          (screen_a.y() + screen_b.y()) / 2)
            edge = V(b.x - a.x, b.y - a.y)
            normal = V(-edge.y, edge.x).normalized()
            painter.setPen(QPen(color.darker(120), 1, Qt.PenStyle.DashLine))
            painter.drawLine(mid, mid + QPointF(normal.x * 14, normal.y * 14))

            if selected:
                painter.setPen(QPen(QColor(255, 255, 255, 90), 1))
                painter.drawText(mid + QPointF(6, -6), f"#{index + 1}")

            self._add_handle(Handle(
                ("segment", index, "a"), a,
                lambda world, i=index: self._drag_segment_point(i, "a", world),
                color=color,
            ))
            self._add_handle(Handle(
                ("segment", index, "b"), b,
                lambda world, i=index: self._drag_segment_point(i, "b", world),
                color=color,
            ))
            self._add_handle(Handle(
                ("segment", index, "mid"),
                V((a.x + b.x) / 2, (a.y + b.y) / 2),
                lambda world, i=index: self._drag_segment_whole(i, world),
                color=color, shape="circle", radius=3.6,
            ))

    def _segment(self, index):
        light = self.prefab.find("LightCollider")
        if light is None:
            return None
        segments = light.get("segments") or []
        if 0 <= index < len(segments):
            return segments[index]
        return None

    def _drag_segment_point(self, index, key, world):
        segment = self._segment(index)
        if segment is None:
            return
        local = self.world_to_local(world.x, world.y)
        segment[key] = Vec2(self.snap(local.x), self.snap(local.y),
                            _style_of(segment.get(key), Vec2.CALL))
        segment.setdefault("_explicit", set()).add(key)
        self.selected_segment = index

    def _drag_segment_whole(self, index, world):
        segment = self._segment(index)
        if segment is None:
            return
        local = self.world_to_local(world.x, world.y)
        a, b = segment["a"], segment["b"]
        mid_x = (float(a.x) + float(b.x)) / 2.0
        mid_y = (float(a.y) + float(b.y)) / 2.0
        dx = self.snap(local.x - mid_x)
        dy = self.snap(local.y - mid_y)
        for key in ("a", "b"):
            point = segment[key]
            segment[key] = Vec2(round(float(point.x) + dx, 4),
                                round(float(point.y) + dy, 4),
                                _style_of(point, Vec2.CALL))
            segment.setdefault("_explicit", set()).add(key)
        self.selected_segment = index

    # -- light trace -------------------------------------------------------

    def _draw_light(self, painter):
        segments = raytrace.world_segments(self.prefab, V(0.0, 0.0), self.preview_rotation)
        if not segments:
            if self.probe_enabled:
                self._draw_probe_marker(painter)
            return

        fans = []
        own_source = self.prefab.find("LightSource")
        if own_source is not None:
            fans.append(raytrace.cast_fan(
                segments, V(0.0, 0.0), self.preview_rotation,
                int(own_source.get("rayCount", 16) or 16),
                float(own_source.get("coneAngle", 2 * math.pi) or 0),
                int(own_source.get("maxDepth", 4) or 4),
                float(own_source.get("minIntensity", 0.05) or 0),
            ))
        if self.probe_enabled:
            fans.append(raytrace.cast_fan(
                segments, self.probe_position, self.probe_angle,
                self.probe_ray_count, self.probe_cone, self.probe_depth, 0.02,
            ))

        for fan in fans:
            if self.show_godrays:
                for index in range(len(fan) - 1):
                    self._draw_quad_pair(painter, fan[index], fan[index + 1])
            painter.setPen(QPen(RAY_COLOR, 1.0))
            for node in fan:
                self._draw_ray_node(painter, node)

        if self.probe_enabled:
            self._draw_probe_marker(painter)

    def _draw_ray_node(self, painter, node):
        end = node.end_point()
        painter.setPen(QPen(QColor(255, 255, 150, int(40 + 150 * min(1.0, node.intensity))), 1.0))
        painter.drawLine(self.world_to_screen(node.origin), self.world_to_screen(end))
        if node.reflected is not None:
            self._draw_ray_node(painter, node.reflected)
        if node.refracted is not None:
            self._draw_ray_node(painter, node.refracted)

    def _draw_quad_pair(self, painter, node_a, node_b):
        """Mirrors GodrayRenderer:drawQuadPair, including its recursion."""
        if node_a is None or node_b is None:
            return
        if node_a.hit_point is None or node_b.hit_point is None:
            return

        alpha = (node_a.intensity + node_b.intensity) / 2.0
        color = QColor(GODRAY_COLOR)
        color.setAlphaF(max(0.0, min(1.0, alpha * 0.30)))

        polygon = QPolygonF([
            self.world_to_screen(node_a.origin),
            self.world_to_screen(node_a.hit_point),
            self.world_to_screen(node_b.hit_point),
            self.world_to_screen(node_b.origin),
        ])
        path = QPainterPath()
        path.addPolygon(polygon)
        painter.fillPath(path, QBrush(color))

        self._draw_quad_pair(painter, node_a.reflected, node_b.reflected)
        self._draw_quad_pair(painter, node_a.refracted, node_b.refracted)

    def _draw_probe_marker(self, painter):
        origin = self.world_to_screen(self.probe_position)
        painter.setPen(QPen(PROBE_COLOR, 1.5))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(origin, 6, 6)
        painter.drawLine(origin + QPointF(-9, 0), origin + QPointF(9, 0))
        painter.drawLine(origin + QPointF(0, -9), origin + QPointF(0, 9))

        arm_length = 46.0 / self.zoom
        tip = V(self.probe_position.x + math.cos(self.probe_angle) * arm_length,
                self.probe_position.y + math.sin(self.probe_angle) * arm_length)
        painter.setPen(QPen(PROBE_COLOR, 1, Qt.PenStyle.DashLine))
        painter.drawLine(origin, self.world_to_screen(tip))

        self._add_handle(Handle(
            ("probe", "position"), self.probe_position,
            self._drag_probe_position, color=PROBE_COLOR, shape="circle", radius=5.0,
        ))
        self._add_handle(Handle(
            ("probe", "angle"), tip, self._drag_probe_angle,
            color=PROBE_COLOR, shape="circle", radius=4.0,
            cursor=Qt.CursorShape.CrossCursor,
        ))

    def _drag_probe_position(self, world):
        self.probe_position = V(round(world.x, 3), round(world.y, 3))

    def _drag_probe_angle(self, world):
        self.probe_angle = math.atan2(world.y - self.probe_position.y,
                                      world.x - self.probe_position.x)

    # -- handles -----------------------------------------------------------

    def _add_handle(self, handle):
        self._handles.append(handle)

    def _draw_handles(self, painter):
        for handle in self._handles:
            screen = self.world_to_screen(handle.position)
            hovered = (self._hover_handle is not None
                       and self._hover_handle.key == handle.key)
            radius = handle.radius + (1.5 if hovered else 0.0)
            painter.setPen(QPen(HANDLE_EDGE, 1))
            painter.setBrush(QBrush(handle.color if hovered else HANDLE_FILL))
            if handle.shape == "circle":
                painter.drawEllipse(screen, radius, radius)
            else:
                painter.drawRect(QRectF(screen.x() - radius, screen.y() - radius,
                                        radius * 2, radius * 2))
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _handle_at(self, position):
        best, best_distance = None, 9.0
        for handle in reversed(self._handles):
            screen = self.world_to_screen(handle.position)
            distance = math.hypot(screen.x() - position.x(), screen.y() - position.y())
            if distance <= max(best_distance, handle.radius + 4):
                if distance < best_distance or best is None:
                    best, best_distance = handle, distance
        return best

    def _draw_hud(self, painter):
        font = QFont(painter.font())
        font.setPointSizeF(8.5)
        painter.setFont(font)
        painter.setPen(QPen(QColor(150, 150, 165)))
        text = (f"zoom {self.zoom:.2f}x   "
                f"rotation {math.degrees(self.preview_rotation):.1f}deg   "
                f"snap {self.snap_step:g}px" if self.snap_enabled else
                f"zoom {self.zoom:.2f}x   "
                f"rotation {math.degrees(self.preview_rotation):.1f}deg   snap off")
        painter.drawText(8, self.height() - 8, text)

    # -- interaction -------------------------------------------------------

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = True
            self._last_mouse = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._handle_at(event.position())
            if handle is not None:
                self._active_handle = handle
                if handle.key[0] != "probe":
                    self.editStarted.emit()
                if handle.key[0] == "segment":
                    self.selected_segment = handle.key[1]
                    self.selectionChanged.emit(self.selected_segment)
                return
            self._panning = True
            self._last_mouse = event.position().toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)

    def mouseMoveEvent(self, event):
        if self._panning:
            current = event.position().toPoint()
            delta = current - self._last_mouse
            self.pan += QPointF(delta.x(), delta.y())
            self._last_mouse = current
            self.update()
            return

        if self._active_handle is not None:
            world = self.screen_to_world(event.position())
            self._active_handle.on_drag(world)
            if self._active_handle.key[0] != "probe":
                self.modelChanged.emit()
            self.update()
            return

        hover = self._handle_at(event.position())
        if hover is not self._hover_handle:
            self._hover_handle = hover
            self.setCursor(hover.cursor if hover else Qt.CursorShape.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, event):
        if self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
        if self._active_handle is not None:
            self._active_handle = None
            self.modelChanged.emit()

    def wheelEvent(self, event):
        before = self.screen_to_world(event.position())
        factor = 1.15 if event.angleDelta().y() > 0 else 1 / 1.15
        self.zoom = max(0.2, min(24.0, self.zoom * factor))
        after = self.screen_to_world(event.position())
        self.pan += QPointF((after.x - before.x) * self.zoom,
                            (after.y - before.y) * self.zoom)
        self.update()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_F:
            self.frame_content()
        else:
            super().keyPressEvent(event)


_RESIZE_HANDLES = {
    "nw": (-1, -1), "n": (0, -1), "ne": (1, -1),
    "w": (-1, 0), "e": (1, 0),
    "sw": (-1, 1), "s": (0, 1), "se": (1, 1),
}

_RESIZE_CURSORS = {
    "nw": Qt.CursorShape.SizeFDiagCursor, "se": Qt.CursorShape.SizeFDiagCursor,
    "ne": Qt.CursorShape.SizeBDiagCursor, "sw": Qt.CursorShape.SizeBDiagCursor,
    "n": Qt.CursorShape.SizeVerCursor, "s": Qt.CursorShape.SizeVerCursor,
    "e": Qt.CursorShape.SizeHorCursor, "w": Qt.CursorShape.SizeHorCursor,
}


def _rotate(vector, angle):
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return V(vector.x * cos_a - vector.y * sin_a, vector.x * sin_a + vector.y * cos_a)


def _style_of(existing, fallback):
    if isinstance(existing, Vec2) and existing.style:
        return existing.style
    return fallback
