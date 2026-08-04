local math = require('math')

local Rotation = {}
Rotation.__index = Rotation

function Rotation.new(rotation)
    local self = setmetatable({},Rotation)
    self.angle = rotation
    return self
end

function Rotation:Rad2deg()
    return self.angle % (2 * math.pi) * 180
end

function Rotation:__tostring()
    return "rotation: " .. self.angle .. " rad "
end

return Rotation