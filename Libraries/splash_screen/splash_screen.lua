--[[
  Splash Screen Module for LÖVE2D (Self-Contained)
  Automatically loads assets from its own directory.
  
  MINIMAL Usage in main.lua:
    require("libraries.splash_screen.splash_screen")
    
    function love.load()
      splash_screen:init()
    end
    
    function love.update(dt)
      splash_screen:update(dt)
    end
    
    function love.draw()
      splash_screen:draw()
      if splash_screen:isDone() then
        -- Draw game here
      end
    end
--]]

local SplashScreen = {}
SplashScreen.__index = SplashScreen

function SplashScreen.new()
  local self = setmetatable({}, SplashScreen)
  
  -- Detect script directory (works with require "libraries.splash_screen.splash_screen")
  local source = debug.getinfo(1).source:sub(2)  -- Remove @ prefix
  self.scriptDir = source:match("(.*)/") or "."
  
  -- Default configuration - loads from this script's directory
  self.config = {
    sprite = self.scriptDir .. "/venus_animation-Sheet.png",
    sound = self.scriptDir .. "/splash.ogg",
    frameDuration = 0.1,
    totalDuration = 3,
    frames = 6,                    -- venus_animation-Sheet.png has 6 frames
    spriteLayout = "horizontal"
  }
  
  -- State variables
  self.image = nil
  self.audio = nil
  self.elapsed = 0
  self.currentFrame = 1
  self.frameTimer = 0
  self.isActive = false
  self.hasPlayedSound = false
  
  return self
end

---Initialize splash screen (one-call setup with defaults)
function SplashScreen:init()
  -- Load sprite from local directory
  if self.config.sprite then
    local success, image = pcall(love.graphics.newImage, self.config.sprite)
    if success then
      self.image = image
      self.image:setFilter("nearest", "nearest") -- Pixel-perfect rendering
    else
      print("Warning: Could not load splash sprite at " .. self.config.sprite)
    end
  end
  
  -- Load sound from local directory
  if self.config.sound then
    local success, audio = pcall(love.audio.newSource, self.config.sound, "static")
    if success then
      self.audio = audio
    else
      print("Warning: Could not load splash sound at " .. self.config.sound)
    end
  end
  
  -- Start splash
  self.elapsed = 0
  self.currentFrame = 1
  self.frameTimer = 0
  self.isActive = true
  self.hasPlayedSound = false
end

---Load splash screen with custom configuration (optional, overrides defaults)
function SplashScreen:load(config)
  -- Merge provided config with defaults
  if config then
    for key, value in pairs(config) do
      self.config[key] = value
    end
  end
  
  self:init()
end

---Update splash screen (call in love.update)
function SplashScreen:update(dt)
  if not self.isActive then
    return
  end
  
  -- Play sound once at start
  if not self.hasPlayedSound and self.audio then
    self.audio:play()
    self.hasPlayedSound = true
  end
  
  -- Update elapsed time
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
  if self.elapsed >= self.config.totalDuration then
    self:stop()
  end
end

---Draw splash screen (call in love.draw)
function SplashScreen:draw()
  if not self.isActive or not self.image then
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

---Check if splash screen is finished
function SplashScreen:isDone()
  return not self.isActive
end

---Stop splash screen immediately
function SplashScreen:stop()
  self.isActive = false
  if self.audio and self.audio:isPlaying() then
    self.audio:stop()
  end
end

---Reset splash screen to initial state
function SplashScreen:reset()
  self.elapsed = 0
  self.currentFrame = 1
  self.frameTimer = 0
  self.isActive = true
  self.hasPlayedSound = false
end

---Get progress (0 to 1)
function SplashScreen:getProgress()
  return math.min(self.elapsed / self.config.totalDuration, 1)
end

-- Return singleton instance
return SplashScreen.new()