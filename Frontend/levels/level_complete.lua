-- level_complete.lua
--
-- Placeholder end card, as a *script level* (see level_manager.lua): it lists
-- no prefabs, draws itself, and hands over when the player presses jump.
--
--   LevelManager.load('Frontend.levels.level_complete')
--
-- Reached from the door prefab's `nextLevel`. Everything in `config` can be
-- overridden through the load args, so a real ending later can pass its own
-- text and destination without this file changing:
--
--   LevelManager.load('Frontend.levels.level_complete', {
--       title = "CHAPTER ONE COMPLETE",
--       nextLevel = 'Frontend.levels.level_two',
--   })
--
-- It draws inside the Screen canvas rather than to the window, for the same
-- reason the splash does -- so it scales with the same integer factor as the
-- game and stays crisp on the handheld. That is why the centring below uses
-- Screen.WIDTH/HEIGHT and not love.graphics.getDimensions(), which still
-- reports the window while a canvas is bound.

local Screen = require('Libraries.renderer.screen')
local Input  = require('Libraries.universal.input')

local LevelComplete = {}
LevelComplete.__index = LevelComplete

function LevelComplete.new()
    local self = setmetatable({}, LevelComplete)

    self.config = {
        title    = "LEVEL COMPLETED",
        subtitle = "press jump to play again",

        titleSize    = 32,
        subtitleSize = 12,

        background = { 0.04, 0.05, 0.08 },
        titleColor = { 1.0, 0.87, 0.55 },
        subtitleColor = { 0.65, 0.68, 0.78 },

        fadeIn  = 0.4,
        -- Gap between the two lines.
        lineGap = 24,

        -- Where jump goes. Restarting is the placeholder behaviour; point it
        -- at the next level when there is one.
        nextLevel = 'Frontend.levels.level',

        -- Ignore the button briefly. The player may well still be holding
        -- jump from the platforming that got them here, and an end card that
        -- vanishes before it is read is worse than no end card.
        inputDelay = 0.5,
    }

    self.elapsed   = 0
    self.finished  = false
    self.titleFont = nil
    self.subFont   = nil

    return self
end

function LevelComplete:init(manager)
    self.elapsed  = 0
    self.finished = false

    self.titleFont = love.graphics.newFont(self.config.titleSize)
    self.subFont   = love.graphics.newFont(self.config.subtitleSize)
end

-- One-shot: the request is only queued, so update keeps being called until
-- the manager applies it at the top of the next frame. Without the guard we
-- would queue the same load every one of those frames.
function LevelComplete:finish(manager)
    if self.finished then return end
    if not self.config.nextLevel then return end

    self.finished = true
    manager.load(self.config.nextLevel)
end

function LevelComplete:update(dt, manager)
    self.elapsed = self.elapsed + dt

    if self.elapsed < self.config.inputDelay then return end
    if Input.state.jumpPressed then self:finish(manager) end
end

function LevelComplete:alpha()
    local fadeIn = self.config.fadeIn
    if fadeIn <= 0 then return 1 end
    return math.min(1, self.elapsed / fadeIn)
end

local function printCentered(text, font, y, r, g, b, a)
    love.graphics.setFont(font)
    love.graphics.setColor(r, g, b, a)
    love.graphics.print(text, math.floor((Screen.WIDTH - font:getWidth(text)) / 2), math.floor(y))
end

function LevelComplete:draw()
    local config = self.config
    local width, height = Screen.WIDTH, Screen.HEIGHT

    -- setFont is global state and this draws last, so anything after it in
    -- love.draw -- the Tune panel, the FPS counter -- would inherit a 32pt
    -- font. Put it back on the way out.
    local previousFont = love.graphics.getFont()

    local background = config.background
    love.graphics.setColor(background[1], background[2], background[3], 1)
    love.graphics.rectangle("fill", 0, 0, width, height)

    local alpha = self:alpha()

    -- Both lines are centred as one block, so changing the subtitle -- or
    -- dropping it -- does not shift the title off centre.
    local titleHeight = self.titleFont:getHeight()
    local subHeight   = config.subtitle and self.subFont:getHeight() or 0
    local blockHeight = titleHeight + (config.subtitle and (config.lineGap + subHeight) or 0)
    local top = (height - blockHeight) / 2

    local titleColor = config.titleColor
    printCentered(config.title, self.titleFont, top,
        titleColor[1], titleColor[2], titleColor[3], alpha)

    if config.subtitle then
        -- Slow pulse, and only once the card has finished fading in, so the
        -- hint reads as an invitation rather than competing with the title.
        local pulse = 0.55 + 0.45 * math.sin(self.elapsed * 3)
        local subColor = config.subtitleColor
        printCentered(config.subtitle, self.subFont, top + titleHeight + config.lineGap,
            subColor[1], subColor[2], subColor[3], alpha * pulse)
    end

    if previousFont then love.graphics.setFont(previousFont) end
    love.graphics.setColor(1, 1, 1, 1)
end

function LevelComplete:cleanup()
    -- Fonts hold GPU-side glyph atlases, so they are worth releasing rather
    -- than waiting for a collection -- the same reason the splash releases
    -- its audio source here.
    if self.titleFont and self.titleFont.release then self.titleFont:release() end
    if self.subFont and self.subFont.release then self.subFont:release() end
    self.titleFont = nil
    self.subFont   = nil
end

return LevelComplete
