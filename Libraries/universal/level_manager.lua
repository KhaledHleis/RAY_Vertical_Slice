-- level_manager.lua
--
-- Owns the one thing a level cannot own for itself: the moment it stops
-- existing. Level.load builds a scene from a definition table and stops
-- there; the manager wraps that with a lifecycle -- load, run, tear down,
-- load the next -- and with the teardown order that keeps a switch from
-- leaking bodies, light segments, listeners and Lua modules.
--
-- Usage from main.lua:
--
--   local LevelManager = require('Libraries.universal.level_manager')
--
--   function love.load()
--       LevelManager.init({ gravityX = 0, gravityY = 9.81 })
--       LevelManager.load('Frontend.levels.demo')
--   end
--
--   function love.update(dt) LevelManager.update(dt) end
--   function love.draw()     LevelManager.draw()     end
--
-- and from anywhere inside a running level:
--
--   LevelManager.load('Frontend.levels.next_one')
--
--
-- TWO KINDS OF LEVEL
--
-- A *data* level is what Frontend/levels/*.lua already are: a module
-- returning an array of prefab entries, handed straight to Level.load.
--
-- A *script* level is a module that drives itself -- the splash screen is
-- one. It returns either a class (a table with .new) or a ready instance,
-- and may implement any of:
--
--   init(manager)        once, after the scene exists
--   update(dt, manager)  every frame, between Scene:Update and LateUpdate
--   draw(manager)        every frame, after Scene:Draw (so it paints on top)
--   cleanup()            once, first thing during teardown
--
-- A script level still gets an empty Scene (LevelManager.scene), so it can
-- spawn prefabs like any other level if it wants to. The splash does not.
--
-- The two are told apart by what the module returns; see levelKind below.
--
--
-- WHY LOADING IS DEFERRED
--
-- LevelManager.load queues the request and returns. The switch happens at
-- the top of the next update, before anything else runs. That is the only
-- safe point: a level that calls load from inside its own update -- which is
-- the normal case, a door was reached, the splash timer ran out -- would
-- otherwise be destroying the very scene Scene:Update is iterating.
--
--
-- WHAT TEARDOWN ACTUALLY FREES
--
-- In order, and the order matters:
--
--   1. the script level's cleanup hook, while its resources are still valid;
--   2. every object in the scene, which runs each component's OnDestroy --
--      that is what destroys Box2D bodies and joints, unregisters light
--      segments, colliders and detectors, and drops EventBus subscriptions
--      made through Component:Subscribe;
--   3. level-scoped EventBus listeners registered via LevelManager.subscribe
--      (see below);
--   4. LightWorld.clear, belt and braces -- a segment left behind holds a
--      reference to its owner Object and would keep the whole level alive;
--   5. World.reset, a fresh Box2D world, which also drops contacts and any
--      joint nothing claimed;
--   6. package.loaded[path] = nil, so the level table itself is collectable
--      and the next load re-reads the file from disk (free hot reload while
--      editing with Tools/level_editor);
--   7. two collectgarbage passes, because a body destroyed in step 2 may
--      only release its userdata on the second.
--
-- EventBus.clear() is deliberately NOT called. Component subscriptions clean
-- themselves up in step 2, and anything else subscribed directly to the bus
-- is by definition not part of a level -- an audio manager, a save system --
-- and should survive the switch. Non-component code that *does* want a
-- listener to die with the level should register it through
-- LevelManager.subscribe. If you really want the nuclear option, pass
-- clearEventBus = true to init/configure.

local Scene      = require('Libraries.universal.scene')
local Level      = require('Libraries.universal.level')
local World      = require('Libraries.physics.world')
local LightWorld = require('Libraries.light_engine.light_world')
local EventBus   = require('Libraries.universal.event_bus')

local LevelManager = {}

-- The live level. Read these; do not assign them.
LevelManager.scene       = nil   -- Scene, or nil when nothing is loaded
LevelManager.script      = nil   -- script-level instance, or nil
LevelManager.path        = nil   -- module path of the loaded level
LevelManager.objectsById = {}    -- id -> Object, from the level definition

local config = {
    gravityX      = 0,
    gravityY      = 9.81,
    -- Drop the level module from package.loaded on unload. Off means levels
    -- stay cached: marginally faster to revisit, but edits on disk are not
    -- picked up and the definition table is never freed.
    unloadModules = true,
    -- Wipe every EventBus listener, including ones the game set up outside
    -- of any level. See the note above -- off is almost always right.
    clearEventBus = false,
    -- Run collectgarbage after teardown. Off if you would rather pay for the
    -- collection incrementally than take the hiccup at the switch.
    collect       = true,
}

local pending       = nil    -- { path = string, args = table|nil }
local subscriptions = {}     -- level-scoped EventBus handles
local switching     = false  -- re-entrancy guard around a switch

--------------------------------------------------------------------- setup

function LevelManager.configure(options)
    for key, value in pairs(options or {}) do
        config[key] = value
    end
    return LevelManager
end

-- Call once from love.load, before the first load. Creates the physics world
-- so components that grab World.get() in OnAttach have one to grab.
function LevelManager.init(options)
    LevelManager.configure(options)
    World.init(config.gravityX, config.gravityY)
    return LevelManager
end

------------------------------------------------------------------ requests

-- Queues a level. Applied at the top of the next update, never here -- see
-- the note above. Calling it twice in one frame keeps the last request.
function LevelManager.load(path, args)
    assert(type(path) == "string", "LevelManager.load: path must be a module path string")
    pending = { path = path, args = args }
end

-- Reloads the current level from scratch. With unloadModules on (the
-- default) this re-reads the file, so it doubles as a hot-reload key.
-- A no-op when nothing is loaded, rather than an assert -- it is bound to a
-- debug key, and a debug key should never be the thing that crashes a build.
function LevelManager.reload()
    if not LevelManager.path then return false end
    pending = { path = LevelManager.path, args = LevelManager.args }
    return true
end

function LevelManager.isPending()
    return pending ~= nil
end

------------------------------------------------------------------- scoping

-- An EventBus subscription that dies with the level. For non-component code
-- only -- components should use Component:Subscribe, which is already tied
-- to the object's lifetime.
function LevelManager.subscribe(eventName, callback)
    local handle = EventBus.subscribe(eventName, callback)
    table.insert(subscriptions, handle)
    return handle
end

function LevelManager.unsubscribe(handle)
    if not handle then return end
    EventBus.unsubscribe(handle)
    for i = #subscriptions, 1, -1 do
        if subscriptions[i] == handle then
            table.remove(subscriptions, i)
            break
        end
    end
end

-------------------------------------------------------------------- lookup

-- The object a level entry gave an `id`. nil if there is no such id.
function LevelManager.get(id)
    return LevelManager.objectsById[id]
end

-- Spawns into the live scene. Convenience so gameplay code does not have to
-- reach through LevelManager.scene for the common case.
function LevelManager.spawn(object)
    assert(LevelManager.scene, "LevelManager.spawn: no level is loaded")
    return LevelManager.scene:Spawn(object)
end

------------------------------------------------------------------ teardown

-- Destroys everything the current level owns and leaves the manager empty.
-- Safe to call when nothing is loaded.
function LevelManager.unload()
    if not (LevelManager.scene or LevelManager.script or LevelManager.path) then
        return
    end

    local path = LevelManager.path
    EventBus.publish("level:unloading", path)

    -- 1. The script level goes first, while its own resources (audio sources,
    --    canvases) are still whole.
    if LevelManager.script and LevelManager.script.cleanup then
        LevelManager.script:cleanup()
    end
    LevelManager.script = nil

    -- 2. Objects. This is where the real freeing happens -- every component's
    --    OnDestroy runs, and every component in this project that holds
    --    engine-side state releases it there.
    if LevelManager.scene then
        LevelManager.scene:Clear()
    end
    LevelManager.scene = nil
    LevelManager.objectsById = {}

    -- 3. Level-scoped listeners.
    for _, handle in ipairs(subscriptions) do
        EventBus.unsubscribe(handle)
    end
    subscriptions = {}
    if config.clearEventBus then EventBus.clear() end

    -- 4. Anything that failed to unregister itself in step 2 -- a hand-built
    --    collider, a component someone forgot to give an OnDestroy. Cheap,
    --    and it is the difference between a leak and a clean slate.
    LightWorld.clear()

    -- 5. A brand new Box2D world. Bodies died with their components above;
    --    this clears contacts, joints and the broadphase in one go.
    World.reset(config.gravityX, config.gravityY)

    -- 6. Forget the module so the table is collectable and the next load
    --    re-reads the file.
    if config.unloadModules and path then
        package.loaded[path] = nil
    end

    LevelManager.path = nil
    LevelManager.args = nil

    -- 7. Twice: the first pass runs finalizers, the second collects what
    --    they released.
    if config.collect then
        collectgarbage("collect")
        collectgarbage("collect")
    end

    EventBus.publish("level:unloaded", path)
end

------------------------------------------------------------------- loading

-- A module returning a table with .new is a script-level class; one with an
-- update or draw of its own is a script-level instance; anything else is a
-- plain array of level entries for Level.load.
local function levelKind(module)
    if type(module) ~= "table" then
        return nil
    end
    if type(module.new) == "function" then return "script-class" end
    if type(module.update) == "function" or type(module.draw) == "function" then
        return "script-instance"
    end
    return "data"
end

-- Script levels keep their tunables in `config` (the splash does); anything
-- without one takes the args on the instance itself.
local function applyArgs(instance, args)
    if not args then return end
    local target = instance.config or instance
    for key, value in pairs(args) do
        target[key] = value
    end
end

local function applyLoad(request)
    LevelManager.unload()

    local path = request.path
    local module = require(path)
    local kind = levelKind(module)
    assert(kind, "LevelManager: '" .. path .. "' did not return a table")

    -- Every level gets a scene, script levels included -- an empty one costs
    -- nothing and means a splash or a menu can spawn prefabs later without
    -- changing kind.
    LevelManager.scene = Scene.new()
    LevelManager.path = path
    LevelManager.args = request.args

    if kind == "data" then
        LevelManager.objectsById = Level.load(path, LevelManager.scene) or {}
    else
        local instance = module
        if kind == "script-class" then instance = module.new() end
        applyArgs(instance, request.args)
        instance.scene = LevelManager.scene
        instance.manager = LevelManager
        LevelManager.script = instance
        if instance.init then instance:init(LevelManager) end
    end

    EventBus.publish("level:loaded", path, LevelManager.objectsById)
end

-- Applies a queued load immediately. Called at the top of update; exposed so
-- boot code or a test can have the level live before the first frame.
function LevelManager.flush()
    if not pending or switching then return false end

    local request = pending
    pending = nil

    switching = true
    local ok, err = pcall(applyLoad, request)
    switching = false

    if not ok then error(err, 0) end
    return true
end

-------------------------------------------------------------------- frame

-- The whole frame for the live level, in the order the engine depends on:
--
--   World.update   Box2D steps; bodies move
--   Scene:Update   transforms are written (physics readback, Spinner,
--                  PlayerController)
--   script update  the level's own logic, on settled transforms
--   syncColliders  light geometry rebuilt from those transforms, in one pass
--   Scene:LateUpdate  LightSource casts against that geometry; anything
--                  reading a world transform here is order-independent
--   resolveDetectors  this frame's hits turned into detector state
--
-- Input.update and Tune.update stay in main.lua: they are not level state
-- and must keep running across a switch.
function LevelManager.update(dt)
    LevelManager.flush()

    local scene = LevelManager.scene
    if not scene then return end

    World.update(dt)
    scene:Update(dt)

    local script = LevelManager.script
    if script and script.update then
        script:update(dt, LevelManager)
        -- The script may have queued the next level. Stop here rather than
        -- run light and detector passes over a scene that is one line from
        -- being destroyed.
        if pending then return end
    end

    LightWorld.syncColliders()
    scene:LateUpdate(dt)
    LightWorld.resolveDetectors()
end

-- Draw the scene first, then the script level on top -- a splash or a pause
-- overlay wants to cover what it is standing in front of. Call this inside
-- Screen.beginDraw/endDraw so everything shares the pixel canvas.
function LevelManager.draw()
    if LevelManager.scene then LevelManager.scene:Draw() end

    local script = LevelManager.script
    if script and script.draw then script:draw(LevelManager) end
end

return LevelManager
