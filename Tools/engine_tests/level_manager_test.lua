package.path = "./?.lua;./?/init.lua;" .. package.path

local mock = require('Tools.engine_tests.love_mock')
mock.install()

local Prefab = require('Libraries.universal.prefab')
local Clip = require('Libraries.animation.clip')
local LevelManager = require('Libraries.universal.level_manager')
local LightWorld = require('Libraries.light_engine.light_world')
local EventBus = require('Libraries.universal.event_bus')
local Screen = require('Libraries.renderer.screen')
local Input = require('Libraries.universal.input')
local Tune = require('Libraries.universal.tune')

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

local persistentHits = 0
EventBus.subscribe("persistent:probe", function() persistentHits = persistentHits + 1 end)

local loaded, unloaded = {}, {}
EventBus.subscribe("level:loaded", function(path) table.insert(loaded, path) end)
EventBus.subscribe("level:unloaded", function(path) table.insert(unloaded, path) end)

LevelManager.init({ gravityX = 0, gravityY = 9.81 })
check("world created on init", mock.counts().worlds == 1, mock.counts().worlds)

-- splash ---------------------------------------------------------------------
LevelManager.load('Libraries.splash_screen.splash_level', { nextLevel = 'Frontend.levels.demo' })
check("load is deferred (nothing live yet)", LevelManager.scene == nil)

LevelManager.update(1 / 60)
check("splash live after one update", LevelManager.script ~= nil)
check("splash got nextLevel", LevelManager.script.config.nextLevel == 'Frontend.levels.demo')
check("splash built its quads", LevelManager.script.quads and #LevelManager.script.quads == 98,
      LevelManager.script.quads and #LevelManager.script.quads)
check("splash spawned no objects", #LevelManager.scene.objects == 0)
LevelManager.draw()

-- run the splash out ---------------------------------------------------------
for _ = 1, 200 do
    LevelManager.update(1 / 60)
    LevelManager.draw()
end

check("splash handed over to demo", LevelManager.path == 'Frontend.levels.demo', LevelManager.path)
check("script level cleared", LevelManager.script == nil)
check("demo objects spawned", #LevelManager.scene.objects > 0, #LevelManager.scene.objects)
check("objectsById populated", LevelManager.get("player") ~= nil)
check("level:loaded fired twice", #loaded == 2, table.concat(loaded, ", "))
check("level:unloaded fired once", #unloaded == 1, table.concat(unloaded, ", "))
check("only one physics world alive", mock.counts().worlds == 1, mock.counts().worlds)

local bodiesInDemo = mock.counts().bodies
local jointsInDemo = mock.counts().joints
check("demo made bodies", bodiesInDemo > 0, bodiesInDemo)
check("demo made a joint", jointsInDemo > 0, jointsInDemo)

-- run the demo ---------------------------------------------------------------
for _ = 1, 60 do
    LevelManager.update(1 / 60)
    LevelManager.draw()
end
check("demo still stable after 60 frames", LevelManager.path == 'Frontend.levels.demo')

-- level-scoped subscription --------------------------------------------------
local scopedHits = 0
LevelManager.subscribe("scoped:probe", function() scopedHits = scopedHits + 1 end)
EventBus.publish("scoped:probe")
EventBus.publish("persistent:probe")
check("scoped listener fires while loaded", scopedHits == 1, scopedHits)

-- reload / teardown ----------------------------------------------------------
LevelManager.reload()
LevelManager.update(1 / 60)
check("reload rebuilt the level", LevelManager.path == 'Frontend.levels.demo')
check("body count stable across reload", mock.counts().bodies == bodiesInDemo,
      mock.counts().bodies .. " vs " .. bodiesInDemo)
check("joint count stable across reload", mock.counts().joints == jointsInDemo,
      mock.counts().joints .. " vs " .. jointsInDemo)

EventBus.publish("scoped:probe")
check("scoped listener died with the level", scopedHits == 1, scopedHits)
EventBus.publish("persistent:probe")
check("persistent listener survived the switch", persistentHits == 2, persistentHits)

local segs, dets, cols = LightWorld.stats()
check("light registrations present while loaded", segs > 0 and cols > 0,
      segs .. "/" .. dets .. "/" .. cols)
local segsBefore, detsBefore, colsBefore = segs, dets, cols

-- full unload ----------------------------------------------------------------
LevelManager.unload()
check("scene gone", LevelManager.scene == nil)
check("path gone", LevelManager.path == nil)
check("all bodies destroyed", mock.counts().bodies == 0, mock.counts().bodies)
check("all joints destroyed", mock.counts().joints == 0, mock.counts().joints)
check("exactly one world remains", mock.counts().worlds == 1, mock.counts().worlds)
check("level module dropped from package.loaded",
      package.loaded['Frontend.levels.demo'] == nil)

local segsAfter, detsAfter, colsAfter = LightWorld.stats()
check("light world emptied", segsAfter == 0 and detsAfter == 0 and colsAfter == 0,
      segsAfter .. "/" .. detsAfter .. "/" .. colsAfter)
-- Safe to pump the light passes with nothing registered.
LightWorld.syncColliders()
LightWorld.resolveDetectors()

-- update/draw with nothing loaded must not explode
LevelManager.update(1 / 60)
LevelManager.draw()
check("update/draw are safe with no level", true)

-- reload after unload
LevelManager.load('Frontend.levels.demo')
LevelManager.update(1 / 60)
check("can load again after a full unload", #LevelManager.scene.objects > 0)

LevelManager.update(1 / 60)
local segsAgain, detsAgain, colsAgain = LightWorld.stats()
check("light registrations do not accumulate across switches",
      segsAgain == segsBefore and colsAgain == colsBefore,
      segsAgain .. "/" .. detsAgain .. "/" .. colsAgain
      .. " vs " .. segsBefore .. "/" .. detsBefore .. "/" .. colsBefore)

print("")
print(failures == 0 and "ALL CHECKS PASSED" or (failures .. " CHECK(S) FAILED"))
os.exit(failures == 0 and 0 or 1)
