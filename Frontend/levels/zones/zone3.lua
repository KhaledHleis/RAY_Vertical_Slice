local Vector = require('Libraries.transform.vector')

local ex, ey = 50, 150
local eangle = math.rad(20)
local dx, dy = math.cos(eangle), math.sin(eangle)

local dist1 = 260
local glassInX, glassInY = ex + dist1 * dx, ey + dist1 * dy

-- compute the actual bent direction the engine will produce (n1=1 hardcoded,
-- n2=1.5, normal facing against the ray i.e. (-1,0) for a rightward-ish ray)
local n1, n2 = 1, 1.5
local normalX, normalY = -1, 0
local cosI = -(dx * normalX + dy * normalY)
local ratio = n1 / n2
local sin2T = ratio * ratio * (1 - cosI * cosI)
local cosT = math.sqrt(1 - sin2T)
local bentX = dx * ratio + normalX * (ratio * cosI - cosT)
local bentY = dy * ratio + normalY * (ratio * cosI - cosT)

local dist2 = 120
local glassOutX, glassOutY = glassInX + bentX * dist2, glassInY + bentY * dist2

local detDist = 200
local detX, detY = glassOutX + bentX * detDist, glassOutY + bentY * detDist

return {
    { id = "emitter",   prefab = "Emitter",           position = Vector.new(ex, ey), rotation = eangle },
    { id = "glass_in",  prefab = "GlassFaceVertical", position = Vector.new(glassInX, glassInY) },
    { id = "glass_out", prefab = "GlassFaceVertical", position = Vector.new(glassOutX, glassOutY) },
    { id = "detector",  prefab = "Detector",          position = Vector.new(detX, detY) },
    { id = "strayflag", prefab = "Detector",          position = Vector.new(ex + dist1*dx + (dist1+dist2+detDist)*dx - dist1*dx, ey + (dist1+dist2+detDist)*dy) },
}
