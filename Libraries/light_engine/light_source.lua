local Component = require('Libraries.universal.component')
local Vector = require('Libraries.transform.vector')
local RayMath = require('Libraries.light_engine.utils.ray_math')
local LightWorld = require('Libraries.light_engine.light_world')

local LightSource = setmetatable({}, { __index = Component })
LightSource.__index = LightSource

function LightSource.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, LightSource)
    self.rayCount = args.rayCount or 16
    self.coneAngle = args.coneAngle or math.pi * 2
    self.maxDepth = args.maxDepth or 4
    self.minIntensity = args.minIntensity or 0.05
    self.fan = {}
    return self
end
function LightSource:__tostring()
    return "LightSource"
end
function LightSource:castRay(origin, dir, intensity, depth)
    local node = { origin = origin, dir = dir, intensity = intensity, depth = depth }

    if depth >= self.maxDepth or intensity < self.minIntensity then
        return node
    end

    local hit = LightWorld.raycast(origin, dir, 2000)
    if not hit then
        return node
    end

    node.hitPoint = hit.point
    node.segment = hit.segment

    local remaining = intensity * (1 - hit.segment.absorption)

    if hit.segment.reflective > 0 then
        local reflectedDir = RayMath.reflect(dir, hit.normal)
        node.reflected = self:castRay(hit.point, reflectedDir, remaining * hit.segment.reflective, depth + 1)
    end

    if hit.segment.refractiveIndex ~= 1 then
        local refractedDir = RayMath.refract(dir, hit.normal, 1, hit.segment.refractiveIndex)
        if refractedDir then
            node.refracted = self:castRay(hit.point, refractedDir, remaining * (1 - hit.segment.reflective), depth + 1)
        end
    end

    return node
end

function LightSource:Update(object, dt)
    local pos = object.transform.position
    local baseAngle = object.transform.rotation.angle
    self.fan = {}
    for i = 0, self.rayCount - 1 do
        local angle = baseAngle - self.coneAngle / 2 + (self.coneAngle * i / (self.rayCount - 1))
        local dir = Vector.new(math.cos(angle), math.sin(angle))
        table.insert(self.fan, self:castRay(pos, dir, 1.0, 0))
    end
end

return LightSource