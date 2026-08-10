local Vector = require('Libraries.transform.vector')
local World = require('Libraries.physics.world')
local Component = require('Libraries.universal.component')

local RigidBody = setmetatable({}, { __index = Component })
RigidBody.__index = RigidBody

function RigidBody.new(args)
    args = args or {}
    local self = Component.new()
    self = setmetatable(self, RigidBody)

    self.bodyType = args.bodyType or "dynamic"
    self.shape = args.shape or "rectangle"
    self.width = args.width or 16
    self.height = args.height or 16
    self.radius = args.radius
    self.density = args.density or 1
    self.friction = args.friction or 0.3
    self.restitution = args.restitution or 0
    self.fixedRotation = args.fixedRotation or false
    -- Multiplier on world gravity for this body. PlayerController sets it to
    -- 0 so it can integrate its own gravity curve.
    self.gravityScale = args.gravityScale or 1
    -- Continuous collision detection: needed for anything small and fast that
    -- would otherwise tunnel through thin geometry.
    self.bullet = args.bullet or false
    -- Only stops bodies arriving from above. Honoured by World's preSolve.
    self.oneWay = args.oneWay or false

    self.body = nil
    self.fixture = nil
    self.shapeObj = nil
    -- World scale at the moment the fixture was built. See OnAttach.
    self.bakedScale = 1

    return self
end

function RigidBody:OnAttach(object)
    local world = World.get()

    -- love.physics is configured with setMeter(World.PIXELS_PER_METER), so it
    -- expects and returns PIXELS. Pass transform values through unscaled.
    --
    -- World, not local: an object with a RigidBody can never be a child (see
    -- Object:SetParent), so these are the same numbers today. Reading the
    -- world values anyway means this line stays correct if that rule is ever
    -- relaxed.
    local x, y, angle, scale = object.transform:World()

    -- Scale is baked into the fixture here and never again: Box2D cannot
    -- resize a shape, only replace it. Changing transform.scale after this
    -- point moves the sprite and leaves the collider behind. The authored
    -- width/height are overwritten with the effective world size, so
    -- PlayerController's probes and CollisionRenderer's outline -- both of
    -- which work in world pixels -- stay correct with no changes.
    self.bakedScale = scale
    self.width = self.width * scale
    self.height = self.height * scale
    if self.radius then self.radius = self.radius * scale end

    self.body = love.physics.newBody(world, x, y, self.bodyType)
    self.body:setAngle(angle)
    self.body:setFixedRotation(self.fixedRotation)
    self.body:setGravityScale(self.gravityScale)
    self.body:setBullet(self.bullet)

    if self.shape == "circle" then
        self.shapeObj = love.physics.newCircleShape(self.radius)
    else
        self.shapeObj = love.physics.newRectangleShape(self.width, self.height)
    end

    self.fixture = love.physics.newFixture(self.body, self.shapeObj, self.density)
    self.fixture:setFriction(self.friction)
    self.fixture:setRestitution(self.restitution)
    self.fixture:setUserData(object)
end

function RigidBody:AddForce(fx, fy)
    self.body:applyForce(fx, fy)
end

function RigidBody:SetVelocity(vx, vy)
    self.body:setLinearVelocity(vx, vy)
end

function RigidBody:Update(object, dt)
    if self.bodyType == "static" then return end
    -- Already in pixels, thanks to setMeter().
    local x, y = self.body:getPosition()
    object.transform.position.x = x
    object.transform.position.y = y
    object.transform.rotation.angle = self.body:getAngle()
end

function RigidBody:OnDestroy(object)
    if self.body and not self.body:isDestroyed() then
        self.body:destroy()
    end
end

function RigidBody:__tostring()
    return "RigidBody"
end

return RigidBody
