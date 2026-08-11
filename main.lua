local World = require('Libraries.physics.world')
local Scene = require('Libraries.universal.scene')
local Screen = require('Libraries.renderer.screen')
local Prefab = require('Libraries.universal.prefab')
local Level = require('Libraries.universal.level')
local PrefabDefinitions = require('Frontend.prefabs.definitions')
local Clip = require('Libraries.animation.clip')
local ClipDefinitions = require('Frontend.animations.definitions')
local LightWorld = require('Libraries.light_engine.light_world')
local Input = require('Libraries.universal.input')
local Tune = require('Libraries.universal.tune')
local splash_screen = require("Libraries.splash_screen.splash_screen")

local scene
local tuneFont

function love.load()
    splash_screen:init()

    love.graphics.setDefaultFilter("nearest", "nearest")
    love.graphics.setLineStyle("rough")

    Screen.init()
    World.init(0, 9.81)
    Prefab.Register(PrefabDefinitions)
    -- Before any prefab is instantiated: AnimationPlayer resolves its clips
    -- by name in OnAttach, so they have to be registered by then.
    Clip.Register(ClipDefinitions)

    Tune.load()
    Input.init()
    tuneFont = love.graphics.newFont(8)

    scene = Scene.new()
    Level.load('Frontend.levels.demo', scene)
end

function love.update(dt)
    splash_screen:update(dt)
    -- Before the scene: PlayerController reads Input.state during its Update,
    -- and jumpPressed is a single-frame edge that has to be fresh.
    Input.update(dt)
    Tune.update(dt, love.keyboard.isDown("left"), love.keyboard.isDown("right"))

    -- Three phases, in this order, and the order is the whole point:
    --   Update        transforms move (physics readback, Spinner, controller)
    --   syncColliders light geometry rebuilt from settled transforms
    --   LateUpdate    LightSource casts against that geometry
    -- Anything reading a world transform in LateUpdate is order-independent.
    World.update(dt)
    scene:Update(dt)
    LightWorld.syncColliders()
    scene:LateUpdate(dt)
    LightWorld.resolveDetectors()
end

function love.draw()
    if not splash_screen:isDone() then
        splash_screen:draw()
    end
    Screen.beginDraw()
    scene:Draw()
    -- Inside the canvas so the panel scales with the game and stays crisp.
    Tune.draw(tuneFont, Screen.WIDTH, Screen.HEIGHT)
    Screen.endDraw()

    love.graphics.print("FPS: " .. love.timer.getFPS(), 10, 10)
end

function love.keypressed(key, scancode, isrepeat)
    if key == "escape" then print("quit game"); love.event.quit() end
    -- tab toggles the panel, f5 dumps, f9 resets; arrows drive it while open.
    if Tune.keypressed(key) then
        if key == "tab" and not Tune.isOpen() then Tune.save() end
        return
    end
end

function love.joystickadded(joystick)
    if joystick:isGamepad() then Input.setJoystick(joystick) end
end

function love.joystickremoved(joystick)
    Input.init()
end

function love.gamepadpressed(joystick, button)

end

function love.resize(w, h)
    Screen.updateScale()
end
