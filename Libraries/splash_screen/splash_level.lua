-- splash_level.lua
--
-- The Venus Engine splash, as a *script level* (see level_manager.lua): a
-- level that drives itself instead of listing prefabs, and hands over to the
-- next one when it is done.
--
--   LevelManager.load('Libraries.splash_screen.splash_level', {
--       nextLevel = 'Frontend.levels.demo',
--   })
--
-- Anything in `config` can be overridden through those load args.
--
-- It draws inside the Screen canvas rather than to the window, so it scales
-- with the same integer factor as the game and stays pixel-crisp on the
-- handheld. That is why the centring below uses Screen.WIDTH/HEIGHT and not
-- love.graphics.getDimensions(), which still reports the window while a
-- canvas is bound.

local Screen = require('Libraries.renderer.screen')
local Input  = require('Libraries.universal.input')

local SplashLevel = {}
SplashLevel.__index = SplashLevel

-- Assets live next to this file, so the path is derived rather than hardcoded
-- relative to the project root.
local SCRIPT_DIR = (debug.getinfo(1).source:sub(2):match("(.*)[/\\]")) or "."

function SplashLevel.new()
    local self = setmetatable({}, SplashLevel)

    self.config = {
        sprite    = SCRIPT_DIR .. "/venus_animation_rising-Sheet.png",
        logo      = SCRIPT_DIR .. "/Name.png",
        sound     = SCRIPT_DIR .. "/splash.ogg",

        -- The sheet is one long horizontal strip of square frames, so the
        -- frame size is the image height and the count falls out of the
        -- width. Set frameWidth explicitly for a sheet that is not square.
        frameWidth = nil,
        fps        = 60,

        -- Total time on screen, fades included.
        duration  = 1.5,
        fadeIn    = 0.35,
        fadeOut   = 0.45,

        -- Pixels between the planet and the wordmark.
        logoGap   = 10,

        background = { 0, 0, 0 },

        -- Jump skips ahead. Handy while iterating; turn it off for a build.
        skippable = true,

        nextLevel = nil,
    }

    self.image     = nil
    self.logoImage = nil
    self.audio     = nil
    self.quads     = nil
    self.elapsed   = 0
    self.finished  = false

    return self
end

function SplashLevel:init(manager)
    local config = self.config

    local ok, image = pcall(love.graphics.newImage, config.sprite)
    if ok then
        self.image = image
        self.image:setFilter("nearest", "nearest")

        local imageWidth, imageHeight = self.image:getDimensions()
        imageWidth,imageHeight = imageWidth*2,imageHeight*2
        local frameWidth  = config.frameWidth or imageHeight
        local frameHeight = imageHeight
        local count = math.max(1, math.floor(imageWidth / frameWidth))

        -- Built once. Rebuilding a quad per frame is cheap but pointless when
        -- the strip never changes.
        self.quads = {}
        for i = 0, count - 1 do
            self.quads[i + 1] = love.graphics.newQuad(
                i * frameWidth, 0, frameWidth, frameHeight, imageWidth, imageHeight)
        end
        self.frameWidth  = frameWidth
        self.frameHeight = frameHeight
    else
        print("SplashLevel: could not load sprite at " .. tostring(config.sprite))
    end

    if config.logo then
        local logoOk, logo = pcall(love.graphics.newImage, config.logo)
        if logoOk then
            self.logoImage = logo
            self.logoImage:setFilter("nearest", "nearest")
        end
    end

    if config.sound then
        local soundOk, audio = pcall(love.audio.newSource, config.sound, "static")
        if soundOk then
            self.audio = audio
            self.audio:play()
        else
            print("SplashLevel: could not load sound at " .. tostring(config.sound))
        end
    end

    self.elapsed = 0
    self.finished = false
end

-- One-shot: the request is queued, so update keeps being called until the
-- manager applies it at the top of the next frame. Without the guard we would
-- queue the same load every one of those frames.
function SplashLevel:finish(manager)
    if self.finished then return end
    self.finished = true

    if self.config.nextLevel then
        manager.load(self.config.nextLevel)
    end
end

function SplashLevel:update(dt, manager)
    self.elapsed = self.elapsed + dt

    if self.config.skippable and Input.state.jumpPressed then
        self:finish(manager)
        return
    end

    if self.elapsed >= self.config.duration then
        self:finish(manager)
    end
end

-- Ramps up over fadeIn, holds, ramps down over fadeOut.
function SplashLevel:alpha()
    local config = self.config
    local fadeIn, fadeOut = config.fadeIn, config.fadeOut
    local remaining = config.duration - self.elapsed

    if fadeIn > 0 and self.elapsed < fadeIn then
        return self.elapsed / fadeIn
    end
    if fadeOut > 0 and remaining < fadeOut then
        return math.max(0, remaining / fadeOut)
    end
    return 1
end

function SplashLevel:draw()
    local width, height = Screen.WIDTH, Screen.HEIGHT

    local background = self.config.background
    love.graphics.setColor(background[1], background[2], background[3], 1)
    love.graphics.rectangle("fill", 0, 0, width, height)

    local alpha = self:alpha()

    if self.image and self.quads then
        -- Loops: the strip is a full rotation, and it is nicer to keep
        -- spinning than to freeze on the last cell if the timing is retuned.
        local index = math.floor(self.elapsed * self.config.fps) % #self.quads + 1

        -- Planet and wordmark are centred as one block, so adding or removing
        -- the logo does not shift the planet off centre.
        local logoWidth, logoHeight = 0, 0
        if self.logoImage then
            logoWidth, logoHeight = self.logoImage:getDimensions()
        end

        local blockHeight = self.frameHeight
        if self.logoImage then
            blockHeight = blockHeight + self.config.logoGap + logoHeight
        end

        local top = math.floor((height - blockHeight) / 2)

        love.graphics.setColor(1, 1, 1, alpha)
        love.graphics.draw(self.image, self.quads[index],
            math.floor((width - self.frameWidth) / 2), top)

        if self.logoImage then
            love.graphics.draw(self.logoImage,
                math.floor((width - logoWidth) / 2),
                top + self.frameHeight + self.config.logoGap)
        end
    end

    love.graphics.setColor(1, 1, 1, 1)
end

function SplashLevel:cleanup()
    if self.audio then
        if self.audio:isPlaying() then self.audio:stop() end
        self.audio = nil
    end
    self.image     = nil
    self.logoImage = nil
    self.quads     = nil
end

return SplashLevel
