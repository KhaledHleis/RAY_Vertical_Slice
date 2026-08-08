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
    -- How far a ray travels before it simply runs out. This used to be a
    -- hard-coded 2000 inside castRay; it is a field now because renderers
    -- need to know it to fade beams out over the same distance.
    self.maxDistance = args.maxDistance or 2000
    self.fan = {}
    return self
end
function LightSource:__tostring()
    return "LightSource"
end

-- Every node returned from here is guaranteed to carry `origin`, `endPoint`
-- and `length`, whether or not it actually touched geometry. `hitPoint` is
-- still only set on a real surface hit, so detector/physics code that tests
-- for it keeps working unchanged; renderers should use `endPoint` instead.
function LightSource:castRay(origin, dir, intensity, depth, travel)
    travel = travel or 0
    local node = {
        origin = origin,
        dir = dir,
        intensity = intensity,
        depth = depth,
        travel = travel,
    }

    -- Too dim to contribute anything. Kill it with zero length so it neither
    -- draws nor registers a hit against a detector.
    if intensity < self.minIntensity then
        node.endPoint = origin
        node.length = 0
        node.dead = true
        return node
    end

    local hit = LightWorld.raycast(origin, dir, self.maxDistance)

    if not hit then
        -- Nothing in the way. The ray still exists, it just runs out of
        -- range, so give it explicit geometry rather than returning a node
        -- with no end point for renderers to silently skip.
        node.endPoint = origin + dir * self.maxDistance
        node.length = self.maxDistance
        node.escaped = true
        return node
    end

    node.hitPoint = hit.point
    node.segment = hit.segment
    node.endPoint = hit.point
    node.length = hit.t

    -- Depth is a bounce budget, so it is checked *after* the cast: a ray at
    -- the limit still travels and still terminates on geometry, it just
    -- does not spawn children.
    if depth >= self.maxDepth then
        return node
    end

    local remaining = intensity * (1 - hit.segment.absorption)
    local childTravel = travel + node.length

    if hit.segment.reflective > 0 then
        local reflectedDir = RayMath.reflect(dir, hit.normal)
        node.reflected = self:castRay(hit.point, reflectedDir, remaining * hit.segment.reflective, depth + 1, childTravel)
    end

    if hit.segment.refractiveIndex ~= 1 then
        local refractedDir = RayMath.refract(dir, hit.normal, 1, hit.segment.refractiveIndex)
        if refractedDir then
            node.refracted = self:castRay(hit.point, refractedDir, remaining * (1 - hit.segment.reflective), depth + 1, childTravel)
        end
    end

    return node
end

function LightSource:Update(object, dt)
    local pos = object.transform.position
    local baseAngle = object.transform.rotation.angle
    self.fan = {}
    -- Guard the single-ray case: rayCount - 1 would be a divide by zero.
    local spread = (self.rayCount > 1) and (self.coneAngle / (self.rayCount - 1)) or 0
    for i = 0, self.rayCount - 1 do
        local angle = baseAngle - self.coneAngle / 2 + spread * i
        local dir = Vector.new(math.cos(angle), math.sin(angle))
        table.insert(self.fan, self:castRay(pos, dir, 1.0, 0, 0))
    end
end

return LightSource
