--[[
  Splash Screen Level for Venus Engine
  
  Use this as a level that loads first, plays splash animation,
  then automatically transitions to the next level.
  
  Usage in level manager:
    local splash_level = require("Libraries.splash_screen.splash_level")
    level_manager:load_level(splash_level, "demo")  -- auto-transitions to "demo" after splash
--]]

local Level = require("Libraries.universal.level")
local SplashLevel = setmetatable({}, Level)
SplashLevel.__index = SplashLevel

function SplashLevel.new()
  local self = setmetatable(Level.new(), SplashLevel)
  
  -- Splash-specific state
  self.image = nil
  self.audio = nil
  self.elapsed = 0
  self.currentFrame = 1
  self.frameTimer = 0
  
  -- Configuration
  self.config = {
    frameDuration = 0.1,
    totalDuration = 3,
    frames = 6,
    spriteLayout = "horizontal",
    nextLevel = nil  -- Set by level manager
  }
  
  -- Get script directory for assets
  local source = debug.getinfo(1).source:sub(2)
  self.scriptDir = source:match("(.*)/") or "."
  self.config.sprite = self.scriptDir .. "/venus_animation-Sheet.png"
  self.config.sound = self.scriptDir .. "/splash.ogg"
  
  return self
end

function SplashLevel:init()
  -- Load sprite
  if self.config.sprite then
    local success, image = pcall(love.graphics.newImage, self.config.sprite)
    if success then
      self.image = image
      self.image:setFilter("nearest", "nearest")
    else
      print("Warning: Could not load splash sprite at " .. self.config.sprite)
    end
  end
  
  -- Load audio
  if self.config.sound then
    local success, audio = pcall(love.audio.newSource, self.config.sound, "static")
    if success then
      self.audio = audio
      self.audio:play()
    else
      print("Warning: Could not load splash sound at " .. self.config.sound)
    end
  end
  
  self.elapsed = 0
  self.currentFrame = 1
  self.frameTimer = 0
end

function SplashLevel:update(dt, level_manager)
  self.elapsed = self.elapsed + dt
  
  -- Update animation frame
  self.frameTimer = self.frameTimer + dt
  if self.frameTimer >= self.config.frameDuration and self.config.frames > 1 then
    self.frameTimer = 0
    self.currentFrame = self.currentFrame + 1
    if self.currentFrame > self.config.frames then
      self.currentFrame = self.config.frames
    end
  end
  
  -- Check if splash duration is complete
  if self.elapsed >= self.config.totalDuration and self.config.nextLevel then
    -- Transition to next level
    level_manager:load_level(self.config.nextLevel)
  end
end

function SplashLevel:draw()
  if not self.image then
    return
  end
  
  local windowWidth = love.graphics.getWidth()
  local windowHeight = love.graphics.getHeight()
  
  -- Calculate frame dimensions
  local frameWidth, frameHeight
  if self.config.spriteLayout == "horizontal" then
    frameWidth = self.image:getWidth() / self.config.frames
    frameHeight = self.image:getHeight()
  else
    frameWidth = self.image:getWidth()
    frameHeight = self.image:getHeight() / self.config.frames
  end
  
  -- Calculate center position
  local x = (windowWidth - frameWidth) / 2
  local y = (windowHeight - frameHeight) / 2
  
  -- Draw background
  love.graphics.setColor(0, 0, 0, 1)
  love.graphics.rectangle("fill", 0, 0, windowWidth, windowHeight)
  
  -- Draw current frame
  love.graphics.setColor(1, 1, 1, 1)
  
  if self.config.spriteLayout == "horizontal" then
    local frameX = (self.currentFrame - 1) * frameWidth
    love.graphics.draw(
      self.image,
      frameX, 0, frameWidth, frameHeight,  -- quad coordinates
      x, y, 0,                               -- draw position and rotation
      1, 1                                  -- scale
    )
  else
    local frameY = (self.currentFrame - 1) * frameHeight
    love.graphics.draw(
      self.image,
      0, frameY, frameWidth, frameHeight,  -- quad coordinates
      x, y, 0,                               -- draw position and rotation
      1, 1                                  -- scale
    )
  end
  
  love.graphics.setColor(1, 1, 1, 1)
end

function SplashLevel:cleanup()
  if self.audio and self.audio:isPlaying() then
    self.audio:stop()
  end
end

-- Convenience function to create splash that transitions to a specific level
function SplashLevel:set_next_level(level_name)
  self.config.nextLevel = level_name
  return self
end

return SplashLevel
