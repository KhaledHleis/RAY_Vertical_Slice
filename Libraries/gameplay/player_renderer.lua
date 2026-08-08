-- player_renderer.lua
--
-- Draws the player from PlayerController's state, squash and facing.
--
-- This deliberately does not go through SpriteRenderer: SpriteRenderer centres
-- the image on the transform, and squash has to be anchored at the *feet* or
-- a landing looks like the character shrinking in mid-air instead of
-- compressing against the floor. Same reason the original controller drew
-- itself.
--
-- With no image it falls back to the original's plain rectangle, so the
-- controller is playable and tunable before any art exists.
--
-- Animations are declared per state:
--   animations = {
--       idle = { row = 0, frames = 4,  fps = 6 },
--       run  = { row = 1, frames = 8,  fps = 12, steps = { 0, 4 } },
--       jump = { row = 2, frames = 1,  fps = 1, loop = false },
--   }
-- `steps` lists the frame indices that fire "player:step" -- the original's
-- "play a footstep on specific frames" trick, without the manual latch.

local Component = require('Libraries.universal.component')
local EventBus  = require('Libraries.universal.event_bus')

local PlayerRenderer = setmetatable({}, { __index = Component })
PlayerRenderer.__index = PlayerRenderer

function PlayerRenderer.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, PlayerRenderer)

    self.image = args.image or (args.path and love.graphics.newImage(args.path))
    self.frameWidth  = args.frameWidth
    self.frameHeight = args.frameHeight
    self.animations  = args.animations

    -- nudge sprite alignment vs hitbox
    self.artOX = args.artOX or 0
    self.artOY = args.artOY or 0

    self.color = args.color or { 0.95, 0.78, 0.25 }

    self.frame = 0
    self.timer = 0
    self.currentState = nil
    self.quad = nil

    if self.image and self.frameWidth and self.frameHeight then
        self.quad = love.graphics.newQuad(0, 0, self.frameWidth, self.frameHeight,
                                          self.image:getDimensions())
    end

    return self
end

function PlayerRenderer:__tostring()
    return "PlayerRenderer"
end

function PlayerRenderer:OnAttach(object)
    self.controller = object:GetComponent("PlayerController")
    self.rigidBody  = object:GetComponent("RigidBody")
end

function PlayerRenderer:Update(object, dt)
    if not (self.animations and self.quad) then return end

    local state = (self.controller and self.controller.state) or "idle"
    local anim = self.animations[state] or self.animations.idle
    if not anim then return end

    if state ~= self.currentState then
        self.currentState = state
        self.frame, self.timer = 0, 0
    end

    local step = 1 / (anim.fps or 8)
    self.timer = self.timer + dt
    while self.timer >= step do
        self.timer = self.timer - step
        local next = self.frame + 1
        if next >= anim.frames then
            next = (anim.loop == false) and (anim.frames - 1) or 0
        end
        self.frame = next

        if anim.steps then
            for _, f in ipairs(anim.steps) do
                if f == self.frame then EventBus.publish("player:step", object) end
            end
        end
    end

    self.quad:setViewport(self.frame * self.frameWidth, (anim.row or 0) * self.frameHeight,
                          self.frameWidth, self.frameHeight,
                          self.image:getDimensions())
end

function PlayerRenderer:Draw(object)
    local pc = self.controller
    local sx = pc and pc.sx or 1
    local sy = pc and pc.sy or 1
    local facing = pc and pc.facing or 1

    local pos = object.transform.position
    local halfH = self.rigidBody and (self.rigidBody.height / 2) or 0

    if self.image and self.quad then
        -- Round to whole pixels: the game renders into a 320x240 canvas, and
        -- a half-pixel offset here shows up as a shimmering sprite.
        local drawX = math.floor(pos.x + self.artOX + 0.5)
        local drawY = math.floor(pos.y + halfH + self.artOY + 0.5)
        love.graphics.setColor(1, 1, 1, 1)
        love.graphics.draw(self.image, self.quad, drawX, drawY, 0,
                           facing * sx, sy,
                           self.frameWidth / 2, self.frameHeight)
    else
        -- fallback rectangle (art not loaded)
        local rb = self.rigidBody
        local w = (rb and rb.width or 6) * sx
        local h = (rb and rb.height or 12) * sy
        local by = pos.y + halfH
        love.graphics.setColor(self.color)
        love.graphics.rectangle("fill", pos.x - w / 2, by - h, w, h)
    end

    love.graphics.setColor(1, 1, 1, 1)
end

return PlayerRenderer
