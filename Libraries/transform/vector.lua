-- vector.lua
local Vector = {}
Vector.__index = Vector

function Vector.new(x, y)
    local self = setmetatable({}, Vector)
    self.x = x
    self.y = y
    return self
end

-- allow Vector(x, y) instead of Vector.new(x, y)
setmetatable(Vector, {
    __call = function(_, x, y)
        return Vector.new(x, y)
    end
})

function Vector:__tostring()
    return "vector: (" .. self.x .. "," .. self.y .. ")"
end

function Vector.__add(a, b)
    return Vector.new(a.x + b.x, a.y + b.y)
end

function Vector.__sub(a, b)
    return Vector.new(a.x - b.x, a.y - b.y)
end

function Vector.__mul(a, scalar)
    return Vector.new(a.x * scalar, a.y * scalar)
end

return Vector