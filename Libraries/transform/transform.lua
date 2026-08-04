local Vector = require('Libraries.transform.vector')
local Rotation = require('Libraries.transform.rotation')

local Transform = {}
Transform.__index = Transform

function Transform.new(position, rotation)
    local self = setmetatable({}, Transform)
    self.position = position or Vector.new(0, 0)
    self.rotation = Rotation.new(rotation or 0)
    return self
end

function Transform:__tostring()
    return "Transform: " .. tostring(self.position) .. " \n " .. tostring(self.rotation)
end

return Transform
