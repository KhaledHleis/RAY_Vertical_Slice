local Vector = require('Libraries.transform.vector')

-- TIR probe: a single glass face at a very steep (near-grazing) incidence.
-- Physically, if this face were being exited from inside glass (n1=1.5 ->
-- n2=1) at a steep enough angle, this should totally-internally-reflect
-- (refract() returns nil) rather than transmit. Because light_source.lua
-- always calls RayMath.refract with n1 hardcoded to 1, entering-from-air
-- math is used regardless, and TIR can structurally never trigger --
-- refracted should be non-nil here even though a real optical system
-- would block/reflect it.
local ex, ey = 50, 150
local eangle = math.rad(80)
local dx, dy = math.cos(eangle), math.sin(eangle)
local dist = 150
local glassX, glassY = ex + dist * dx, ey + dist * dy

return {
    { id = "emitter", prefab = "Emitter",           position = Vector.new(ex, ey), rotation = eangle },
    { id = "glass",   prefab = "GlassFaceVertical",  position = Vector.new(glassX, glassY) },
}
