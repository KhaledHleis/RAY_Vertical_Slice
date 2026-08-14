-- Tilemap regression checks. Runs outside LOVE, on plain lua5.1:
--
--     lua5.1 Tools/engine_tests/tilemap_test.lua
--
-- Two things are worth guarding here. The first is the index formula: the
-- editor writes a flat row-major array and the engine reads it back, and if the
-- two ever disagree about what `tiles[n]` means, every map in the game shifts
-- by a row and nothing says why.
--
-- The second is the SpriteBatch. It is the only GPU allocation the component
-- makes, LevelManager's teardown assumes it goes away with the level, and a
-- batch leaked per level switch is invisible until the handheld runs out.

package.path = "./?.lua;./?/init.lua;" .. package.path

local mock = require('Tools.engine_tests.love_mock')
mock.install()

local Object = require('Libraries.universal.object')
local Prefab = require('Libraries.universal.prefab')
local Vector = require('Libraries.transform.vector')
local Tilemap = require('Libraries.renderer.tilemap')

local failures = 0
local function check(label, ok, detail)
    print((ok and "  ok   " or "  FAIL ") .. label
        .. (detail and ("  -> " .. tostring(detail)) or ""))
    if not ok then failures = failures + 1 end
end

-- The mock's newImage reports 64x64, so a 16 px tile means 4 columns.
local function newMap(overrides)
    local args = {
        tileset = "Resources/sprites/test/box.png",
        tileWidth = 16,
        tileHeight = 16,
        width = 4,
        height = 3,
        tiles = {
            0, 1, 2, 3,
            4, 0, 0, 5,
            6, 7, 8, 0,
        },
    }
    for key, value in pairs(overrides or {}) do args[key] = value end
    return Tilemap.new(args)
end

-- geometry -------------------------------------------------------------------

local map = newMap()
check("columns derived from the sheet width", map.columns == 4, map.columns)

-- Row-major, 0-based col/row, 1-based array: index = row * width + col + 1.
check("cell (1, 0) reads the second entry", map:GetTile(1, 0) == 1, map:GetTile(1, 0))
check("cell (0, 1) reads entry width+1", map:GetTile(0, 1) == 4, map:GetTile(0, 1))
check("cell (2, 2) reads the last row", map:GetTile(2, 2) == 8, map:GetTile(2, 2))
check("out of bounds reads as empty", map:GetTile(9, 9) == 0)
check("negative indices read as empty", map:GetTile(-1, 0) == 0)

check("InBounds accepts the far corner", map:InBounds(3, 2))
check("InBounds rejects one past it", not map:InBounds(4, 2))

check("SetTile reports a change", map:SetTile(0, 0, 9))
check("SetTile wrote the cell", map:GetTile(0, 0) == 9)
check("SetTile is a no-op for the same value", not map:SetTile(0, 0, 9))
check("SetTile refuses out of bounds", not map:SetTile(9, 9, 1))

-- world <-> cell, against the transform ---------------------------------------
--
-- The position is the TOP-LEFT of cell (0, 0), which is the whole reason the
-- editor can paint into it without a half-tile fudge.

local object = Object.new(Vector.new(32, 16))
object:AddComponent(map)

local col, row = map:CellAt(object, 32, 16)
check("the object position is cell (0, 0)", col == 0 and row == 0,
      tostring(col) .. "," .. tostring(row))

col, row = map:CellAt(object, 47.9, 16)
check("a point inside the first cell stays there", col == 0 and row == 0,
      tostring(col) .. "," .. tostring(row))

col, row = map:CellAt(object, 48, 32)
check("one tile right and down is cell (1, 1)", col == 1 and row == 1,
      tostring(col) .. "," .. tostring(row))

check("a point before the origin is off the map", map:CellAt(object, 0, 0) == nil)

-- Scale multiplies the cell size, matching Transform:World.
local scaled = Object.new(Vector.new(0, 0), 0, 2)
local scaledMap = newMap()
scaled:AddComponent(scaledMap)
col, row = scaledMap:CellAt(scaled, 32, 0)
check("scale 2 makes cells 32 px wide", col == 1 and row == 0,
      tostring(col) .. "," .. tostring(row))

-- the batch ------------------------------------------------------------------

local before = mock.counts().batches
map:Draw(object)
check("Draw allocated one batch", mock.counts().batches == before + 1,
      mock.counts().batches)

-- Only the non-zero cells are added: an empty cell must not cost a sprite.
local painted = 0
for _, id in ipairs(map.tiles) do if id > 0 then painted = painted + 1 end end
check("the batch holds only the painted cells",
      map.batch:getCount() == painted, map.batch:getCount() .. " vs " .. painted)

local batchesAfterFirstDraw = mock.counts().batches
map:Draw(object)
check("a clean redraw does not reallocate",
      mock.counts().batches == batchesAfterFirstDraw, mock.counts().batches)

map:SetTile(1, 1, 3)
map:Draw(object)
check("editing a cell rebuilds in place, not into a new batch",
      mock.counts().batches == batchesAfterFirstDraw, mock.counts().batches)
check("the rebuilt batch counts the new cell",
      map.batch:getCount() == painted + 1, map.batch:getCount())

map:OnDestroy(object)
check("OnDestroy released the batch", mock.counts().batches == before,
      mock.counts().batches)
check("OnDestroy dropped the reference", map.batch == nil)

-- A second teardown is what Scene:Clear can produce for an object already
-- queued for destruction; it must not double-release.
map:OnDestroy(object)
check("a second OnDestroy is harmless", mock.counts().batches == before,
      mock.counts().batches)

-- no tileset -----------------------------------------------------------------
--
-- Draw returns early rather than erroring, so a map whose tileset is missing
-- from the level file costs a blank screen and not a crash.

local blank = Tilemap.new({ width = 2, height = 2, tiles = { 1, 1, 1, 1 } })
local blankObject = Object.new(Vector.new(0, 0))
blankObject:AddComponent(blank)
local ok = pcall(function() blank:Draw(blankObject) end)
check("Draw with no tileset is safe", ok)
check("and allocates nothing", blank.batch == nil)

-- through the prefab pipeline -------------------------------------------------
--
-- The level file reaches the component through Prefab.Instantiate's mergeArgs,
-- so the grid has to survive being an override rather than a prefab default.

Prefab.Register(require('Frontend.prefabs.definitions'))
local instance = Prefab.Instantiate("Tilemap", {
    position = Vector.new(0, 0),
    components = {
        Tilemap = {
            tileset = "Resources/sprites/test/box.png",
            width = 2,
            height = 2,
            tiles = { 0, 1, 2, 0 },
        },
    },
})

-- Object keys its components by tostring(component), so the registry name and
-- the __tostring metamethod have to agree -- which is itself worth asserting.
local component = instance:GetComponent("Tilemap")

check("the Tilemap prefab exists", component ~= nil)
if component then
    check("the override carried the grid", component:GetTile(1, 0) == 1,
          component:GetTile(1, 0))
    check("the override carried the size",
          component.width == 2 and component.height == 2,
          component.width .. "x" .. component.height)
    component:Draw(instance)
    check("an instantiated map draws", component.batch ~= nil)
    check("skipping the empty cells", component.batch:getCount() == 2,
          component.batch:getCount())
    instance:Destroy()
end

print("")
if failures > 0 then
    print(failures .. " CHECK(S) FAILED")
    os.exit(1)
end
print("ALL CHECKS PASSED")
