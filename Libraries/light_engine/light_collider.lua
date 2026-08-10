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
    -- Transform:World() once and compose by hand rather than calling
    -- TransformPoint per endpoint: this runs for every segment of every
    -- dynamic collider every frame, and TransformPoint would re-walk the
    -- parent chain each time.
    --
    -- Scale falls out for free here, unlike RigidBody -- these segments are
    -- our own geometry, rebuilt every frame, with no Box2D fixture to replace.
    local wx, wy, angle, scale = object.transform:World()
    local c, s = math.cos(angle), math.sin(angle)

    for i, seg in ipairs(self.worldSegments) do
        local localA = self.localSegments[i].a
        local localB = self.localSegments[i].b
        local ax, ay = localA.x * scale, localA.y * scale
        local bx, by = localB.x * scale, localB.y * scale
        seg.a = Vector.new(wx + ax * c - ay * s, wy + ax * s + ay * c)
        seg.b = Vector.new(wx + bx * c - by * s, wy + bx * s + by * c)
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
    if self.dynamic then LightWorld.registerCollider(self) end
end

-- No Update: LightWorld.syncColliders drives dynamic colliders in one pass
-- between Scene:Update and Scene:LateUpdate. See the note in light_world.lua.

function LightCollider:OnDestroy(object)
    LightWorld.unregisterSegments(object)
    LightWorld.unregisterCollider(self)
end

return LightCollider
