-- Covers the detector -> door -> next level chain end to end, headlessly.
--
-- The three things worth pinning down, because each of them fails silently in
-- the game rather than crashing:
--
--   * the detector swaps its sprite on the lit transition and swaps back on
--     the lost one;
--   * the door only counts as passable once the open clip has *finished* --
--     a door that reports itself open on frame 1 lets the player walk through
--     a shut door;
--   * the doorway is a sensor, and someone already standing in it when the
--     puzzle is solved still triggers -- that beginContact happened seconds
--     earlier, so acting on the contact itself would miss it.

package.path = "./?.lua;./?/init.lua;" .. package.path

local mock = require('Tools.engine_tests.love_mock')
mock.install()

local Prefab       = require('Libraries.universal.prefab')
local Clip         = require('Libraries.animation.clip')
local LevelManager = require('Libraries.universal.level_manager')
local LightWorld   = require('Libraries.light_engine.light_world')
local EventBus     = require('Libraries.universal.event_bus')
local Screen       = require('Libraries.renderer.screen')
local Input        = require('Libraries.universal.input')
local Tune         = require('Libraries.universal.tune')
local Vector       = require('Libraries.transform.vector')

local failures = 0
local function check(label, ok, detail)
    print((ok and "  ok   " or "  FAIL ") .. label .. (detail and ("  -> " .. tostring(detail)) or ""))
    if not ok then failures = failures + 1 end
end

-- boot, mirroring main.lua ---------------------------------------------------
Screen.init()
Prefab.Register(require('Frontend.prefabs.definitions'))
Clip.Register(require('Frontend.animations.definitions'))
Tune.load()
Input.init()
LevelManager.init({ gravityX = 0, gravityY = 9.81 })

LevelManager.load('Frontend.levels.level')
LevelManager.update(1 / 60)

check("level loaded", LevelManager.path == 'Frontend.levels.level', LevelManager.path)

-- find the pieces ------------------------------------------------------------
local door, detector, player
for _, object in ipairs(LevelManager.scene.objects) do
    if object:GetComponent("Door") then door = object end
    if object:GetComponent("LightDetector") then detector = object end
    if object:GetComponent("PlayerController") then player = object end
end

check("door instantiated", door ~= nil)
check("detector instantiated", detector ~= nil)
check("player instantiated", player ~= nil)
if not (door and detector and player) then os.exit(1) end

local doorComponent = door:GetComponent("Door")
local doorSprite    = door:GetComponent("SpriteRenderer")
local doorBody      = door:GetComponent("RigidBody")
local detComponent  = detector:GetComponent("LightDetector")
local detSprite     = detector:GetComponent("SpriteRenderer")

-- the doorway is a trigger, not a wall ---------------------------------------
check("door body is a sensor", doorBody.fixture:isSensor() == true)
check("door body is static", doorBody.bodyType == "static", doorBody.bodyType)

-- clip integrity -------------------------------------------------------------
local openClip = Clip.Resolve("DoorOpen")
check("DoorOpen has all six frames", #openClip.frames == 6, #openClip.frames)
check("DoorOpen holds its last frame", openClip.mode == "once", openClip.mode)
local closeClip = Clip.Resolve("DoorClose")
check("DoorClose runs backwards",
      closeClip.frames[1].col == 5 and closeClip.frames[6].col == 0,
      closeClip.frames[1].col .. " -> " .. closeClip.frames[6].col)

-- detector sprite swap -------------------------------------------------------
local unlitImage = detSprite.image
check("detector starts unlit", detComponent:IsLit() == false)

-- Stand the player in the doorway *before* the puzzle is solved, which is the
-- awkward ordering: the overlap is old news by the time the door opens.
EventBus.publish("physics:collisionBegin", door, player)
check("occupant tracked while shut", doorComponent.occupants[player] == true)

LevelManager.update(1 / 60)
check("shut door does not trigger", LevelManager.isPending() == false)

-- light it up ----------------------------------------------------------------
-- In the exact order LightWorld.resolveDetectors does it: flip lit, call
-- OnHit, then publish. OnHit reads self.lit to decide which sprite to show, so
-- a test that set the flag afterwards would be testing nothing.
detComponent.lit = true
detComponent:OnHit({})
EventBus.publish("light:hit", detComponent, {})

check("detector reports lit", detComponent:IsLit() == true)
check("detector swapped sprite", detSprite.image ~= unlitImage)
check("door began opening", doorComponent.opening == true)
check("door not passable yet", doorComponent:IsOpen() == false)

LevelManager.update(1 / 60)
check("still shut mid-animation", doorComponent:IsOpen() == false)
check("no level queued mid-animation", LevelManager.isPending() == false)

-- run the open clip out (6 frames at 12fps) ----------------------------------
local opened = false
EventBus.subscribe("door:opened", function() opened = true end)
for _ = 1, 40 do
    if LevelManager.isPending() then break end
    LevelManager.update(1 / 60)
end

check("door:opened fired", opened == true)
check("door reports open", doorComponent:IsOpen() == true)
local viewportX = doorSprite.quad:getViewport()
check("door shows its last frame", viewportX == 5 * 64, viewportX)

-- entry ----------------------------------------------------------------------
check("entry latched", doorComponent.entered == true)
check("next level queued", LevelManager.isPending() == true)

LevelManager.update(1 / 60)
check("level_complete live", LevelManager.path == 'Frontend.levels.level_complete',
      LevelManager.path)
check("level_complete is a script level", LevelManager.script ~= nil)
check("level_complete says so", LevelManager.script.config.title == "LEVEL COMPLETED",
      LevelManager.script and LevelManager.script.config.title)
LevelManager.draw()

-- and the switch left nothing behind -----------------------------------------
local segments, detectors, colliders = LightWorld.stats()
check("no light segments leaked", segments == 0, segments)
check("no detectors leaked", detectors == 0, detectors)
check("no dynamic colliders leaked", colliders == 0, colliders)
check("one physics world alive", mock.counts().worlds == 1, mock.counts().worlds)

-- jump goes back -------------------------------------------------------------
Input.state.jumpPressed = true
for _ = 1, 90 do
    LevelManager.update(1 / 60)
    if LevelManager.path == 'Frontend.levels.level' then break end
end
check("jump restarts the level", LevelManager.path == 'Frontend.levels.level',
      LevelManager.path)

LevelManager.unload()
check("teardown leaves no bodies", mock.counts().bodies == 0, mock.counts().bodies)

print(failures == 0 and "\nall door checks passed" or ("\n" .. failures .. " FAILED"))
os.exit(failures == 0 and 0 or 1)
