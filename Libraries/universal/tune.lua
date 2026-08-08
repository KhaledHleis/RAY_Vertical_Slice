-- Every number that affects player feel lives here.
-- Edit live in-game (Tab), values persist to the LOVE save dir.
-- When you like a set, press F5 to print them so you can paste back as defaults.
--
-- Ported unchanged in spirit from the standalone controller. The box_gravity /
-- box_max_fall / box_slide entries are gone: crates are Box2D RigidBodies in
-- this project, so their fall and slide come from the physics world and the
-- fixture's friction, not from here. push_speed / push_accel / push_in_air stay,
-- because those describe how the *player* behaves while pushing.

local Tune = {}

-- key, label, default, min, max, step
local DEFS = {
    { group = "run" },
    { "run_speed",       "top speed",        110,   10,  400,  5 },
    { "ground_accel",    "ground accel",     900,   50, 4000, 50 },
    { "ground_decel",    "ground decel",    1200,   50, 4000, 50 },
    { "air_accel",       "air accel",        600,   50, 4000, 50 },
    { "air_decel",       "air decel",        400,    0, 4000, 50 },
    { "turn_mult",       "turnaround mult",  2.0,  1.0,  6.0, 0.1 },

    { group = "jump" },
    { "jump_speed",      "jump velocity",    215,   50,  600,  5 },
    { "gravity",         "gravity",          800,  100, 4000, 25 },
    { "fall_mult",       "fall gravity x",   1.5,  1.0,  4.0, 0.05 },
    { "apex_mult",       "apex gravity x",   0.5,  0.1,  1.0, 0.05 },
    { "apex_window",     "apex window",       40,    0,  200,  5 },
    { "jump_cut",        "cut release x",    0.4,  0.0,  1.0, 0.05 },
    { "max_fall",        "terminal vel",     300,   50, 1000, 10 },
    { "coyote_time",     "coyote (s)",      0.10, 0.00, 0.40, 0.01 },
    { "jump_buffer",     "buffer (s)",      0.12, 0.00, 0.40, 0.01 },
    { "drop_time",       "drop window (s)", 0.15, 0.02, 0.50, 0.01 },

    { group = "boxes" },
    { "push_speed",      "push speed",        45,    5,  300,  5 },
    { "push_accel",      "push accel",       500,   50, 3000, 50 },
    { "push_in_air",     "push midair (0/1)",  0,    0,    1,  1 },

    { group = "feel" },
    { "squash",          "squash amount",   0.30, 0.00, 1.00, 0.05 },
    { "squash_recover",  "squash recover",    12,    1,   40,  1 },
    { "land_shake",      "land shake",       1.5,  0.0,  8.0, 0.5 },
}

Tune.defs   = DEFS
Tune.values = {}
Tune.order  = {}

