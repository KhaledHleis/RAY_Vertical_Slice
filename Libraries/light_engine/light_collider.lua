local Component = require('Libraries.universal.component')
local Vector = require('Libraries.transform.vector')
local LightWorld = require('Libraries.light_engine.light_world')

local LightCollider = setmetatable({}, { __index = Component })
LightCollider.__index = LightCollider

function LightCollider.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, LightCollider)
    self.localSegments = args.segments or {}
    -- When true, worldSegments are recomputed every frame from the owning
    -- object's transform (position + rotation). This is required for any
    -- LightCollider attached to an object that moves after spawn, e.g. a
    -- RigidBody with bodyType = "dynamic" affected by gravity. Defaults to
    -- false to preserve the original "compute once on attach" behaviour for
    -- static geometry such as walls.
    self.dynamic = args.dynamic or false
    return self
end

function LightCollider:__tostring()
    return "LightCollider"
end

-- Recomputes worldSegments in place from the object's current transform,
-- rotating each local segment endpoint by the object's rotation angle and
-- translating it by the object's position.
function LightCollider:syncSegments(object)
    local pos = object.transform.position
    local angle = (object.transform.rotation and object.transform.rotation.angle) or 0
    local c, s = math.cos(angle), math.sin(angle)

    for i, seg in ipairs(self.worldSegments) do
        local localA = self.localSegments[i].a
        local localB = self.localSegments[i].b
        seg.a = Vector.new(pos.x + localA.x * c - localA.y * s, pos.y + localA.x * s + localA.y * c)
        seg.b = Vector.new(pos.x + localB.x * c - localB.y * s, pos.y + localB.x * s + localB.y * c)
    end
end

function LightCollider:OnAttach(object)
    self.object = object

    self.worldSegments = {}
    for _, seg in ipairs(self.localSegments) do
        table.insert(self.worldSegments, {
            a = Vector.new(0, 0),
            b = Vector.new(0, 0),
            reflective = seg.reflective or 0,
            refractiveIndex = seg.refractiveIndex or 1,
            absorption = seg.absorption or 0,
        })
    end

    self:syncSegments(object)
    LightWorld.registerSegments(object, self.worldSegments)
end

function LightCollider:Update(object, dt)
    if not self.dynamic then return end
    self:syncSegments(object)
end

function LightCollider:OnDestroy(object)
    LightWorld.unregisterSegments(object)
end

return LightCollider
