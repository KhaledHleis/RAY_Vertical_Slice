local Component = require('Libraries.universal.component')

local DebugLightRenderer = setmetatable({}, { __index = Component })
DebugLightRenderer.__index = DebugLightRenderer

function DebugLightRenderer.new(args)
    local self = Component.new()
    setmetatable(self, DebugLightRenderer)
    return self
end
function DebugLightRenderer:__tostring()
    return "DebugLightRenderer"
end

function DebugLightRenderer:Draw(object)
    local collider = object:GetComponent("LightCollider")
    if collider and collider.worldSegments then
        for _, seg in ipairs(collider.worldSegments) do
            if seg.refractiveIndex and seg.refractiveIndex ~= 1 then
                love.graphics.setColor(0.3, 0.6, 1, 1)      -- glass: blue
            elseif seg.reflective and seg.reflective > 0 then
                love.graphics.setColor(0.9, 0.9, 0.2, 1)    -- mirror: yellow
            elseif seg.absorption and seg.absorption > 0 then
                love.graphics.setColor(0.8, 0.2, 0.2, 1)    -- absorber: red
            else
                love.graphics.setColor(1, 1, 1, 1)
            end
            love.graphics.setLineWidth(3)
            love.graphics.line(seg.a.x, seg.a.y, seg.b.x, seg.b.y)
        end
    end

    local source = object:GetComponent("LightSource")
    if source and source.fan then
        love.graphics.setLineWidth(1)
        local function drawNode(node)
            if not (node and node.endPoint) then return end
            if node.escaped then
                love.graphics.setColor(1, 0.6, 0.6, 0.4)   -- hit nothing: dim red
            else
                love.graphics.setColor(1, 1, 0.6, 0.6)
            end
            love.graphics.line(node.origin.x, node.origin.y, node.endPoint.x, node.endPoint.y)
            drawNode(node.reflected)
            drawNode(node.refracted)
        end
        for _, node in ipairs(source.fan) do drawNode(node) end
    end

    local detector = object:GetComponent("LightDetector")
    if detector then
        if detector.lit then
            love.graphics.setColor(1, 1, 0.3, 1)
        else
            love.graphics.setColor(0.4, 0.4, 0.4, 1)
        end
        local x, y = object.transform:World()
        love.graphics.circle("fill", x, y, 6)
    end

    love.graphics.setColor(1, 1, 1, 1)
end

return DebugLightRenderer
