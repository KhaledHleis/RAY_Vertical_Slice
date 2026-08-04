local Component = require('Libraries.universal.component')
local LightWorld = require('Libraries.light_engine.light_world')

local LightCollider = setmetatable({}, { __index = Component })
LightCollider.__index = LightCollider

function LightCollider.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, LightCollider)
    self.localSegments = args.segments or {}
    return self
end
function LightCollider:__tostring()
    return "LightCollider"
end
function LightCollider:OnAttach(object)
    self.object = object
    local pos = object.transform.position
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
    LightWorld.registerSegments(object, worldSegments)
end

function LightCollider:OnDestroy(object)
    LightWorld.unregisterSegments(object)
end

return LightCollider