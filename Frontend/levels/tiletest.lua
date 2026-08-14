-- Level definition, loaded by Level.load('Frontend.levels.<name>', scene).
--
-- Edited with Tools/level_editor. The list order is the draw order: Scene:Draw
-- walks it with ipairs, so later entries paint over earlier ones.

return {
    -- Painted with Tools/level_editor -- Tile mode in the toolbar.
    -- Scenery only: the colliders below are what makes any of it solid.
    {
        id = "ground",
        prefab = "Tilemap",
        position = { x = 0, y = 0 },
        components = {
            Tilemap = {
                tileset = "Resources/tilesets/debug_tiles.png",
                tileWidth = 16,
                tileHeight = 16,
                width = 20,
                height = 15,
                tiles = {
                    -- 20 x 15, row-major, 0 = empty
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 5, 5, 5, 5, 5, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 5, 5, 5, 5, 5, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 0, 0,
                    0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 7, 0, 0,
                    3, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3,
                    3, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 6, 3,
                },
            },
        },
    },

    -- Hand-placed, over the floor tiles. The tilemap registers no
    -- bodies and no light segments -- that stays authored.
    {
        id = "floor",
        prefab = "Box",
        position = { x = 160, y = 216 },
        components = {
            SpriteRenderer = {
                scale = { x = 0, y = 0 },
            },
            RigidBody = {
                bodyType = "static",
                width = 320,
                height = 32,
            },
        },
    },

    {
        id = "ledge",
        prefab = "Box",
        position = { x = 104, y = 152 },
        components = {
            SpriteRenderer = {
                scale = { x = 0, y = 0 },
            },
            RigidBody = {
                bodyType = "static",
                width = 80,
                height = 16,
            },
        },
    },

    {
        id = "player",
        prefab = "Player",
        position = { x = 40, y = 180 },
    },

    {
        prefab = "LightCone",
        position = { x = 240, y = 40 },
        rotation = 1.5707963268,
    },
}
