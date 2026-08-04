local Vector = require('Libraries.transform.vector')

local World = {}
World.PIXELS_PER_METER = 64

local instance = nil

function World.init(gx, gy)
    instance = love.physics.newWorld(gx or 0, gy or 9.81, true)
    return instance
end

function World.reset(gx, gy)
    if instance and not instance:isDestroyed() then
        instance:destroy()
    end
    return World.init(gx, gy)
end

function World.get()
    assert(instance, "World.init() must be called before World.get()")
    return instance
end

function World.update(dt)
    if instance then instance:update(dt) end
end

function World.toMeters(v)
    return Vector.new(v.x / World.PIXELS_PER_METER, v.y / World.PIXELS_PER_METER)
end

function World.toPixels(v)
    return Vector.new(v.x * World.PIXELS_PER_METER, v.y * World.PIXELS_PER_METER)
end

return World
