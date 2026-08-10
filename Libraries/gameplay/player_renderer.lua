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
-- What changed with AnimationPlayer:
--
-- The frame timer, the fps stepping and the `steps` footstep latch used to
-- live here. They are gone -- an AnimationPlayer on the same object owns the
-- playhead now and pushes frames in through SetSheet/SetFrame, exactly as it
-- does for a SpriteRenderer. What stays here is the part that is genuinely
-- about the player: the foot-anchored draw, and the mapping from a controller
-- state to a clip name:
--
--   { type = "PlayerRenderer", args = {
--         animations = {
--             idle = "PlayerIdle",
--             run  = "PlayerRun",
--             jump = "PlayerJump",
--             fall = "PlayerFall",
--         },
--   }},
--   { type = "AnimationPlayer", args = { target = "PlayerRenderer" } },
--
-- Footsteps are now declared on the clip itself (`events = { { at = 1, name =
-- "player:step" } }`) rather than as a `steps` list here, so the same clip
-- fires them however it is played.
--
-- That `animations` table is a one-state-one-clip map: no conditions, no
-- transitions, no blending. It is the seed of the Animator -- when the state
-- machine lands, this table lifts out of here unchanged and becomes its
-- state -> clip column, and PlayerRenderer goes back to being purely a draw.

local Component = require('Libraries.universal.component')

local PlayerRenderer = setmetatable({}, { __index = Component })
PlayerRenderer.__index = PlayerRenderer

function PlayerRenderer.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, PlayerRenderer)

    -- state name -> clip name
    self.animations = args.animations

    -- nudge sprite alignment vs hitbox
    self.artOX = args.artOX or 0
    self.artOY = args.artOY or 0

    self.color = args.color or { 0.95, 0.78, 0.25 }

    -- Written by AnimationPlayer through SetSheet/SetFrame.
    self.image       = args.image or (args.path and love.graphics.newImage(args.path))
    self.frameWidth  = args.frameWidth
    self.frameHeight = args.frameHeight
    self.quad        = nil

    if self.image and self.frameWidth and self.frameHeight then
        self.quad = love.graphics.newQuad(0, 0, self.frameWidth, self.frameHeight,
                                          self.image:getDimensions())
    end

    self.currentState = nil

    return self
end

function PlayerRenderer:__tostring()
    return "PlayerRenderer"
end

function PlayerRenderer:OnAttach(object)
    self.controller = object:GetComponent("PlayerController")
    self.rigidBody  = object:GetComponent("RigidBody")
    self.animator   = object:GetComponent("AnimationPlayer")

    if not self.animations then return end

    -- PlayerController publishes this the frame a state actually changes, so
    -- reacting to it means no lag waiting for our own Update -- components
    -- update in an unspecified order, and the controller may well run after
    -- us. Update still polls as a safety net; a matching state makes it a
    -- no-op.
    self:Subscribe("player:state", function(target, state)
        if target == object then self:_playState(object, state) end
    end)
end

-- Same contract as SpriteRenderer:SetSheet -- see the note there about why a
-- new image needs a new quad.
function PlayerRenderer:SetSheet(image, frameWidth, frameHeight)
    if not image then return end
    if self.image == image
        and self.frameWidth == frameWidth
        and self.frameHeight == frameHeight
        and self.quad then
        return
    end

    self.image = image
    self.frameWidth = frameWidth
    self.frameHeight = frameHeight
    self.quad = love.graphics.newQuad(0, 0, frameWidth, frameHeight, image:getDimensions())
end

function PlayerRenderer:SetFrame(col, row)
    if not self.quad then return end
    self.quad:setViewport(col * self.frameWidth, row * self.frameHeight,
                          self.frameWidth, self.frameHeight)
end

function PlayerRenderer:_playState(object, state)
    if not self.animations then return end

    -- AnimationPlayer may attach after us, depending on prefab order.
    self.animator = self.animator or object:GetComponent("AnimationPlayer")
    if not self.animator then return end

    local clip = self.animations[state] or self.animations.idle
    if not clip then return end

    self.currentState = state
    self.animator:Play(clip)
end

function PlayerRenderer:Update(object, dt)
    if not self.animations then return end

    local state = (self.controller and self.controller.state) or "idle"
    if state ~= self.currentState then
        self:_playState(object, state)
    end
end

function PlayerRenderer:Draw(object)
    local pc = self.controller
    local sx = pc and pc.sx or 1
    local sy = pc and pc.sy or 1
    local facing = pc and pc.facing or 1

    -- The player always has a RigidBody, so it is always a root and world is
    -- local. Read it through World() anyway to pick up scale, and so nothing
    -- here needs revisiting if the player is ever spawned scaled.
    local px, py, _, scale = object.transform:World()
    local halfH = self.rigidBody and (self.rigidBody.height / 2) or 0

    if self.image and self.quad then
        -- Round to whole pixels: the game renders into a 320x240 canvas, and
        -- a half-pixel offset here shows up as a shimmering sprite.
        -- artOX/artOY scale with the object or the art drifts off the hitbox.
        local drawX = math.floor(px + self.artOX * scale + 0.5)
        local drawY = math.floor(py + halfH + self.artOY * scale + 0.5)
        love.graphics.setColor(1, 1, 1, 1)
        love.graphics.draw(self.image, self.quad, drawX, drawY, 0,
                           facing * sx * scale, sy * scale,
                           self.frameWidth / 2, self.frameHeight)
    else
        -- fallback rectangle (art not loaded)
        local rb = self.rigidBody
        -- rb.width/height are already world sizes; RigidBody baked scale in.
        local w = (rb and rb.width or 6 * scale) * sx
        local h = (rb and rb.height or 12 * scale) * sy
        local by = py + halfH
        love.graphics.setColor(self.color)
        love.graphics.rectangle("fill", px - w / 2, by - h, w, h)
    end

    love.graphics.setColor(1, 1, 1, 1)
end

return PlayerRenderer