for _, d in ipairs(DEFS) do
    if not d.group then
        Tune.values[d[1]] = d[3]
        Tune.order[#Tune.order + 1] = d
    end
end

local SAVE = "tune_values.lua"

function Tune.load()
    if not love.filesystem.getInfo(SAVE) then return end
    local ok, chunk = pcall(love.filesystem.load, SAVE)
    if not ok or not chunk then return end
    local ok2, data = pcall(chunk)
    if ok2 and type(data) == "table" then
        for k, v in pairs(data) do
            if Tune.values[k] ~= nil then Tune.values[k] = v end
        end
    end
end

function Tune.save()
    local out = { "return {" }
    for _, d in ipairs(Tune.order) do
        out[#out + 1] = ("  [%q] = %s,"):format(d[1], tostring(Tune.values[d[1]]))
    end
    out[#out + 1] = "}"
    love.filesystem.write(SAVE, table.concat(out, "\n"))
end

function Tune.reset()
    for _, d in ipairs(Tune.order) do Tune.values[d[1]] = d[3] end
end

-- Dump current values to the console in DEFS format, ready to paste back
function Tune.dump()
    print("---- tuned values ----")
    for _, d in ipairs(Tune.order) do
        print(("%-16s %s"):format(d[1], tostring(Tune.values[d[1]])))
    end
    print("----------------------")
end

------------------------------------------------------------------ panel

local panel = { open = false, index = 1, hold = 0, dir = 0 }
Tune.panel = panel

function Tune.toggle() panel.open = not panel.open end
function Tune.isOpen() return panel.open end

function Tune.moveCursor(d)
    panel.index = panel.index + d
    if panel.index < 1 then panel.index = #Tune.order end
    if panel.index > #Tune.order then panel.index = 1 end
end

local function applyStep(d, mult)
    local def = Tune.order[panel.index]
    local key, step = def[1], def[6]
    local v = Tune.values[key] + d * step * mult
    v = math.max(def[4], math.min(def[5], v))
    -- kill float drift from repeated fractional steps
    Tune.values[key] = math.floor(v * 1000 + 0.5) / 1000
end

function Tune.adjust(d) applyStep(d, 1) end

function Tune.update(dt, leftDown, rightDown)
    if not panel.open then return end
    local d = (rightDown and 1 or 0) - (leftDown and 1 or 0)
    if d ~= 0 then
        if panel.dir ~= d then
            panel.dir, panel.hold = d, 0
            applyStep(d, 1)
        else
            panel.hold = panel.hold + dt
            if panel.hold > 0.35 then
                applyStep(d, 4 * dt * 12)
            end
        end
    else
        panel.dir, panel.hold = 0, 0
    end
end

-- Keyboard handling for the panel, so main.lua doesn't have to know the
-- layout. Returns true when the key was consumed by the panel.
function Tune.keypressed(key)
    if key == "tab" then Tune.toggle() return true end
    if key == "f5" then Tune.dump() return true end
    if key == "f9" then Tune.reset() Tune.save() return true end
    if not panel.open then return false end
    if key == "up"   then Tune.moveCursor(-1) return true end
    if key == "down" then Tune.moveCursor(1)  return true end
    if key == "left" or key == "right" then return true end
    return false
end

-- Derived numbers are more useful than the raw ones when tuning a jump.
function Tune.derived()
    local v = Tune.values
    local apex_t = v.jump_speed / v.gravity
    local height = (v.jump_speed * v.jump_speed) / (2 * v.gravity)
    return apex_t, height
end

-- Flat display list so scrolling can account for group headers too.
local display
local function buildDisplay()
    display = {}
    local pi = 0
    for _, d in ipairs(Tune.defs) do
        if d.group then
            display[#display + 1] = { group = d.group }
        else
            pi = pi + 1
            display[#display + 1] = { def = d, index = pi }
        end
    end
end

function Tune.draw(font, w, h)
    if not panel.open then return end
    if not display then buildDisplay() end

    local pad, lineH = 5, 8
    local pw = 148
    local footer = 34
    local visible = math.floor((h - pad - footer) / lineH)

    -- find the display row holding the selected param, then scroll to show it
    local selRow = 1
    for i, e in ipairs(display) do
        if e.index == panel.index then selRow = i break end
    end
    local scroll = 0
    if selRow > visible - 1 then scroll = selRow - (visible - 1) end
    if scroll > #display - visible then scroll = math.max(0, #display - visible) end

    local prevFont = love.graphics.getFont()
    love.graphics.setFont(font)
    love.graphics.setColor(0, 0, 0, 0.85)
    love.graphics.rectangle("fill", 0, 0, pw, h)
    love.graphics.setColor(1, 1, 1, 0.15)
    love.graphics.line(pw, 0, pw, h)

    local y = pad
    for i = scroll + 1, math.min(#display, scroll + visible) do
        local e = display[i]
        if e.group then
            love.graphics.setColor(0.40, 0.70, 1.0)
            love.graphics.print(e.group, pad, y)
        else
            local d = e.def
            local sel = (e.index == panel.index)
            if sel then
                love.graphics.setColor(0.95, 0.75, 0.2, 0.28)
                love.graphics.rectangle("fill", 0, y - 1, pw, lineH)
            end
            love.graphics.setColor(sel and 1 or 0.70, sel and 0.90 or 0.70, sel and 0.40 or 0.70)
            love.graphics.print(d[2], pad + 2, y)
            local val = Tune.values[d[1]]
            local s = (val % 1 == 0) and tostring(math.floor(val)) or tostring(val)
            love.graphics.printf(s, 0, y, pw - pad, "right")
        end
        y = y + lineH
    end

    -- scroll indicators
    love.graphics.setColor(0.5, 0.5, 0.5)
    if scroll > 0 then love.graphics.print("^", pw - 10, pad) end
    if scroll + visible < #display then
        love.graphics.print("v", pw - 10, pad + (visible - 1) * lineH)
    end

    -- footer: derived jump numbers, the ones you actually tune against
    local apex_t, height = Tune.derived()
    local fy = h - footer + 2
    love.graphics.setColor(1, 1, 1, 0.12)
    love.graphics.line(0, fy - 3, pw, fy - 3)
    love.graphics.setColor(0.40, 0.70, 1.0)
    love.graphics.print(("apex %.2fs  rise %.0fpx"):format(apex_t, height), pad, fy)
    love.graphics.setColor(0.70, 0.70, 0.70)
    love.graphics.print(("= %.1f tiles high"):format(height / 8), pad, fy + lineH)
    love.graphics.setColor(0.5, 0.5, 0.5)
    love.graphics.print("f5 dump   f9 reset", pad, fy + lineH * 2)

    love.graphics.setColor(1, 1, 1, 1)
    if prevFont then love.graphics.setFont(prevFont) end
end

return Tune
