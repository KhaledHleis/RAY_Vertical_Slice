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

function Vector:dot(other)
    return self.x * other.x + self.y * other.y
end

function Vector:cross(other)
    return self.x * other.y - self.y * other.x
end

function Vector:length()
    return math.sqrt(self.x * self.x + self.y * self.y)
end

function Vector:normalized()
    local len = self:length()
    if len == 0 then
        return Vector.new(0, 0)
    end
    return Vector.new(self.x / len, self.y / len)
end

return Vector