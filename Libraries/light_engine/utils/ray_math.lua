local Vector = require('Libraries.transform.vector')
local EPSILON = 1e-9
local RayMath = {}

function RayMath.segmentIntersect(origin, dir, maxDist, a, b)
    local edge = b - a
    local denom = dir:cross(edge)

    if math.abs(denom) < EPSILON then
        return nil
    end

    local Q = a - origin
    local t = Q:cross(edge) / denom
    local u = Q:cross(dir) / denom

    if t <= EPSILON or t > maxDist or u < 0 or u > 1 then
        return nil
    end

    local hitPoint = origin + dir * t
    local normal = Vector.new(-edge.y, edge.x):normalized()
    if normal:dot(dir) > 0 then
        normal = normal * -1
    end

    return t, hitPoint, normal
end


function RayMath.reflect(dir, normal)
    return dir - normal * (2 * dir:dot(normal))
end

function RayMath.refract(dir, normal, n1, n2)
    local ratio = n1 / n2
    local cosI = -dir:dot(normal)
    local sin2T = ratio * ratio * (1 - cosI * cosI)
    if sin2T > 1 then
        return nil
    end
    local cosT = math.sqrt(1 - sin2T)
    return dir * ratio + normal * (ratio * cosI - cosT)
end

return RayMath
