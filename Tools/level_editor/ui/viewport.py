"""The level canvas: every object drawn where the engine would draw it, plus
selection, dragging, rotation and the whole-room light solution.

Two coordinate spaces, one fewer than the prefab editor needs:

    world   -- game pixels, the same numbers that go in the level file
    screen  -- world scaled by zoom and shifted by pan

Objects are painted in list order, because that is `Scene:Draw`. Light is solved
once for the room and painted after all the sprites, which is a small departure
from the engine -- there each object draws its own godrays in list order -- but
the alternative is a beam disappearing behind a sprite that happens to sit later
in the list, which would be an artefact of the tool rather than the game.

The solve is cached and invalidated by `mark_light_dirty`. Without that, every
mouse move during a drag would re-trace a few hundred rays.
"""

from __future__ import annotations

import math
import os

from PyQt6.QtCore import QPoint, QPointF, QRectF, Qt, pyqtSignal
from PyQt6.QtGui import (QBrush, QColor, QFont, QPainter, QPainterPath, QPen,
                         QPixmap, QPolygonF, QTransform)
from PyQt6.QtWidgets import QWidget

from ..model import level as level_model
from ..model import sprites
from ..model import tilemap as tilemap_model
from ..preview import scene_light
from ..preview.raytrace import V

BACKGROUND = QColor(18, 18, 22)
OUTSIDE = QColor(11, 11, 14)
GRID_MINOR = QColor(34, 34, 42)
GRID_MAJOR = QColor(50, 50, 60)
SCREEN_EDGE = QColor(120, 120, 150)
BODY_COLOR = QColor(0, 235, 60)
BODY_FILL = QColor(0, 235, 60, 22)
STATIC_COLOR = QColor(90, 190, 255)
STATIC_FILL = QColor(90, 190, 255, 22)
SPRITE_BOUNDS = QColor(150, 150, 210, 90)
SELECTION = QColor(255, 170, 60)
SELECTION_FILL = QColor(255, 170, 60, 30)
HANDLE_FILL = QColor(255, 255, 255)
HANDLE_EDGE = QColor(20, 20, 20)
GODRAY_COLOR = QColor(255, 255, 230)
JOINT_COLOR = QColor(220, 120, 255)
DETECTOR_LIT = QColor(120, 255, 160)
DETECTOR_DARK = QColor(110, 110, 120)
GHOST = QColor(255, 255, 255, 90)
TILE_GRID = QColor(255, 255, 255, 28)
TILE_BOUNDS = QColor(120, 200, 255, 160)
TILE_HOVER = QColor(255, 170, 60, 70)
TILE_HOVER_EDGE = QColor(255, 170, 60)

# Matches Libraries/renderer/debug_light_renderer.lua.
MIRROR_COLOR = QColor(230, 230, 50)
GLASS_COLOR = QColor(75, 150, 255)
ABSORBER_COLOR = QColor(205, 50, 50)
INERT_COLOR = QColor(220, 220, 220)


def segment_color(segment):
    if float(getattr(segment, "refractive_index", 1) or 1) != 1:
        return GLASS_COLOR
    if float(getattr(segment, "reflective", 0) or 0) > 0:
        return MIRROR_COLOR
    if float(getattr(segment, "absorption", 0) or 0) > 0:
        return ABSORBER_COLOR
    return INERT_COLOR


