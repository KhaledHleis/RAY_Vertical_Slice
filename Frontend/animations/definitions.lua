-- Animation clip definitions.
--
-- Registered once in main.lua and referenced by name from component args, so
-- a prefab only ever carries strings and stays round-trippable through
-- Tools/prefab_editor.
--
-- Fields, all optional except the sheet:
--
--   path         sheet to draw from (required unless `image` is passed)
--   frameWidth   defaults to frameHeight
--   frameHeight  defaults to the image height -- a single-row strip of square
--                frames therefore needs neither
--   fps          default 8
--   mode         "loop" (default) | "once" | "pingpong"
--   frames       flat cell indices, or { col, row } pairs; cells are 0-based
--   row/count    walk one row instead of listing frames
--   durations    per-frame seconds, overriding fps frame by frame
--   speed        baked-in multiplier, on top of AnimationPlayer's
--   events       { { at = <1-based frame position>, name = "some:event" } }
--
-- See Libraries/animation/clip.lua.

return {
    -- coin.png is 64x16: one row of four 16x16 cells, so the frame size is
    -- inferred and only the cell order is spelled out.
    CoinSpin = {
        path   = "Resources/sprites/test/coin.png",
        fps    = 10,
        frames = { 0, 1, 2, 3 },
        mode = "pingpong",
        events = {
            -- Fires as the coin turns edge-on -- something for audio or a
            -- light flicker to hang off later.
            { at = 3, name = "coin:glint" },
        },
    },


    -- Until then PlayerRenderer draws its fallback rectangle exactly as
    -- before, so the controller stays playable with no art.
    --
    PlayerIdle = {
        path = "Resources/sprites/player/ray_idle.png",
        frameWidth = 32, frameHeight = 32,
        fps = 6, row = 0, count = 3,
    },
    
    PlayerRun = {
        path = "Resources/sprites/player/ray_walk.png",
        frameWidth = 32, frameHeight = 32,
        fps = 12, row = 0, count = 6,
        -- the old PlayerRenderer `steps = { 0, 4 }`, now owned by the clip
        events = {
            { at = 1, name = "player:step" },
            { at = 5, name = "player:step" },
        },
    },
    
    PlayerJump = {
        path = "Resources/sprites/player/ray_jump.png",
        frameWidth = 32, frameHeight = 32,
        row = 0, count = 2, mode = "once",
    },

    PlayerFall = {
        path = "Resources/sprites/player/ray_jump.png",
        frameWidth = 32, frameHeight = 32,
        row = 0, count = 1, mode = "once",
    },

    -- door.png is 384x64: one row of six 64x64 cells, shut on the left and
    -- fully open on the right. `once` holds the last frame rather than
    -- snapping back, which is exactly what a door that stays open needs, and
    -- the "finished" event is what Door waits for before letting the player
    -- through -- so the count has to be right or the door reports itself open
    -- while still drawn shut.
    DoorOpen = {
        path = "Resources/sprites/door/door.png",
        frameWidth = 64, frameHeight = 64,
        fps = 12, row = 0, count = 6, mode = "once",
    },

    -- The same six cells walked backwards. A pingpong clip would loop the two
    -- together forever; this is a separate one-shot so Door can play either
    -- direction on demand.
    DoorClose = {
        path = "Resources/sprites/door/door.png",
        frameWidth = 64, frameHeight = 64,
        fps = 12, mode = "once",
        frames = { 5, 4, 3, 2, 1, 0 },
    },
}
