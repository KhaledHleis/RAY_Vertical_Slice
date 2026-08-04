local Component = require('Libraries.universal.component')
local LightWorld = require('Libraries.light.light_world')

local LightCollider = setmetatable({}, { __index = Component })
LightCollider.__index = LightCollider

function LightCollider.new(args)
    local self = Component.new(args)
    setmetatable(self, LightCollider)
    self.localSegments = args.segments or {}
    return self
end

function LightCollider:OnAttach()
    local pos = self.object.transform.position
    local worldSegments = {}
    for _, seg in ipairs(self.localSegments) do
        table.insert(worldSegments, {
            a = pos + seg.a,
            b = pos + seg.b,
            reflective = seg.reflective or 0,
            refractiveIndex = seg.refractiveIndex or 1,
            absorption = seg.absorption or 0,
        })
    end
    self.worldSegments = worldSegments
    LightWorld.registerSegments(self.object, worldSegments)
end

function LightCollider:OnDestroy()
    LightWorld.unregisterSegments(self.object)
end

return LightCollider