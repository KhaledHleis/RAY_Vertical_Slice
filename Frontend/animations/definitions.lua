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
-- See Libraries/animation/clip.lua for the full contract.

return {
    -- coin.png is 64x16: one row of four 16x16 cells, so the frame size is
    -- inferred and only the cell order is spelled out.
    CoinSpin = {
        path   = "Resources/sprites/test/coin.png",
        fps    = 10,
        frames = { 0, 1, 2, 3 },
        events = {
            -- Fires as the coin turns edge-on -- something for audio or a
            -- light flicker to hang off later.
            { at = 3, name = "coin:glint" },
        },
    },

    -- Player clips. Uncomment once there is a sheet, then hand PlayerRenderer
    -- its state map and add an AnimationPlayer targeting it:
    --
    --   { type = "PlayerRenderer",  args = { animations = {
    --         idle = "PlayerIdle", run = "PlayerRun",
    --         jump = "PlayerJump", fall = "PlayerFall",
    --   } } },
    --   { type = "AnimationPlayer", args = { target = "PlayerRenderer" } },
    --
    -- Until then PlayerRenderer draws its fallback rectangle exactly as
    -- before, so the controller stays playable with no art.
    --
    -- PlayerIdle = {
    --     path = "Resources/sprites/player.png",
    --     frameWidth = 16, frameHeight = 16,
    --     fps = 6, row = 0, count = 4,
    -- },
    --
    -- PlayerRun = {
    --     path = "Resources/sprites/player.png",
    --     frameWidth = 16, frameHeight = 16,
    --     fps = 12, row = 1, count = 8,
    --     -- the old PlayerRenderer `steps = { 0, 4 }`, now owned by the clip
    --     events = {
    --         { at = 1, name = "player:step" },
    --         { at = 5, name = "player:step" },
    --     },
    -- },
    --
    -- PlayerJump = {
    --     path = "Resources/sprites/player.png",
    --     frameWidth = 16, frameHeight = 16,
    --     row = 2, count = 1, mode = "once",
    -- },
}
