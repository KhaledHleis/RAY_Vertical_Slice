"""The tile grid, as the editor sees it.

A tilemap is not a new kind of entry in the level file. It is an ordinary object
whose prefab carries a `Tilemap` component, and every paint stroke lands in the
same `LevelObject.overrides` bucket that every other per-instance edit uses. So
undo, the diff-on-save dialog, the round-trip guarantees and the writer all work
on tile data without knowing anything about tiles.

`TilemapBinding` is the read/write view over that bucket. It resolves the
effective value of each argument the way `Prefab.Instantiate` would -- override
first, prefab default second -- and writes only to the override.

One rule it enforces on every write: `width` and `height` are always stored
alongside `tiles`. The grid is flat, so without the width the array is a bag of
numbers that neither the writer nor the engine can shape back into a map.

Kept free of Qt so the tests and the lint can use it.
"""

from __future__ import annotations

COMPONENT = "Tilemap"

EMPTY = 0


def component_of(obj, library):
    """The prefab's `Tilemap` component for `obj`, or None.

    Deliberately the *prefab's* component rather than the resolved one: the
    binding layers overrides on top itself, and resolving would flatten the
    distinction it needs to keep.
    """
    if obj is None or library is None:
        return None
    definition = library.find(obj.prefab)
    if definition is None:
        return None
    return definition.find(COMPONENT)


def is_tilemap(obj, library):
    return component_of(obj, library) is not None


def tilemap_objects(level, library):
    if level is None or library is None:
        return []
    return [o for o in level.objects if is_tilemap(o, library)]


