local Screen = require('Libraries.renderer.screen')
local Prefab = require('Libraries.universal.prefab')
local PrefabDefinitions = require('Frontend.prefabs.definitions')
local Clip = require('Libraries.animation.clip')
local ClipDefinitions = require('Frontend.animations.definitions')
local Input = require('Libraries.universal.input')
local Tune = require('Libraries.universal.tune')
local LevelManager = require('Libraries.universal.level_manager')

-- The boot chain. The splash is a script level that hands over to whatever
-- nextLevel it is given, so changing the first playable level is one string.
local SPLASH_LEVEL = 'Libraries.splash_screen.splash_level'
local FIRST_LEVEL  = 'Frontend.levels.demo'

local tuneFont

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    love.graphics.setLineStyle("rough")

    Screen.init()

    Prefab.Register(PrefabDefinitions)
    -- Before any prefab is instantiated: AnimationPlayer resolves its clips
    -- by name in OnAttach, so they have to be registered by then.
    Clip.Register(ClipDefinitions)

    Tune.load()
    Input.init()
    tuneFont = love.graphics.newFont(8)

    -- Creates the Box2D world; components grab it in OnAttach, so it has to
    -- exist before the first level loads.
    LevelManager.init({ gravityX = 0, gravityY = 9.81 })
    LevelManager.load(SPLASH_LEVEL, { nextLevel = FIRST_LEVEL })
end

function love.update(dt)
    -- Input and Tune are not level state: they keep running across a switch,
    -- so they stay here rather than inside the manager.
    --
    -- Input first, because PlayerController reads Input.state during its
    -- Update and jumpPressed is a single-frame edge that has to be fresh.
    Input.update(dt)
    Tune.update(dt, love.keyboard.isDown("left"), love.keyboard.isDown("right"))

    -- Applies any queued level switch, then runs the frame: physics, Update,
    -- light sync, LateUpdate, detectors. The ordering rationale lives in
    -- level_manager.lua next to the code that depends on it.
    LevelManager.update(dt)
end

function love.draw()
    Screen.beginDraw()
    LevelManager.draw()
    -- Inside the canvas so the panel scales with the game and stays crisp.
    Tune.draw(tuneFont, Screen.WIDTH, Screen.HEIGHT)
    Screen.endDraw()

    love.graphics.print("FPS: " .. love.timer.getFPS(), 10, 10)
end

function love.keypressed(key, scancode, isrepeat)
    if key == "escape" then print("quit game"); love.event.quit() end

    -- Reloads the level from disk: with LevelManager's unloadModules on, the
    -- level file is re-read, so edits from Tools/level_editor land without a
    -- restart.
    if key == "f6" then LevelManager.reload() return end

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
