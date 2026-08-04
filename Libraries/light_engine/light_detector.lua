local Component = require('Libraries.universal.component')
local LightWorld = require('Libraries.light_engine.light_world')

local LightDetector = setmetatable({}, { __index = Component })
LightDetector.__index = LightDetector

function LightDetector.new(args)
    local self = Component.new(args)
    setmetatable(self, LightDetector)
    self.lit = false
    return self
end

function LightDetector:OnAttach()
    LightWorld.registerDetector(self)
end

function LightDetector:OnDestroy()
    LightWorld.unregisterDetector(self)
end

function LightDetector:OnHit(hits)
end

function LightDetector:OnLost()
end

return LightDetector