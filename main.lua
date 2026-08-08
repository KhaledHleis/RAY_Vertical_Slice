local World = require('Libraries.physics.world')
local Scene = require('Libraries.universal.scene')
local Screen = require('Libraries.renderer.screen')
local Prefab = require('Libraries.universal.prefab')
local Level = require('Libraries.universal.level')
local PrefabDefinitions = require('Frontend.prefabs.definitions')
local LightWorld = require('Libraries.light_engine.light_world')
local Input = require('Libraries.universal.input')
local Tune = require('Libraries.universal.tune')

local scene
local tuneFont

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    love.graphics.setLineStyle("rough")

    Screen.init()
    World.init(0, 9.81)
    Prefab.Register(PrefabDefinitions)

    Tune.load()
    Input.init()
    tuneFont = love.graphics.newFont(8)

    scene = Scene.new()
    Level.load('Frontend.levels.demo', scene)
end

function love.update(dt)
    -- Before the scene: PlayerController reads Input.state during its Update,
    -- and jumpPressed is a single-frame edge that has to be fresh.
    Input.update(dt)
    Tune.update(dt, love.keyboard.isDown("left"), love.keyboard.isDown("right"))

    World.update(dt)
    scene:Update(dt)
    LightWorld.resolveDetectors()
end

function love.draw()
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
