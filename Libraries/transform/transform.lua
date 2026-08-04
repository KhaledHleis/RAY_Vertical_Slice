local Vector = require('Libraries.transform.vector')
local Rotation = require('Libraries.transform.rotation')

local Trasform = {}
Trasform.__index = Trasform

function Trasform.new(position,rotation)
    local self = setmetatable({},Trasform)
    self.position = position
    self.rotation = Rotation.new(rotation)
    return self
end

function Trasform:__tostring()
    return "Trasform: " .. tostring(self.position) .. " \n " .. tostring(self.rotation) .. ""
end

return Trasform