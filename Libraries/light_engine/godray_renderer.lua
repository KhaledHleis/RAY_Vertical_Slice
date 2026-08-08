local Component = require('Libraries.universal.component')

local GodrayRenderer = setmetatable({}, { __index = Component })
GodrayRenderer.__index = GodrayRenderer

-- Blank 4-vertex quad, filled in per beam. Vertex format is the LOVE default:
-- x, y, u, v, r, g, b, a.
local BLANK_QUAD = {
    { 0, 0, 0, 0, 1, 1, 1, 1 },
    { 0, 0, 0, 0, 1, 1, 1, 1 },
    { 0, 0, 0, 0, 1, 1, 1, 1 },
    { 0, 0, 0, 0, 1, 1, 1, 1 },
}

function GodrayRenderer.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, GodrayRenderer)
    self.lightSource = nil
    self.color = args.color or { 1, 1, 0.9 }
    self.strength = args.strength or 0.3
    -- Distance over which a beam fades to nothing. Leave nil to inherit the
    -- light source's maxDistance, so a ray that hits nothing fades out exactly
    -- as it reaches the end of its range instead of stopping on a hard edge.
    self.falloff = args.falloff
    self.mesh = nil
    return self
end

function GodrayRenderer:__tostring()
    return "GodrayRenderer"
end

function GodrayRenderer:OnAttach(object)
    self.lightSource = object:GetComponent("LightSource")
end

-- Quadratic ramp to zero at `range`. Reaching exactly zero matters: it is what
-- lets an unobstructed beam end without a visible cut-off line.
local function falloffAt(distance, range)
    if not range or range <= 0 then return 1 end
    local t = distance / range
    if t >= 1 then return 0 end
    local k = 1 - t
    return k * k
end

function GodrayRenderer:getMesh()
    if not self.mesh then
        -- "fan" mode tolerates degenerate and self-intersecting quads, which
        -- love.graphics.polygon("fill", ...) does not: every beam leaving the
        -- source shares an origin, and reflected pairs can cross each other.
        self.mesh = love.graphics.newMesh(BLANK_QUAD, "fan", "stream")
    end
    return self.mesh
end

function GodrayRenderer:drawQuadPair(nodeA, nodeB, range)
    if not (nodeA and nodeB and nodeA.endPoint and nodeB.endPoint) then
        return
    end

    local r, g, b = self.color[1], self.color[2], self.color[3]
    local aNear = nodeA.intensity * self.strength * falloffAt(nodeA.travel, range)
    local aFar  = nodeA.intensity * self.strength * falloffAt(nodeA.travel + nodeA.length, range)
    local bNear = nodeB.intensity * self.strength * falloffAt(nodeB.travel, range)
    local bFar  = nodeB.intensity * self.strength * falloffAt(nodeB.travel + nodeB.length, range)

    if (aNear + aFar + bNear + bFar) > 0 then
        local mesh = self:getMesh()
        mesh:setVertices({
            { nodeA.origin.x,   nodeA.origin.y,   0, 0, r, g, b, aNear },
            { nodeA.endPoint.x, nodeA.endPoint.y, 0, 0, r, g, b, aFar },
            { nodeB.endPoint.x, nodeB.endPoint.y, 0, 0, r, g, b, bFar },
            { nodeB.origin.x,   nodeB.origin.y,   0, 0, r, g, b, bNear },
        })
        -- Mesh vertex colours are multiplied by the current draw colour.
        love.graphics.setColor(1, 1, 1, 1)
        love.graphics.draw(mesh)
    end

    self:drawQuadPair(nodeA.reflected, nodeB.reflected, range)
    self:drawQuadPair(nodeA.refracted, nodeB.refracted, range)
end

function GodrayRenderer:Draw(object)
    if not self.lightSource then return end
    local fan = self.lightSource.fan
    local range = self.falloff or self.lightSource.maxDistance

    for i = 1, #fan - 1 do
        self:drawQuadPair(fan[i], fan[i + 1], range)
    end

    love.graphics.setColor(1, 1, 1, 1)
end

return GodrayRenderer
