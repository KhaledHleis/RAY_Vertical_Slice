local Vector = require('Libraries.transform.vector')
local EventBus = require('Libraries.universal.event_bus')

local World = {}

-- How many game pixels make up one physics metre.
-- This is handed straight to love.physics.setMeter(), so love does the
-- pixel <-> metre conversion for us. Every value we pass into love.physics
-- (positions, shape sizes, joint anchors, gravity) is therefore in PIXELS,
-- and everything love hands back is in PIXELS too.
--
-- Do NOT divide by this yourself before calling love.physics.* -- that scales
-- the world twice and shrinks it far below the 0.1m-10m range Box2D is tuned
-- for, which makes Box2D's fixed collision skin (b2_polygonRadius, 1cm) show
-- up as a huge visible gap under every resting body.
World.PIXELS_PER_METER = 64

local instance = nil

-- Box2D contact callbacks. Fixtures get their userData set to the owning
-- Object in RigidBody:OnAttach, so we can publish the Objects on each side
-- of the contact rather than raw fixtures. Published on the EventBus
-- instead of dispatched directly so gameplay code (a spike that damages on
-- contact, a pressure plate, a landing sound) can react without RigidBody
-- itself knowing anything about gameplay.
local function beginContact(fixtureA, fixtureB, contact)
    EventBus.publish("physics:collisionBegin", fixtureA:getUserData(), fixtureB:getUserData(), contact)
end

local function endContact(fixtureA, fixtureB, contact)
    EventBus.publish("physics:collisionEnd", fixtureA:getUserData(), fixtureB:getUserData(), contact)
end

local function rigidBodyOf(object)
    if not (object and object.GetComponent) then return nil end
    return object:GetComponent("RigidBody")
end

-- One-way platforms. A RigidBody declared with oneWay = true only stops
-- bodies that arrive from above, and lets anything holding a drop-through
-- (PlayerController.dropThrough) fall straight past.
--
-- This has to live in preSolve rather than in the gameplay component: by the
-- time a contact reaches beginContact, Box2D has already decided to solve it.
-- preSolve runs before the solver each step, so disabling the contact there
-- is what actually lets the body through.
local function preSolve(fixtureA, fixtureB, contact)
    local objectA, objectB = fixtureA:getUserData(), fixtureB:getUserData()
    local platformRB = rigidBodyOf(objectA)
    local moverObject, moverRB = objectB, rigidBodyOf(objectB)

    if not (platformRB and platformRB.oneWay) then
        platformRB = rigidBodyOf(objectB)
        moverObject, moverRB = objectA, rigidBodyOf(objectA)
        if not (platformRB and platformRB.oneWay) then return end
    end
    if not moverRB then return end
    -- Two one-ways touching each other: leave the contact alone.
    if moverRB.oneWay then return end

    local _, platformY = platformRB.body:getPosition()
    local _, moverY = moverRB.body:getPosition()
    local _, moverVY = moverRB.body:getLinearVelocity()

    local top = platformY - platformRB.height / 2
    local bottom = moverY + moverRB.height / 2

    -- Slop scales with fall speed: a fast lander is already a few pixels past
    -- the lip on the frame the contact appears, and should still be caught.
    local slop = math.max(4, math.abs(moverVY) / 50)

    local controller = moverObject.GetComponent and moverObject:GetComponent("PlayerController")
    local dropping = controller and controller.dropThrough

    if dropping or moverVY < 0 or bottom > top + slop then
        contact:setEnabled(false)
    end
end

-- gx, gy are in metres/second^2 (so 9.81 is real-world gravity).
function World.init(gx, gy)
    gx = gx or 0
    gy = gy or 9.81

    love.physics.setMeter(World.PIXELS_PER_METER)
    instance = love.physics.newWorld(
        gx * World.PIXELS_PER_METER,
        gy * World.PIXELS_PER_METER,
        true
    )
    instance:setCallbacks(beginContact, endContact, preSolve)
    return instance
end

function World.reset(gx, gy)
    if instance and not instance:isDestroyed() then
        instance:destroy()
    end
    return World.init(gx, gy)
end

function World.get()
    assert(instance, "World.init() must be called before World.get()")
    return instance
end

function World.update(dt)
    if instance then instance:update(dt) end
end

-- Kept for gameplay code that wants to reason in metres (e.g. "how many
-- metres has the player fallen"). NOT needed when talking to love.physics.
function World.toMeters(v)
    return Vector.new(v.x / World.PIXELS_PER_METER, v.y / World.PIXELS_PER_METER)
end

function World.toPixels(v)
    return Vector.new(v.x * World.PIXELS_PER_METER, v.y * World.PIXELS_PER_METER)
end

return World
