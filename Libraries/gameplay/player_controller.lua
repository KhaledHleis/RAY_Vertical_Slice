-- player_controller.lua
--
-- Port of the standalone tile-grid player controller onto this project's
-- Box2D world. The feel model is unchanged -- coyote time, jump buffering,
-- variable jump height, heavier falls, a floatier apex, snappier turnarounds,
-- push speed caps, squash and stretch -- and every number still comes from
-- Tune, so the live panel keeps working.
--
-- What changed, and why:
--
--   * The original owned its own AABB sweep (moveX/moveY with per-step
--     callbacks) against a tile grid. There is no tile grid here, so Box2D
--     resolves the collisions. We keep authority over velocity: gravity scale
--     is zeroed on the body and we integrate vy ourselves, so fall_mult,
--     apex_mult and max_fall stay meaningful in pixels/second exactly as they
--     were. love.physics is configured with setMeter(PIXELS_PER_METER), so
--     the tuning numbers transfer 1:1 with no unit conversion.
--
--   * The moveX/moveY callbacks used to zero vx on a wall and vy on a floor or
--     ceiling. Box2D does that for us during its step, so we read the body's
--     velocity back at the top of each update and treat it as the truth about
--     what happened, rather than tracking it blind.
--
--   * Pushing used to mean probing for a box actor and calling box:shove().
--     Crates are dynamic RigidBodies here, so Box2D moves them on contact by
--     itself. The probe survives as a raycast whose only job is deciding
--     whether to apply the push_speed cap and push_accel -- which is the part
--     that was ever about feel.
--
--   * Sound calls became EventBus publishes ("player:jumped", "player:landed",
--     "player:step", "player:died", "player:state"). Nothing here needs to
--     know an audio module exists, and the same events can drive screen shake
--     or a light flicker.

local Component = require('Libraries.universal.component')
local EventBus  = require('Libraries.universal.event_bus')
local World     = require('Libraries.physics.world')
local Screen    = require('Libraries.renderer.screen')
local Input     = require('Libraries.universal.input')
local Tune      = require('Libraries.universal.tune')

local PlayerController = setmetatable({}, { __index = Component })
PlayerController.__index = PlayerController

function PlayerController.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, PlayerController)

    -- By default the component reads the live global Tune table, so edits in
    -- the panel apply instantly. A prefab passing tune = { run_speed = 90 }
    -- gets a per-instance override that still falls through to Tune.values
    -- for everything it does not mention.
    if args.tune then
        self.tune = setmetatable(args.tune, { __index = Tune.values })
    else
        self.tune = Tune.values
    end

    -- How far below the feet we look for ground. Larger is more forgiving on
    -- rough geometry, but starts letting you jump slightly before you land.
    self.groundProbe = args.groundProbe or 2
    self.killY       = args.killY

    self.vx, self.vy  = 0, 0
    self.prevVy       = 0
    self.grounded     = false
    self.wasGrounded  = false
    self.groundKind   = nil
    self.coyote       = 0      -- time left to still count as grounded
    self.buffer       = 0      -- time left on a queued jump press
    self.jumping      = false  -- in the rising phase of a jump
    self.facing       = 1
    self.pushing      = false
    self.dropTimer    = 0
    self.dropThrough  = false
    self.landImpact   = 0
    self.dead         = false
    self.sx, self.sy  = 1, 1   -- squash/stretch, consumed by PlayerRenderer
    self.state        = "idle"

    return self
end

function PlayerController:__tostring()
    return "PlayerController"
end

function PlayerController:OnAttach(object)
    self.object = object
    self.rigidBody = object:GetComponent("RigidBody")
    assert(self.rigidBody, "PlayerController needs a RigidBody on the same object -- "
        .. "declare RigidBody before PlayerController in the prefab so it exists by now.")

    local body = self.rigidBody.body

    body:setFixedRotation(true)
    -- We integrate gravity by hand; letting Box2D also apply it would double
    -- it up and make fall_mult / apex_mult meaningless.
    body:setGravityScale(0)
    -- Cheap here, and it stops fast falls tunnelling through thin floors.
    body:setBullet(true)
    -- Friction fights the velocity we set every frame and glues the player to
    -- walls mid-jump. All horizontal damping is the accel model's job.
    self.rigidBody.fixture:setFriction(0)

    self.spawnX, self.spawnY = body:getPosition()
    self.killY = self.killY or (Screen.HEIGHT + 64)

    -- Anything can kill the player without holding a reference to it:
    --   EventBus.publish("player:kill")            -- kills every player
    --   EventBus.publish("player:kill", playerObj) -- kills one
    self:Subscribe("player:kill", function(target)
        if target == nil or target == object then self:respawn() end
    end)