class TilemapBinding:
    """Read/write view of one object's tile grid."""

    def __init__(self, obj, library):
        self.obj = obj
        self.library = library
        self.component = component_of(obj, library)

    def __bool__(self):
        return self.component is not None

    # -- argument access ---------------------------------------------------

    def get(self, name, default=None):
        bucket = self.obj.overrides.get(COMPONENT, {})
        if name in bucket:
            return bucket[name]
        if self.component is not None:
            value = self.component.args.get(name)
            if value is not None:
                return value
        return default

    def set(self, name, value):
        self.obj.override(COMPONENT, name, value)

    @property
    def tileset(self):
        return self.get("tileset")

    @property
    def tile_width(self):
        return max(1, int(self.get("tileWidth", 16) or 16))

    @property
    def tile_height(self):
        return max(1, int(self.get("tileHeight", 16) or 16))

    @property
    def width(self):
        return max(0, int(self.get("width", 0) or 0))

    @property
    def height(self):
        return max(0, int(self.get("height", 0) or 0))

    @property
    def columns(self):
        value = self.get("columns")
        return int(value) if value else None

    @property
    def tiles(self):
        """The grid, padded or trimmed to width * height.

        A hand-edited file can easily hold an array that does not match the
        declared size. Normalising on read means every consumer -- the viewport,
        the flood fill, the writer -- sees a rectangle, and the lint reports the
        mismatch separately rather than every one of them having to cope.
        """
        raw = self.get("tiles") or []
        cells = self.width * self.height
        values = [int(t) for t in raw]
        if len(values) < cells:
            values.extend([EMPTY] * (cells - len(values)))
        return values[:cells]

    # -- grid ops ----------------------------------------------------------

    def index(self, col, row):
        return row * self.width + col

    def in_bounds(self, col, row):
        return 0 <= col < self.width and 0 <= row < self.height

    def tile_at(self, col, row):
        if not self.in_bounds(col, row):
            return EMPTY
        return self.tiles[self.index(col, row)]

    def _commit(self, values):
        """Write the grid back, always with the size that shapes it."""
        self.set("tiles", [int(v) for v in values])
        self.set("width", self.width)
        self.set("height", self.height)

    def paint(self, col, row, tile_id):
        """Set one cell. Returns True when something actually changed."""
        if not self.in_bounds(col, row):
            return False
        values = self.tiles
        position = self.index(col, row)
        if values[position] == tile_id:
            return False
        values[position] = int(tile_id)
        self._commit(values)
        return True

    def paint_many(self, cells, tile_id):
        """Set a batch of (col, row) cells in one write.

        One commit rather than one per cell: `_commit` copies the whole array,
        so a rectangle fill done cell by cell would be quadratic.
        """
        values = self.tiles
        changed = False
        for col, row in cells:
            if not self.in_bounds(col, row):
                continue
            position = self.index(col, row)
            if values[position] != tile_id:
                values[position] = int(tile_id)
                changed = True
        if changed:
            self._commit(values)
        return changed

    def fill_rect(self, col0, row0, col1, row1, tile_id):
        left, right = sorted((int(col0), int(col1)))
        top, bottom = sorted((int(row0), int(row1)))
        cells = [(c, r)
                 for r in range(top, bottom + 1)
                 for c in range(left, right + 1)]
        return self.paint_many(cells, tile_id)

    def flood_fill(self, col, row, tile_id):
        """Four-way flood fill of the contiguous run of like tiles."""
        if not self.in_bounds(col, row):
            return False
        values = self.tiles
        target = values[self.index(col, row)]
        if target == tile_id:
            return False

        width, height = self.width, self.height
        stack = [(col, row)]
        seen = set()
        changed = False
        while stack:
            c, r = stack.pop()
            if (c, r) in seen or not (0 <= c < width and 0 <= r < height):
                continue
            seen.add((c, r))
            position = r * width + c
            if values[position] != target:
                continue
            values[position] = int(tile_id)
            changed = True
            stack.extend(((c + 1, r), (c - 1, r), (c, r + 1), (c, r - 1)))

        if changed:
            self._commit(values)
        return changed

    def resize(self, width, height):
        """Change the map size, keeping whatever tiles still fit.

        Anchored at the top-left, which is where the transform is: growing a map
        must not move the tiles already painted, or every collider placed over
        them would need moving too.
        """
        width = max(0, int(width))
        height = max(0, int(height))
        if width == self.width and height == self.height:
            return False

        old_width, old_height = self.width, self.height
        old = self.tiles
        values = [EMPTY] * (width * height)
        for r in range(min(old_height, height)):
            for c in range(min(old_width, width)):
                values[r * width + c] = old[r * old_width + c]

        self.set("width", width)
        self.set("height", height)
        self.set("tiles", values)
        return True

    def clear(self):
        return self.paint_many(
            [(c, r) for r in range(self.height) for c in range(self.width)],
            EMPTY)

    # -- geometry ----------------------------------------------------------

    def cell_at_world(self, world_x, world_y):
        """The cell containing a world point, or None when outside the map.

        Mirrors `Tilemap:CellAt`: the object's position is the top-left corner,
        and rotation is ignored on both sides.
        """
        scale = self.obj.world_scale() or 1.0
        col = int((world_x - self.obj.x) // (self.tile_width * scale))
        row = int((world_y - self.obj.y) // (self.tile_height * scale))
        if not self.in_bounds(col, row):
            return None
        return col, row

    def cell_at_world_unclamped(self, world_x, world_y):
        """Like `cell_at_world`, but returns cells outside the map too.

        The hover highlight wants to show where a stroke *would* land while the
        cursor is off the edge, without pretending the paint would take.
        """
        scale = self.obj.world_scale() or 1.0
        import math
        return (math.floor((world_x - self.obj.x) / (self.tile_width * scale)),
                math.floor((world_y - self.obj.y) / (self.tile_height * scale)))

    def world_rect(self):
        """(x, y, width, height) of the whole map in world pixels."""
        scale = self.obj.world_scale() or 1.0
        return (self.obj.x, self.obj.y,
                self.width * self.tile_width * scale,
                self.height * self.tile_height * scale)


def tileset_columns(binding, project):
    """Tiles per row in the tileset image.

    The authored `columns` wins when set; otherwise it is derived from the image
    width exactly as the engine derives it, so the editor and the game agree on
    what tile id 7 means.
    """
    explicit = binding.columns
    if explicit:
        return explicit
    if project is None or not binding.tileset:
        return None
    from . import sprites
    absolute = project.resolve(binding.tileset)
    if not absolute:
        return None
    size = sprites.image_size(absolute)
    if not size:
        return None
    return max(1, size[0] // binding.tile_width)


def tileset_tile_count(binding, project):
    """How many tiles the sheet holds, or None when it cannot be measured."""
    if project is None or not binding.tileset:
        return None
    from . import sprites
    absolute = project.resolve(binding.tileset)
    if not absolute:
        return None
    size = sprites.image_size(absolute)
    if not size:
        return None
    columns = max(1, size[0] // binding.tile_width)
    rows = max(1, size[1] // binding.tile_height)
    return columns * rows