class Handle:
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
    modelChanged = pyqtSignal()        # the level changed; redraw dependents
    editStarted = pyqtSignal()         # push an undo snapshot before this edit
    selectionChanged = pyqtSignal()
    placementFinished = pyqtSignal()
    statusMessage = pyqtSignal(str)
    tilePicked = pyqtSignal(int)      # eyedropper result, for the tile panel

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(480, 380)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)

        self.project = None
        self.level = None
        self.library = None
        self.selection = []

        self.screen_size = (320, 240)
        self.zoom = 2.0
        self.pan = QPointF(0.0, 0.0)

        self.show_grid = True
        self.show_tiles = True
        self.show_sprites = True
        self.show_bodies = True
        self.show_segments = True
        self.show_light = True
        self.show_godrays = True
        self.show_joints = True
        self.show_labels = False
        self.show_screen_frame = True
        self.dim_outside = True

        self.snap_enabled = True
        self.snap_step = 8.0

        self.placement_prefab = None       # armed from the palette

        # Tile painting. `tile_target` is the object being painted into; it is
        # set from the tile panel rather than from whatever happens to be
        # selected, so clicking a lamp mid-stroke does not redirect the brush.
        self.tile_mode = False
        self.tile_target = None
        self.tile_tool = "brush"
        self.tile_id = 1

        self._light = None
        self._light_dirty = True
        self._detectors = []
        self._handles = []
        self._active_handle = None
        self._hover_handle = None
        self._panning = False
        self._dragging = False
        self._drag_origin = None
        self._drag_start = []
        self._marquee = None
        self._last_mouse = QPoint()
        self._pixmap_cache = {}
        self._tileset_cache = {}
        self._cursor_world = V(0.0, 0.0)
        self._tile_stroke = None           # the tool driving the drag, or None
        self._tile_erasing = False
        self._tile_rect_origin = None
        self._tile_hover = None

    # -- external API ------------------------------------------------------

    def set_project(self, project):
        self.project = project
        self._pixmap_cache.clear()
        self._tileset_cache.clear()
        if project is not None:
            self.screen_size = project.screen_size()
        self.mark_light_dirty()

    def set_level(self, level, library=None):
        self.level = level
        if library is not None:
            self.library = library
        self.selection = []
        self.mark_light_dirty()
        self.selectionChanged.emit()

    def set_library(self, library):
        self.library = library
        self.mark_light_dirty()

    def is_interacting(self):
        """True while a drag is in flight.

        The window uses this to skip the expensive per-edit work -- rebuilding
        the object list, re-running the checks, re-serializing to test the
        modified flag -- which would otherwise run on every mouse move.
        """
        return bool(self._dragging or self._active_handle or self._panning
                    or self._tile_stroke)

    def mark_light_dirty(self):
        self._light_dirty = True
        self.update()

    def set_screen_size(self, width, height):
        self.screen_size = (int(width), int(height))
        self.update()

    def set_selection(self, objects):
        self.selection = list(objects)
        self.update()
        self.selectionChanged.emit()

    def selected(self):
        return self.selection[0] if self.selection else None

    def arm_placement(self, prefab_name):
        self.placement_prefab = prefab_name
        self.setCursor(Qt.CursorShape.CrossCursor if prefab_name
                       else Qt.CursorShape.ArrowCursor)
        self.update()

    def frame_screen(self):
        """Fit the game screen rectangle in the view."""
        width, height = self.screen_size
        margin = 1.12
        self.zoom = max(0.25, min(12.0,
                                  min(self.width() / (width * margin),
                                      self.height() / (height * margin))))
        self.pan = QPointF(0.0, 0.0)
        self.update()

    def frame_selection(self):
        if not self.selection:
            self.frame_screen()
            return
        xs = [o.x for o in self.selection]
        ys = [o.y for o in self.selection]
        centre = V((min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2)
        span = max(48.0, max(max(xs) - min(xs), max(ys) - min(ys)) * 1.6)
        self.zoom = max(0.25, min(12.0, min(self.width(), self.height()) / span))
        world_centre = self._world_centre()
        self.pan = QPointF((world_centre.x - centre.x) * self.zoom,
                           (world_centre.y - centre.y) * self.zoom)
        self.update()

    # -- transforms --------------------------------------------------------

    def _world_centre(self):
        width, height = self.screen_size
        return V(width / 2.0, height / 2.0)

    def world_to_screen(self, point):
        centre = self._world_centre()
        return QPointF(
            self.width() / 2.0 + self.pan.x() + (point.x - centre.x) * self.zoom,
            self.height() / 2.0 + self.pan.y() + (point.y - centre.y) * self.zoom,
        )

    def screen_to_world(self, point):
        centre = self._world_centre()
        return V(
            (point.x() - self.width() / 2.0 - self.pan.x()) / self.zoom + centre.x,
            (point.y() - self.height() / 2.0 - self.pan.y()) / self.zoom + centre.y,
        )

    def snap(self, value):
        if not self.snap_enabled or self.snap_step <= 0:
            return round(float(value), 4)
        return round(round(float(value) / self.snap_step) * self.snap_step, 4)

    # -- model helpers -----------------------------------------------------

    def resolve(self, obj):
        return level_model.resolve(obj, self.library)

    def _light_solution(self):
        if self.level is None or self.library is None:
            return None
        if self._light_dirty or self._light is None:
            self._light = scene_light.solve(self.level, self.library)
            self._detectors = scene_light.detector_hits(
                self.level, self.library, self._light)
            self._light_dirty = False
        return self._light

    # -- painting ----------------------------------------------------------

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        painter.fillRect(self.rect(), OUTSIDE if self.dim_outside else BACKGROUND)

        self._handles = []

        if self.dim_outside:
            self._fill_screen_rect(painter)
        if self.show_grid:
            self._draw_grid(painter)

        if self.level is None:
            painter.setPen(QPen(QColor(120, 120, 130)))
            painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter,
                             "Open a level file to begin")
            painter.end()
            return

        light = self._light_solution() if self.show_light else None

        if self.show_tiles:
            for obj in self.level.objects:
                self._draw_tilemap(painter, obj)

        if self.show_sprites:
            for obj in self.level.objects:
                self._draw_sprite(painter, obj)

        if light is not None:
            if self.show_godrays:
                for _obj, fan in light.fans:
                    for index in range(len(fan) - 1):
                        self._draw_quad_pair(painter, fan[index], fan[index + 1])
            for _obj, fan in light.fans:
                for node in fan:
                    self._draw_ray_node(painter, node)

        if self.show_bodies:
            for obj in self.level.objects:
                self._draw_body(painter, obj)

        if self.show_segments:
            self._draw_segments(painter)

        if self.show_joints:
            self._draw_joints(painter)

        self._draw_detectors(painter)

        for obj in self.selection:
            self._draw_selection(painter, obj)

        if self.show_labels:
            for obj in self.level.objects:
                self._draw_label(painter, obj)

        if self.show_screen_frame:
            self._draw_screen_frame(painter)

        if self.placement_prefab:
            self._draw_placement_ghost(painter)

        if self._marquee is not None:
            self._draw_marquee(painter)

        if self.tile_mode:
            self._draw_tile_overlay(painter)

        self._draw_handles(painter)
        self._draw_hud(painter)
        painter.end()

    def _screen_rect(self):
        width, height = self.screen_size
        top_left = self.world_to_screen(V(0, 0))
        bottom_right = self.world_to_screen(V(width, height))
        return QRectF(top_left, bottom_right)

    def _fill_screen_rect(self, painter):
        painter.fillRect(self._screen_rect(), BACKGROUND)

    def _draw_screen_frame(self, painter):
        width, height = self.screen_size
        painter.setPen(QPen(SCREEN_EDGE, 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(self._screen_rect())

        font = QFont(painter.font())
        font.setPointSizeF(8.0)
        painter.setFont(font)
        painter.setPen(QPen(SCREEN_EDGE))
        corner = self.world_to_screen(V(0, 0))
        painter.drawText(QPointF(corner.x() + 3, corner.y() - 4),
                         f"{width} x {height}")

    def _draw_grid(self, painter):
        step = self.snap_step if self.snap_step >= 1 else 1.0
        while step * self.zoom < 6:
            step *= 2
        major = step * 4

        top_left = self.screen_to_world(QPointF(0, 0))
        bottom_right = self.screen_to_world(QPointF(self.width(), self.height()))

        x = math.floor(top_left.x / step) * step
        while x <= bottom_right.x:
            painter.setPen(QPen(GRID_MAJOR if abs(x % major) < 1e-6 else GRID_MINOR, 1))
            sx = self.world_to_screen(V(x, 0)).x()
            painter.drawLine(QPointF(sx, 0), QPointF(sx, self.height()))
            x += step

        y = math.floor(top_left.y / step) * step
        while y <= bottom_right.y:
            painter.setPen(QPen(GRID_MAJOR if abs(y % major) < 1e-6 else GRID_MINOR, 1))
            sy = self.world_to_screen(V(0, y)).y()
            painter.drawLine(QPointF(0, sy), QPointF(self.width(), sy))
            y += step

    # -- tilemaps ----------------------------------------------------------

    def tile_binding(self, obj):
        """The tile view of an object, or None when it is not a tilemap."""
        if self.library is None or obj is None:
            return None
        binding = tilemap_model.TilemapBinding(obj, self.library)
        return binding if binding else None

    def _tileset_pixmap(self, binding):
        """The whole sheet, cached by path.

        One pixmap per tileset rather than one per tile: a map draws from a few
        dozen distinct ids, but cutting each into its own QPixmap would allocate
        per id and lose nothing, since drawPixmap takes a source rectangle.
        """
        path = binding.tileset
        if not path or self.project is None:
            return None
        absolute = self.project.resolve(path)
        if not absolute or not os.path.exists(absolute):
            return None
        if absolute in self._tileset_cache:
            return self._tileset_cache[absolute]
        pixmap = QPixmap(absolute)
        if pixmap.isNull():
            pixmap = None
        self._tileset_cache[absolute] = pixmap
        return pixmap

    def _draw_tilemap(self, painter, obj):
        binding = self.tile_binding(obj)
        if binding is None or binding.width <= 0 or binding.height <= 0:
            return
        pixmap = self._tileset_pixmap(binding)
        if pixmap is None:
            return
        columns = tilemap_model.tileset_columns(binding, self.project)
        if not columns:
            return

        tiles = binding.tiles
        tile_w, tile_h = binding.tile_width, binding.tile_height
        scale = obj.world_scale() or 1.0
        step_x, step_y = tile_w * scale, tile_h * scale

        # Cull to what is actually on screen. Without this a 200x200 map costs
        # 40 000 drawPixmap calls per repaint, and repaints happen on every
        # mouse move.
        top_left = self.screen_to_world(QPointF(0, 0))
        bottom_right = self.screen_to_world(QPointF(self.width(), self.height()))
        first_col = max(0, int((top_left.x - obj.x) // step_x))
        last_col = min(binding.width - 1, int((bottom_right.x - obj.x) // step_x) + 1)
        first_row = max(0, int((top_left.y - obj.y) // step_y))
        last_row = min(binding.height - 1, int((bottom_right.y - obj.y) // step_y) + 1)
        if first_col > last_col or first_row > last_row:
            return

        colour = binding.get("color")
        alpha = float(colour[3]) if isinstance(colour, list) and len(colour) > 3 else 1.0

        painter.save()
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.setOpacity(max(0.0, min(1.0, alpha)))
        for row in range(first_row, last_row + 1):
            for col in range(first_col, last_col + 1):
                tile_id = tiles[row * binding.width + col]
                if tile_id <= 0:
                    continue
                index = tile_id - 1
                source = QRectF((index % columns) * tile_w,
                                (index // columns) * tile_h, tile_w, tile_h)
                origin = self.world_to_screen(V(obj.x + col * step_x,
                                                obj.y + row * step_y))
                target = QRectF(origin.x(), origin.y(),
                                step_x * self.zoom, step_y * self.zoom)
                painter.drawPixmap(target, pixmap, source)
        painter.restore()

    def _draw_tile_overlay(self, painter):
        binding = self.tile_binding(self.tile_target)
        if binding is None:
            painter.setPen(QPen(QColor(220, 140, 140)))
            painter.drawText(10, 20, "Tile mode: no tilemap selected")
            return

        x, y, width, height = binding.world_rect()
        top_left = self.world_to_screen(V(x, y))
        bottom_right = self.world_to_screen(V(x + width, y + height))
        bounds = QRectF(top_left, bottom_right)

        scale = self.tile_target.world_scale() or 1.0
        step_x = binding.tile_width * scale * self.zoom
        step_y = binding.tile_height * scale * self.zoom

        # The cell grid is only legible past a few pixels a cell, and below that
        # it turns into a grey wash that hides the tiles underneath it.
        if step_x >= 4 and step_y >= 4:
            painter.setPen(QPen(TILE_GRID, 1))
            for col in range(binding.width + 1):
                sx = bounds.left() + col * step_x
                painter.drawLine(QPointF(sx, bounds.top()),
                                 QPointF(sx, bounds.bottom()))
            for row in range(binding.height + 1):
                sy = bounds.top() + row * step_y
                painter.drawLine(QPointF(bounds.left(), sy),
                                 QPointF(bounds.right(), sy))

        painter.setPen(QPen(TILE_BOUNDS, 1.5, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(bounds)

        if self._tile_rect_origin is not None and self._tile_hover is not None:
            col0, row0 = self._tile_rect_origin
            col1, row1 = self._tile_hover
            left, right = sorted((col0, col1))
            top, bottom = sorted((row0, row1))
            self._fill_cells(painter, bounds, step_x, step_y,
                             left, top, right - left + 1, bottom - top + 1)
        elif self._tile_hover is not None:
            col, row = self._tile_hover
            if binding.in_bounds(col, row):
                self._fill_cells(painter, bounds, step_x, step_y, col, row, 1, 1)

    def _fill_cells(self, painter, bounds, step_x, step_y, col, row, cols, rows):
        rect = QRectF(bounds.left() + col * step_x, bounds.top() + row * step_y,
                      cols * step_x, rows * step_y)
        painter.setPen(QPen(TILE_HOVER_EDGE, 1.2))
        painter.setBrush(QBrush(TILE_HOVER))
        painter.drawRect(rect)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    # -- sprites -----------------------------------------------------------

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
            pixmap = pixmap.copy(int((sprite.get("frameX") or 0) * frame_w),
                                 int((sprite.get("frameY") or 0) * frame_h),
                                 int(frame_w), int(frame_h))

        self._pixmap_cache[key] = pixmap
        return pixmap

    def _draw_sprite(self, painter, obj):
        resolved = self.resolve(obj)
        if resolved is None:
            self._draw_missing(painter, obj)
            return
        sprite = resolved.find("SpriteRenderer")
        if sprite is None:
            return
        pixmap = self._pixmap_for(sprite)
        if pixmap is None:
            return

        # The transform's uniform scale multiplies the sprite's own per-axis
        # scale, matching SpriteRenderer:Draw.
        world_scale = obj.world_scale()
        scale = sprite.get("scale")
        scale_x = (float(scale.x) if scale is not None else 1.0) * world_scale
        scale_y = (float(scale.y) if scale is not None else 1.0) * world_scale
        offset = sprite.get("offset")
        # SpriteRenderer:Draw adds offset in world space, before the rotation,
        # so the offset does not orbit the object origin.
        centre = V(obj.x + (float(offset.x) if offset else 0.0) * world_scale,
                   obj.y + (float(offset.y) if offset else 0.0) * world_scale)

        color = sprite.get("color") or [1, 1, 1, 1]
        opacity = max(0.0, min(1.0, float(color[3]) if len(color) > 3 else 1.0))

        screen = self.world_to_screen(centre)
        transform = QTransform()
        transform.translate(screen.x(), screen.y())
        transform.rotate(math.degrees(obj.angle()))
        transform.scale(scale_x * self.zoom, scale_y * self.zoom)

        painter.save()
        painter.setOpacity(opacity)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform, False)
        painter.setTransform(transform, False)
        painter.drawPixmap(QPointF(-pixmap.width() / 2.0, -pixmap.height() / 2.0),
                           pixmap)
        painter.restore()

    def _draw_missing(self, painter, obj):
        """An object whose prefab is not in the library still has to be visible."""
        screen = self.world_to_screen(V(obj.x, obj.y))
        size = 10.0
        painter.setPen(QPen(QColor(235, 80, 80), 1.4))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawRect(QRectF(screen.x() - size, screen.y() - size,
                                size * 2, size * 2))
        painter.drawLine(QPointF(screen.x() - size, screen.y() - size),
                         QPointF(screen.x() + size, screen.y() + size))
        painter.drawLine(QPointF(screen.x() + size, screen.y() - size),
                         QPointF(screen.x() - size, screen.y() + size))

    # -- bodies ------------------------------------------------------------

    def _draw_body(self, painter, obj):
        resolved = self.resolve(obj)
        if resolved is None:
            return
        body = resolved.find("RigidBody")
        if body is None:
            return

        is_static = body.get("bodyType", "dynamic") == "static"
        pen = QPen(STATIC_COLOR if is_static else BODY_COLOR, 1.2)
        fill = QBrush(STATIC_FILL if is_static else BODY_FILL)

        # RigidBody bakes world scale into its size at attach, so the gizmo
        # has to scale to match what the running game will build.
        world_scale = obj.world_scale()
        offset = body.get("offset")
        local = V((float(offset.x) if offset else 0.0) * world_scale,
                  (float(offset.y) if offset else 0.0) * world_scale)
        centre = _rotate(local, obj.angle())
        centre = V(obj.x + centre.x, obj.y + centre.y)
        screen_centre = self.world_to_screen(centre)

        painter.setPen(pen)
        painter.setBrush(fill)

        if body.get("shape", "rectangle") == "circle":
            radius = float(body.get("radius") or 0) * world_scale * self.zoom
            painter.drawEllipse(screen_centre, radius, radius)
        else:
            half_w = float(body.get("width") or 0) * world_scale / 2.0 * self.zoom
            half_h = float(body.get("height") or 0) * world_scale / 2.0 * self.zoom
            angle = obj.angle() + float(body.get("angle") or 0)
            painter.save()
            painter.translate(screen_centre)
            painter.rotate(math.degrees(angle))
            painter.drawRect(QRectF(-half_w, -half_h, half_w * 2, half_h * 2))
            painter.restore()

        painter.setBrush(Qt.BrushStyle.NoBrush)

    # -- light segments ----------------------------------------------------

    def _draw_segments(self, painter):
        light = self._light_solution()
        if light is None:
            return
        selected = set(id(o) for o in self.selection)
        for segment in light.segments:
            color = QColor(segment_color(segment))
            width = 2.4 if id(segment.owner) in selected else 1.6
            painter.setPen(QPen(color, width))
            painter.drawLine(self.world_to_screen(segment.a),
                             self.world_to_screen(segment.b))

    # -- rays --------------------------------------------------------------

    def _draw_ray_node(self, painter, node):
        end = node.end_point()
        alpha = int(40 + 150 * min(1.0, node.intensity))
        painter.setPen(QPen(QColor(255, 255, 150, alpha), 1.0))
        painter.drawLine(self.world_to_screen(node.origin),
                         self.world_to_screen(end))
        if node.reflected is not None:
            self._draw_ray_node(painter, node.reflected)
        if node.refracted is not None:
            self._draw_ray_node(painter, node.refracted)

    def _draw_quad_pair(self, painter, node_a, node_b):
        """Mirrors GodrayRenderer:drawQuadPair, recursion included."""
        if node_a is None or node_b is None:
            return
        if node_a.hit_point is None or node_b.hit_point is None:
            return

        alpha = (node_a.intensity + node_b.intensity) / 2.0
        color = QColor(GODRAY_COLOR)
        color.setAlphaF(max(0.0, min(1.0, alpha * 0.30)))

        path = QPainterPath()
        path.addPolygon(QPolygonF([
            self.world_to_screen(node_a.origin),
            self.world_to_screen(node_a.hit_point),
            self.world_to_screen(node_b.hit_point),
            self.world_to_screen(node_b.origin),
        ]))
        painter.fillPath(path, QBrush(color))

        self._draw_quad_pair(painter, node_a.reflected, node_b.reflected)
        self._draw_quad_pair(painter, node_a.refracted, node_b.refracted)

    # -- joints ------------------------------------------------------------

    def _draw_joints(self, painter):
        for obj in self.level.objects:
            for extra in obj.extra_components:
                if extra.type != "HingeJoint":
                    continue
                target_id = extra.args.get("connectedObjectId")
                target = self.level.find_by_id(target_id) if target_id else None
                anchor = extra.args.get("anchor")

                painter.setPen(QPen(JOINT_COLOR, 1.2, Qt.PenStyle.DashLine))
                if target is not None:
                    painter.drawLine(self.world_to_screen(V(obj.x, obj.y)),
                                     self.world_to_screen(V(target.x, target.y)))
                if anchor is not None:
                    point = self.world_to_screen(V(float(anchor.x), float(anchor.y)))
                    painter.setPen(QPen(JOINT_COLOR, 1.4))
                    painter.drawEllipse(point, 4, 4)
                    painter.drawLine(point + QPointF(-6, 0), point + QPointF(6, 0))
                    painter.drawLine(point + QPointF(0, -6), point + QPointF(0, 6))
                    if obj in self.selection:
                        self._add_handle(Handle(
                            ("anchor", id(obj), id(extra)),
                            V(float(anchor.x), float(anchor.y)),
                            lambda world, e=extra: self._drag_anchor(e, world),
                            color=JOINT_COLOR, shape="circle", radius=5.0,
                        ))

    def _drag_anchor(self, extra, world):
        from ..luaio.types import Vec2
        existing = extra.args.get("anchor")
        style = existing.style if isinstance(existing, Vec2) else Vec2.TABLE
        extra.args["anchor"] = Vec2(self.snap(world.x), self.snap(world.y), style)

    # -- detectors ---------------------------------------------------------

    def _draw_detectors(self, painter):
        for obj, lit in self._detectors:
            point = self.world_to_screen(V(obj.x, obj.y))
            painter.setPen(QPen(DETECTOR_LIT if lit else DETECTOR_DARK, 1.4))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawEllipse(point, 7, 7)
            if lit:
                painter.setBrush(QBrush(DETECTOR_LIT))
                painter.drawEllipse(point, 2.5, 2.5)
                painter.setBrush(Qt.BrushStyle.NoBrush)

    # -- selection ---------------------------------------------------------

    def _object_extent(self, obj):
        return sprites.object_extent(self.resolve(obj), self.project)

    def _draw_selection(self, painter, obj):
        half_w, half_h = self._object_extent(obj)
        screen = self.world_to_screen(V(obj.x, obj.y))

        painter.save()
        painter.translate(screen)
        painter.rotate(math.degrees(obj.angle()))
        painter.setPen(QPen(SELECTION, 1.2, Qt.PenStyle.DashLine))
        painter.setBrush(QBrush(SELECTION_FILL))
        painter.drawRect(QRectF(-half_w * self.zoom, -half_h * self.zoom,
                                half_w * 2 * self.zoom, half_h * 2 * self.zoom))
        painter.restore()

        painter.setPen(QPen(SELECTION, 1.4))
        painter.drawLine(screen + QPointF(-7, 0), screen + QPointF(7, 0))
        painter.drawLine(screen + QPointF(0, -7), screen + QPointF(0, 7))

        # Rotation handle, on a stalk that stays a constant length on screen so
        # it is reachable whether the object is a 4 px anchor or a 320 px floor.
        arm = (max(half_w, half_h) + 18.0 / self.zoom)
        tip = V(obj.x + math.cos(obj.angle()) * arm,
                obj.y + math.sin(obj.angle()) * arm)
        painter.setPen(QPen(SELECTION, 1, Qt.PenStyle.DotLine))
        painter.drawLine(screen, self.world_to_screen(tip))
        self._add_handle(Handle(
            ("rotate", id(obj)), tip,
            lambda world, o=obj: self._drag_rotation(o, world),
            color=SELECTION, shape="circle", radius=4.5,
            cursor=Qt.CursorShape.CrossCursor,
        ))

    def _drag_rotation(self, obj, world):
        angle = math.atan2(world.y - obj.y, world.x - obj.x)
        if self.snap_enabled:
            step = math.radians(15)
            angle = round(angle / step) * step
        obj.set_angle(round(angle, 6), keep_zero=obj.rotation is not None)
        self.mark_light_dirty()

    def _draw_label(self, painter, obj):
        font = QFont(painter.font())
        font.setPointSizeF(7.5)
        painter.setFont(font)
        painter.setPen(QPen(QColor(200, 200, 215)))
        screen = self.world_to_screen(V(obj.x, obj.y))
        painter.drawText(QPointF(screen.x() + 8, screen.y() - 8), obj.label())

    def _draw_marquee(self, painter):
        painter.setPen(QPen(SELECTION, 1, Qt.PenStyle.DashLine))
        painter.setBrush(QBrush(QColor(255, 170, 60, 20)))
        painter.drawRect(self._marquee)
        painter.setBrush(Qt.BrushStyle.NoBrush)

    def _draw_placement_ghost(self, painter):
        position = V(self.snap(self._cursor_world.x), self.snap(self._cursor_world.y))
        screen = self.world_to_screen(position)
        painter.setPen(QPen(GHOST, 1.2, Qt.PenStyle.DashLine))
        painter.setBrush(Qt.BrushStyle.NoBrush)

        definition = self.library.find(self.placement_prefab) if self.library else None
        half_w, half_h = sprites.object_extent(definition, self.project)
        painter.drawRect(QRectF(screen.x() - half_w * self.zoom,
                                screen.y() - half_h * self.zoom,
                                half_w * 2 * self.zoom, half_h * 2 * self.zoom))
        painter.setPen(QPen(GHOST))
        painter.drawText(QPointF(screen.x() + 8, screen.y() - 8),
                         f"place {self.placement_prefab}")

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
            distance = math.hypot(screen.x() - position.x(),
                                  screen.y() - position.y())
            if distance <= max(best_distance, handle.radius + 4):
                if distance < best_distance or best is None:
                    best, best_distance = handle, distance
        return best

    def _draw_hud(self, painter):
        font = QFont(painter.font())
        font.setPointSizeF(8.5)
        painter.setFont(font)
        painter.setPen(QPen(QColor(150, 150, 165)))
        snap = f"snap {self.snap_step:g}px" if self.snap_enabled else "snap off"
        cursor = f"{self._cursor_world.x:.0f}, {self._cursor_world.y:.0f}"
        count = len(self.level.objects) if self.level else 0
        painter.drawText(8, self.height() - 8,
                         f"zoom {self.zoom:.2f}x   {snap}   cursor {cursor}   "
                         f"{count} objects   {len(self.selection)} selected")

    # -- picking -----------------------------------------------------------

    def object_at(self, world):
        """Topmost object under a world point. Later in the list wins, since
        that is what paints last."""
        if self.level is None:
            return None
        for obj in reversed(self.level.objects):
            half_w, half_h = self._object_extent(obj)
            local = _rotate(V(world.x - obj.x, world.y - obj.y), -obj.angle())
            # A generous minimum keeps 4 px anchors clickable when zoomed out.
            pad = 3.0 / max(self.zoom, 0.001)
            if abs(local.x) <= half_w + pad and abs(local.y) <= half_h + pad:
                return obj
        return None

    def objects_in_rect(self, rect):
        found = []
        for obj in self.level.objects:
            if rect.contains(self.world_to_screen(V(obj.x, obj.y))):
                found.append(obj)
        return found

    # -- interaction -------------------------------------------------------

    def mousePressEvent(self, event):
        button = event.button()
        position = event.position()

        # Tile mode owns the left and right buttons: right-drag erases, which
        # is worth more during a paint session than right-drag panning. Middle
        # still pans, so there is always a way to move the view.
        if self.tile_mode and button in (Qt.MouseButton.LeftButton,
                                         Qt.MouseButton.RightButton):
            self._tile_press(event)
            return

        if button == Qt.MouseButton.MiddleButton or (
                button == Qt.MouseButton.RightButton
                and self.placement_prefab is None):
            self._panning = True
            self._last_mouse = position.toPoint()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
            return

        if button != Qt.MouseButton.LeftButton:
            return

        world = self.screen_to_world(position)

        if self.placement_prefab:
            self._place(world, additive=bool(
                event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
            return

        handle = self._handle_at(position)
        if handle is not None:
            self._active_handle = handle
            self.editStarted.emit()
            return

        hit = self.object_at(world)
        additive = bool(event.modifiers() & (Qt.KeyboardModifier.ShiftModifier
                                             | Qt.KeyboardModifier.ControlModifier))
        if hit is None:
            if not additive:
                self.set_selection([])
            self._marquee = QRectF(position, position)
            self._last_mouse = position.toPoint()
            return

        if additive:
            if hit in self.selection:
                self.selection.remove(hit)
            else:
                self.selection.append(hit)
            self.selectionChanged.emit()
        elif hit not in self.selection:
            self.set_selection([hit])

        self._dragging = True
        self._drag_origin = world
        self._drag_start = [(o, o.x, o.y) for o in self.selection]
        self.editStarted.emit()
        self.setCursor(Qt.CursorShape.SizeAllCursor)
        self.update()

    def mouseMoveEvent(self, event):
        position = event.position()
        self._cursor_world = self.screen_to_world(position)

        if self.tile_mode and not self._panning:
            self._tile_move()
            if self._tile_stroke is not None:
                return

        if self._panning:
            current = position.toPoint()
            delta = current - self._last_mouse
            self.pan += QPointF(delta.x(), delta.y())
            self._last_mouse = current
            self.update()
            return

        if self._marquee is not None:
            self._marquee = QRectF(QPointF(self._last_mouse), position).normalized()
            self.update()
            return

        if self._active_handle is not None:
            self._active_handle.on_drag(self.screen_to_world(position))
            self.modelChanged.emit()
            self.update()
            return

        if self._dragging:
            world = self.screen_to_world(position)
            dx = world.x - self._drag_origin.x
            dy = world.y - self._drag_origin.y
            for obj, start_x, start_y in self._drag_start:
                obj.move_to(self.snap(start_x + dx), self.snap(start_y + dy))
            self.mark_light_dirty()
            self.modelChanged.emit()
            self.update()
            return

        if self.placement_prefab:
            self.update()
            return

        hover = self._handle_at(position)
        if hover is not self._hover_handle:
            self._hover_handle = hover
            self.setCursor(hover.cursor if hover else Qt.CursorShape.ArrowCursor)
            self.update()

    def mouseReleaseEvent(self, event):
        if self._tile_stroke is not None:
            self._tile_release()
            return

        if self._panning:
            self._panning = False
            self.setCursor(Qt.CursorShape.ArrowCursor)

        if self._marquee is not None:
            rect = self._marquee
            self._marquee = None
            if rect.width() > 3 or rect.height() > 3:
                found = self.objects_in_rect(rect)
                additive = bool(event.modifiers()
                                & (Qt.KeyboardModifier.ShiftModifier
                                   | Qt.KeyboardModifier.ControlModifier))
                self.set_selection(self.selection + found if additive else found)
            self.update()

        if self._active_handle is not None:
            self._active_handle = None
            self.mark_light_dirty()
            self.modelChanged.emit()

        if self._dragging:
            self._dragging = False
            self.setCursor(Qt.CursorShape.ArrowCursor)
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
        key = event.key()

        if key == Qt.Key.Key_Escape and self.placement_prefab:
            self.arm_placement(None)
            self.placementFinished.emit()
            return

        if key in (Qt.Key.Key_Delete, Qt.Key.Key_Backspace) and self.selection:
            self.delete_selection()
            return

        if key == Qt.Key.Key_F:
            self.frame_selection() if self.selection else self.frame_screen()
            return

        nudges = {
            Qt.Key.Key_Left: (-1, 0), Qt.Key.Key_Right: (1, 0),
            Qt.Key.Key_Up: (0, -1), Qt.Key.Key_Down: (0, 1),
        }
        if key in nudges and self.selection:
            step = self.snap_step if self.snap_enabled and self.snap_step > 0 else 1.0
            if event.modifiers() & Qt.KeyboardModifier.ShiftModifier:
                step = 1.0
            dx, dy = nudges[key]
            self.editStarted.emit()
            for obj in self.selection:
                obj.move_to(round(obj.x + dx * step, 4), round(obj.y + dy * step, 4))
            self.mark_light_dirty()
            self.modelChanged.emit()
            return

        super().keyPressEvent(event)

    # -- tile painting -----------------------------------------------------

    def set_tile_target(self, obj):
        self.tile_target = obj
        self.update()

    def _tile_press(self, event):
        binding = self.tile_binding(self.tile_target)
        if binding is None:
            self.statusMessage.emit(
                "Tile mode is on but no tilemap is selected -- pick one in the "
                "Tiles panel.")
            return

        world = self.screen_to_world(event.position())
        cell = binding.cell_at_world_unclamped(world.x, world.y)
        self._tile_hover = cell

        alt = bool(event.modifiers() & Qt.KeyboardModifier.AltModifier)
        erasing = event.button() == Qt.MouseButton.RightButton

        if alt or self.tile_tool == "picker":
            if binding.in_bounds(*cell):
                self.tilePicked.emit(binding.tile_at(*cell))
            self.update()
            return

        tool = "eraser" if erasing else self.tile_tool
        self._tile_erasing = erasing or tool == "eraser"

        if tool == "rect":
            # Nothing is written until the release, so a rectangle can be
            # cancelled by dragging back to a degenerate size and no undo
            # snapshot is spent on the preview.
            self._tile_stroke = "rect"
            self._tile_rect_origin = cell
            self.update()
            return

        # One snapshot for the whole drag, pushed before the first cell
        # changes: a stroke is one action to undo, not forty.
        self.editStarted.emit()
        self._tile_stroke = tool

        if tool == "fill":
            if binding.flood_fill(cell[0], cell[1], self._stroke_id()):
                self.modelChanged.emit()
            self._tile_stroke = None
            self.update()
            return

        self._tile_paint_cell(binding, cell)

    def _tile_move(self):
        binding = self.tile_binding(self.tile_target)
        if binding is None:
            return
        cell = binding.cell_at_world_unclamped(self._cursor_world.x,
                                               self._cursor_world.y)
        if cell != self._tile_hover:
            self._tile_hover = cell
            self.update()

        if self._tile_stroke in ("brush", "eraser"):
            self._tile_paint_cell(binding, cell)

    def _tile_release(self):
        binding = self.tile_binding(self.tile_target)
        if self._tile_stroke == "rect" and binding is not None \
                and self._tile_rect_origin is not None and self._tile_hover is not None:
            self.editStarted.emit()
            col0, row0 = self._tile_rect_origin
            col1, row1 = self._tile_hover
            if binding.fill_rect(col0, row0, col1, row1, self._stroke_id()):
                self.modelChanged.emit()

        self._tile_stroke = None
        self._tile_rect_origin = None
        self._tile_erasing = False
        self.modelChanged.emit()
        self.update()

    def _stroke_id(self):
        return 0 if self._tile_erasing else int(self.tile_id)

    def _tile_paint_cell(self, binding, cell):
        if binding.paint(cell[0], cell[1], self._stroke_id()):
            self.modelChanged.emit()
        self.update()

    # -- mutations ---------------------------------------------------------

    def _place(self, world, additive=False):
        from ..model.level import LevelObject
        from ..luaio.types import Vec2

        self.editStarted.emit()
        obj = LevelObject(
            self.placement_prefab,
            Vec2(self.snap(world.x), self.snap(world.y), Vec2.TABLE),
        )
        self.level.add(obj)
        self.set_selection([obj])
        self.mark_light_dirty()
        self.modelChanged.emit()
        self.statusMessage.emit(
            f"Placed {obj.prefab} at ({obj.x:g}, {obj.y:g})")
        if not additive:
            self.arm_placement(None)
            self.placementFinished.emit()

    def delete_selection(self):
        if not self.selection:
            return
        self.editStarted.emit()
        removed = [o.label() for o in self.selection]
        for obj in list(self.selection):
            self.level.remove(obj)
        self.set_selection([])
        self.mark_light_dirty()
        self.modelChanged.emit()
        self.statusMessage.emit(f"Deleted {', '.join(removed)}")

    def duplicate_selection(self):
        if not self.selection:
            return
        self.editStarted.emit()
        copies = []
        for obj in self.selection:
            clone = obj.clone()
            if clone.id:
                clone.id = self.level.unique_id(clone.id)
            clone.move_to(obj.x + (self.snap_step or 8), obj.y + (self.snap_step or 8))
            self.level.add(clone)
            copies.append(clone)
        self.set_selection(copies)
        self.mark_light_dirty()
        self.modelChanged.emit()
        self.statusMessage.emit(f"Duplicated {len(copies)} object(s)")


def _rotate(vector, angle):
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return V(vector.x * cos_a - vector.y * sin_a,
             vector.x * sin_a + vector.y * cos_a)
