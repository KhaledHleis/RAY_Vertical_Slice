local World = require('Libraries.physics.world')
local Scene = require('Libraries.universal.scene')
local Screen = require('Libraries.renderer.screen')
local Prefab = require('Libraries.universal.prefab')
local Level = require('Libraries.universal.level')
local PrefabDefinitions = require('Frontend.prefabs.definitions')
local LightWorld = require('Libraries.light_engine.light_world')

local scene

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    love.graphics.setLineStyle("rough")

    Screen.init()
    World.init(0, 9.81)
    Prefab.Register(PrefabDefinitions)
    Prefab.Register(require('Frontend.prefabs.light_test_prefabs'))
    scene = Scene.new()
    Level.load('Frontend.levels.demo', scene)
end

function love.update(dt)
    World.update(dt)
    scene:Update(dt)
    LightWorld.resolveDetectors()
end

function love.draw()
    Screen.beginDraw()
    scene:Draw()
    Screen.endDraw()

    love.graphics.print("FPS: " .. love.timer.getFPS(), 10, 10)
end

function love.keypressed(key, scancode, isrepeat)
    if key == "escape" then print("quit game"); love.event.quit() end
end

function love.gamepadpressed(joystick, button)

end

function love.resize(w, h)
    Screen.updateScale()
end
