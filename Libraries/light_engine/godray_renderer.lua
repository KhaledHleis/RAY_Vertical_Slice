local Component = require('Libraries.universal.component')

local GodrayRenderer = setmetatable({}, { __index = Component })
GodrayRenderer.__index = GodrayRenderer

function GodrayRenderer.new(args)
    local self = Component.new()
    setmetatable(self, GodrayRenderer)
    self.lightSource = nil
    return self
end
function GodrayRenderer:__tostring()
    return "GodrayRenderer"
end
function GodrayRenderer:OnAttach(object)
    self.lightSource = object:GetComponent("LightSource")
end

function GodrayRenderer:drawQuadPair(nodeA, nodeB)
    if not (nodeA and nodeB and nodeA.hitPoint and nodeB.hitPoint) then
        return
    end

    local alpha = (nodeA.intensity + nodeB.intensity) / 2
    love.graphics.setColor(1, 1, 0.9, alpha * 0.3)
    love.graphics.polygon("fill",
        nodeA.origin.x, nodeA.origin.y,
        nodeA.hitPoint.x, nodeA.hitPoint.y,
        nodeB.hitPoint.x, nodeB.hitPoint.y,
        nodeB.origin.x, nodeB.origin.y
    )

    self:drawQuadPair(nodeA.reflected, nodeB.reflected)
    self:drawQuadPair(nodeA.refracted, nodeB.refracted)
end

function GodrayRenderer:Draw(object)
    if not self.lightSource then return end
    local fan = self.lightSource.fan
    for i = 1, #fan - 1 do
        self:drawQuadPair(fan[i], fan[i + 1])
    end
end

return GodrayRenderer