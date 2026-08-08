-- input.lua
--
-- Single polled snapshot of player intent, refreshed once per frame from
-- main.lua before the scene updates. Components read Input.state rather than
-- taking an `input` argument, because Component:Update's signature is
-- (object, dt) and every component in the project reads its dependencies
-- through requires or GetComponent.
--
-- jumpPressed is edge-triggered: true only on the frame the button went down.
-- The jump buffer in PlayerController depends on that edge, so Input.update
-- must be called exactly once per frame.

local Tune = require('Libraries.universal.tune')

local Input = {}

Input.state = {
    moveX       = 0,
    up          = false,
    down        = false,
    jumpDown    = false,
    jumpPressed = false,
}

-- Rebindable. Any key in the list counts.
Input.keys = {
    left  = { "left",  "a" },
    right = { "right", "d" },
    up    = { "up",    "w" },
    down  = { "down",  "s" },
    jump  = { "space", "z", "c", "k" },
}

-- Gamepad equivalents, for the handheld build.
Input.pad = {
    left  = "dpleft",
    right = "dpright",
    up    = "dpup",
    down  = "dpdown",
    jump  = { "a", "b" },
}

Input.deadzone = 0.35

local joystick = nil
local wasJumpDown = false

local function anyKey(list)
    for _, key in ipairs(list) do
        if love.keyboard.isDown(key) then return true end
    end
    return false
end

local function padDown(button)
    if not (joystick and joystick:isGamepad()) then return false end
    if type(button) == "table" then
        for _, b in ipairs(button) do
            if joystick:isGamepadDown(b) then return true end
        end
        return false
    end
    return joystick:isGamepadDown(button)
end

local function padAxis()
    if not (joystick and joystick:isGamepad()) then return 0 end
    local x = joystick:getGamepadAxis("leftx") or 0
    if math.abs(x) < Input.deadzone then return 0 end
    return x > 0 and 1 or -1
end

function Input.init()
    local sticks = love.joystick and love.joystick.getJoysticks() or {}
    for _, stick in ipairs(sticks) do
        if stick:isGamepad() then joystick = stick break end
    end
end

-- Called from love.joystickadded/removed so hot-plugging works.
function Input.setJoystick(stick)
    joystick = stick
end

function Input.update(dt)
    local s = Input.state

    -- While the tuning panel owns the arrow keys, the player should not also
    -- be running around underneath it.
    if Tune.isOpen() then
        s.moveX, s.up, s.down = 0, false, false
        s.jumpDown, s.jumpPressed = false, false
        wasJumpDown = false
        return
    end

    local left  = anyKey(Input.keys.left)  or padDown(Input.pad.left)
    local right = anyKey(Input.keys.right) or padDown(Input.pad.right)
    local axis  = padAxis()

    local moveX = (right and 1 or 0) - (left and 1 or 0)
    if moveX == 0 then moveX = axis end

    s.moveX = moveX
    s.up    = anyKey(Input.keys.up)   or padDown(Input.pad.up)
    s.down  = anyKey(Input.keys.down) or padDown(Input.pad.down)

    local jump = anyKey(Input.keys.jump) or padDown(Input.pad.jump)
    s.jumpPressed = jump and not wasJumpDown
    s.jumpDown    = jump
    wasJumpDown   = jump
end

return Input
