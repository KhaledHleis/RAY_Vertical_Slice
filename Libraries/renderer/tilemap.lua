local Component = require('Libraries.universal.component')

-- A whole grid of tiles drawn as ONE object and ONE draw call.
--
-- The reason this is a single component rather than one object per tile is
-- arithmetic. A 320x240 screen at 16 px is 20x15 = 300 cells; instantiating a
-- prefab per solid cell would put a few hundred entries in Scene.objects, a few
-- hundred draw calls in Scene:Draw, and -- the one that actually hurts -- a few
-- hundred bodies in the physics world and four segments per cell in
-- LightWorld.segments, which LightWorld.raycast walks linearly for every ray of
-- every bounce. One SpriteBatch costs one draw call and registers nothing.
--
-- Collision and light are deliberately NOT derived from the grid here. Place
-- RigidBody and LightCollider objects over the tiles by hand, in the level
-- editor, exactly as before: the tilemap is scenery that happens to be
-- efficient, and the puzzle geometry stays authored rather than inferred.
--
-- ORIGIN. Unlike SpriteRenderer, which centres its image on the transform, the
-- transform position here is the TOP-LEFT corner of cell (0, 0) and the grid
-- grows right and down. Centring a map whose size changes as you paint would
-- move every tile in it every time you widened it.
--
-- Tile ids are 1-based indices into the tileset, read left to right then top to
-- bottom. 0 means "no tile" and is skipped entirely, so an empty cell costs
-- nothing in the batch.
local Tilemap = setmetatable({}, { __index = Component })
Tilemap.__index = Tilemap

function Tilemap.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, Tilemap)

    self.tileWidth = args.tileWidth or 16
    self.tileHeight = args.tileHeight or 16
    self.width = args.width or 0
    self.height = args.height or 0
    self.tiles = args.tiles or {}
    self.color = args.color or { 1, 1, 1, 1 }
    self.visible = true

    self.image = args.image or (args.tileset and love.graphics.newImage(args.tileset))
    if self.image and self.image.setFilter then
        -- Pixel art: linear filtering on a tileset also bleeds neighbouring
        -- tiles into each other along the quad edges.
        self.image:setFilter("nearest", "nearest")
    end

    -- Tiles per row in the SOURCE image, which is what turns a tile id into a
    -- quad. Derived rather than authored so a wider tileset does not silently
    -- reshuffle every map that uses it -- but overridable for the case of a
    -- sheet with padding the engine cannot see.
    self.columns = args.columns
    if not self.columns and self.image then
        self.columns = math.max(1, math.floor(self.image:getWidth() / self.tileWidth))
    end

    self.batch = nil
    self._quads = {}
    self._dirty = true

    return self
end

function Tilemap:__tostring()
    return "Tilemap"
end

-- -- grid access ------------------------------------------------------------
--
-- Column and row are 0-based, matching the level file and the editor. The
-- backing array is 1-based and row-major, so index = row * width + col + 1.

function Tilemap:InBounds(col, row)
    return col >= 0 and row >= 0 and col < self.width and row < self.height
end

function Tilemap:GetTile(col, row)
    if not self:InBounds(col, row) then return 0 end
    return self.tiles[row * self.width + col + 1] or 0
end

function Tilemap:SetTile(col, row, id)
    if not self:InBounds(col, row) then return false end
    local index = row * self.width + col + 1
    if self.tiles[index] == id then return false end
    self.tiles[index] = id
    -- Marks the batch stale rather than rebuilding now: a fill loop setting a
    -- few hundred cells would otherwise rebuild once per cell.
    self._dirty = true
    return true
end

-- The cell containing a WORLD point, or nil when the point is off the map.
-- Rotation is not accounted for: a rotated tilemap is not something the editor
-- can paint into, so honouring it here would only make the two disagree.
function Tilemap:CellAt(object, worldX, worldY)
    local x, y, _angle, scale = object.transform:World()
    local col = math.floor((worldX - x) / (self.tileWidth * scale))
    local row = math.floor((worldY - y) / (self.tileHeight * scale))
    if not self:InBounds(col, row) then return nil end
    return col, row
end

-- -- rendering ---------------------------------------------------------------

function Tilemap:_quadFor(id)
    local cached = self._quads[id]
    if cached then return cached end
    if not self.image or not self.columns or self.columns < 1 then return nil end

    local zeroBased = id - 1
    local col = zeroBased % self.columns
    local row = math.floor(zeroBased / self.columns)
    local quad = love.graphics.newQuad(
        col * self.tileWidth, row * self.tileHeight,
        self.tileWidth, self.tileHeight,
        self.image:getDimensions()
    )
    self._quads[id] = quad
    return quad
end

function Tilemap:_rebuild()
    self._dirty = false
    if not self.image then return end

    local cells = self.width * self.height
    if not self.batch then
        -- "static" is the right usage hint even though painting in-game would
        -- re-add every sprite: a map is rebuilt on the rare edit, not per frame.
        self.batch = love.graphics.newSpriteBatch(self.image, math.max(1, cells), "static")
    else
        self.batch:clear()
    end

    for row = 0, self.height - 1 do
        for col = 0, self.width - 1 do
            local id = self.tiles[row * self.width + col + 1] or 0
            if id > 0 then
                local quad = self:_quadFor(id)
                if quad then
                    self.batch:add(quad, col * self.tileWidth, row * self.tileHeight)
                end
            end
        end
    end
end

function Tilemap:Draw(object)
    if not self.visible or not self.image then return end
    if self._dirty then self:_rebuild() end
    if not self.batch then return end

    local x, y, angle, scale = object.transform:World()
    love.graphics.setColor(self.color)
    -- No origin offset: (x, y) is the top-left of the map, so the batch's own
    -- local coordinates land where they were built.
    love.graphics.draw(self.batch, x, y, angle, scale, scale)
    love.graphics.setColor(1, 1, 1, 1)
end

-- The batch and the quads are GPU-side objects, and LevelManager's teardown
-- asserts that a level switch leaves nothing behind. Dropping the Lua
-- references would eventually do it, but "eventually" is a garbage collector
-- pass that may not run before the next level's batch is allocated.
function Tilemap:OnDestroy(object)
    if self.batch and self.batch.release then
        self.batch:release()
    end
    self.batch = nil
    for id, quad in pairs(self._quads) do
        if quad.release then quad:release() end
        self._quads[id] = nil
    end
end

return Tilemap