end

function PlayerController:respawn()
    local body = self.rigidBody.body
    body:setPosition(self.spawnX, self.spawnY)
    body:setLinearVelocity(0, 0)

    self.vx, self.vy, self.prevVy = 0, 0, 0
    self.jumping    = false
    self.dropTimer  = 0
    self.coyote     = 0
    self.buffer     = 0
    self.sx, self.sy = 1, 1

    -- Keep the transform in step so the frame we respawn on does not draw the
    -- player at the old position.
    self.object.transform.position.x = self.spawnX
    self.object.transform.position.y = self.spawnY

    EventBus.publish("player:died", self.object)
end

---------------------------------------------------------------------- probes

-- Returns "solid", "oneway", or nil. Three rays (both feet corners and the
-- centre) so a foot hanging over a ledge still counts, matching how the
-- original's AABB overlap test behaved.
function PlayerController:probeGround()
    local rb = self.rigidBody
    local body = rb.body
    local x, y = body:getPosition()
    local hw, hh = rb.width / 2, rb.height / 2
    local feet = y + hh
    local inset = math.min(1, hw * 0.5)
    local kind = nil

    local offsets = { -hw + inset, 0, hw - inset }
    for _, ox in ipairs(offsets) do
        World.get():rayCast(
            x + ox, feet - 1,
            x + ox, feet + self.groundProbe,
            function(fixture, hx, hy, nx, ny, fraction)
                if fixture == rb.fixture or fixture:isSensor() then return -1 end

                local other = fixture:getUserData()
                local otherRB = other and other.GetComponent and other:GetComponent("RigidBody")
                local isOneWay = otherRB and otherRB.oneWay

                -- Mid-drop, a one-way is not ground -- otherwise we would
                -- re-ground on the platform we are falling through.
                if isOneWay and self.dropThrough then return -1 end

                kind = isOneWay and "oneway" or "solid"
                return fraction
            end)
        if kind == "solid" then break end
    end

    return kind
end

-- Is something directly ahead? Returns "dynamic" (a crate we can shove),
-- "static" (a wall), or nil.
function PlayerController:probeAhead(dir)
    local rb = self.rigidBody
    local body = rb.body
    local x, y = body:getPosition()
    local hw, hh = rb.width / 2, rb.height / 2
    local sign = dir > 0 and 1 or -1
    local reach = hw + self.groundProbe + 1
    local found = nil

    for _, oy in ipairs({ -hh * 0.5, 0, hh * 0.5 }) do
        World.get():rayCast(
            x, y + oy,
            x + sign * reach, y + oy,
            function(fixture, hx, hy, nx, ny, fraction)
                if fixture == rb.fixture or fixture:isSensor() then return -1 end
                found = (fixture:getBody():getType() == "dynamic") and "dynamic" or "static"
                return fraction
            end)
        if found == "dynamic" then break end
    end

    return found
end

---------------------------------------------------------------------- update

