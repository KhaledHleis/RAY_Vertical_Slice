local Component = require('Libraries.universal.component')

local CollisionRenderer = setmetatable({}, { __index = Component })
CollisionRenderer.__index = CollisionRenderer

function CollisionRenderer.new(args)
    local self = Component.new()
    setmetatable(self, CollisionRenderer)
    self.isDebugOverlay = true
    return self
end

function CollisionRenderer:__tostring()
    return "CollisionRenderer"
end

function CollisionRenderer:drawRigidBody(object)
    local rigidBody = object:GetComponent("RigidBody")
    if not rigidBody then return end

    -- No scale here on purpose: RigidBody bakes world scale into its width,
    -- height and radius when the fixture is built, so these are already world
    -- sizes. Scaling them again would draw the outline at scale squared.
    local x, y, angle = object.transform:World()

    love.graphics.push()
    love.graphics.translate(x, y)
    love.graphics.rotate(angle)
    -- Sensors are amber: they occupy space on screen but never stop anything,
    -- and telling the two apart at a glance is the whole point of an overlay.
    if rigidBody.sensor then
        love.graphics.setColor(1, 0.75, 0.2, 1)
    else
        love.graphics.setColor(0, 1, 0, 1)
    end
    love.graphics.setLineWidth(1)

    if rigidBody.shape == "circle" then
        love.graphics.circle("line", 0, 0, rigidBody.radius or 0)
    else
        love.graphics.rectangle("line", -rigidBody.width / 2, -rigidBody.height / 2, rigidBody.width, rigidBody.height)
    end

    love.graphics.pop()
end

function CollisionRenderer:drawLightCollider(object)
    local collider = object:GetComponent("LightCollider")
    if not (collider and collider.worldSegments) then return end

    love.graphics.setColor(0.2, 0.5, 1, 1)
    love.graphics.setLineWidth(2)
    for _, seg in ipairs(collider.worldSegments) do
        love.graphics.line(seg.a.x, seg.a.y, seg.b.x, seg.b.y)
    end
end

function CollisionRenderer:Draw(object)
    self:drawRigidBody(object)
    self:drawLightCollider(object)
    love.graphics.setColor(1, 1, 1, 1)
end

return CollisionRenderer
