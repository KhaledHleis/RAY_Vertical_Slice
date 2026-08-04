local Component = require('Libraries.universal.component')
local LightWorld = require('Libraries.light_engine.light_world')

local LightDetector = setmetatable({}, { __index = Component })
LightDetector.__index = LightDetector

function LightDetector.new(args)
    local self = Component.new()
    setmetatable(self, LightDetector)
    self.lit = false
    return self
end
function LightDetector:__tostring()
    return "LightDetector"
end
function LightDetector:OnAttach(object)
    self.object = object
    LightWorld.registerDetector(self)
end

function LightDetector:OnDestroy(object)
    LightWorld.unregisterDetector(self)
end

function LightDetector:OnHit(hits)
end

function LightDetector:OnLost()
end

return LightDetector