function PlayerController:Update(object, dt)
    if dt <= 0 then return end

    local T = self.tune
    local rb = self.rigidBody
    local body = rb.body
    local input = Input.state

    -- Box2D is the authority on what actually happened during the last step:
    -- a wall zeroed vx, a floor or ceiling zeroed vy. Read it back before
    -- planning this frame. prevVy keeps the speed we *asked* for last frame,
    -- which is the one worth measuring a landing against -- by now the real
    -- one has already been zeroed by the collision.
    local bvx, bvy = body:getLinearVelocity()
    self.prevVy = self.vy
    self.vx, self.vy = bvx, bvy

    ---------------------------------------------------------------- timers
    -- Drop-through stays active briefly so we clear the platform's thickness.
    self.dropTimer = math.max(0, self.dropTimer - dt)
    self.dropThrough = self.dropTimer > 0

    self.groundKind = self:probeGround()
    -- Moving upward past a ledge should not count as standing on it.
    self.grounded = (self.groundKind ~= nil) and (self.vy >= -1)

    if self.grounded then
        self.coyote = T.coyote_time
        if not self.wasGrounded then
            self.landImpact = math.min(math.abs(self.prevVy) / T.max_fall, 1)
            self.sy = 1 - T.squash * self.landImpact
            self.sx = 1 + T.squash * self.landImpact
            EventBus.publish("player:landed", object, self.landImpact)
        end
    else
        self.coyote = math.max(0, self.coyote - dt)
    end
    self.wasGrounded = self.grounded

    if input.jumpPressed then self.buffer = T.jump_buffer
    else self.buffer = math.max(0, self.buffer - dt) end

    ---------------------------------------------------------------- horizontal
    local dir = input.moveX
    if dir ~= 0 then self.facing = dir > 0 and 1 or -1 end

    local ahead = (dir ~= 0) and self:probeAhead(dir) or nil
    local canPush = (ahead == "dynamic") and (self.grounded or T.push_in_air >= 1)
    self.pushing = canPush and true or false

    local target = dir * (self.pushing and T.push_speed or T.run_speed)
    local accel
    if dir == 0 then
        accel = self.grounded and T.ground_decel or T.air_decel
    else
        accel = self.grounded and T.ground_accel or T.air_accel
        if self.pushing then accel = T.push_accel end
        -- snappier turnaround when reversing
        if self.vx ~= 0 and (self.vx > 0) ~= (dir > 0) then
            accel = accel * T.turn_mult
        end
    end

    if self.vx < target then self.vx = math.min(self.vx + accel * dt, target)
    elseif self.vx > target then self.vx = math.max(self.vx - accel * dt, target) end

    ---------------------------------------------------------------- jump
    if self.buffer > 0 and self.coyote > 0 then
        -- Holding down on a one-way platform drops through instead of jumping.
        if input.down and self.groundKind == "oneway" then
            self.dropTimer = T.drop_time
            self.dropThrough = true
            self.buffer = 0        -- consume: this press is a drop, not a jump
            self.vy = math.max(self.vy, T.jump_speed * 0.25)  -- nudge downward
        else
            self.vy       = -T.jump_speed
            self.jumping  = true
            self.buffer   = 0
            self.coyote   = 0
            self.grounded = false
            self.sy = 1 + T.squash * 0.8
            self.sx = 1 - T.squash * 0.8
            EventBus.publish("player:jumped", object)
        end
    end

    -- A ceiling killed the rise: Box2D already zeroed vy, so stop treating
    -- this as a jump. (The original's moveY callback did this directly.)
    if self.jumping and self.vy > -1 then self.jumping = false end

    -- releasing early cuts the rise
    if self.jumping and not input.jumpDown and self.vy < 0 then
        self.vy = self.vy * T.jump_cut
        self.jumping = false
    end
    if self.vy >= 0 then self.jumping = false end

    ---------------------------------------------------------------- gravity
    local g = T.gravity
    if self.vy > 0 then g = g * T.fall_mult end
    if math.abs(self.vy) < T.apex_window then g = g * T.apex_mult end
    self.vy = math.min(self.vy + g * dt, T.max_fall)

    ---------------------------------------------------------------- commit
    body:setLinearVelocity(self.vx, self.vy)

    -- fell out of the level
    local _, y = body:getPosition()
    if y > self.killY then self:respawn() end

    ---------------------------------------------------------------- squash
    local r = T.squash_recover * dt
    self.sx = self.sx + (1 - self.sx) * math.min(r, 1)
    self.sy = self.sy + (1 - self.sy) * math.min(r, 1)

    self:updateState(object, input)
end

-- Pick a state from current physics. Order = priority. PlayerRenderer maps
-- these to animations; nothing here knows about art.
function PlayerController:updateState(object, input)
    local prev = self.state
    local st

    if self.dead then
        st = "death"
    elseif not self.grounded then
        if self.vy < -10 then st = "jump"
        elseif self.vy > 10 then st = "fall"
        else st = "jump" end
    elseif self.pushing then
        st = "push"
    elseif math.abs(self.vx) > 5 then
        -- turning: input opposes current velocity
        if input.moveX ~= 0 and (input.moveX > 0) ~= (self.vx > 0) then
            st = "turn"
        else
            st = "run"
        end
    else
        st = "idle"
    end

    self.state = st
    if st ~= prev then
        EventBus.publish("player:state", object, st, prev)
    end
end

return PlayerController
