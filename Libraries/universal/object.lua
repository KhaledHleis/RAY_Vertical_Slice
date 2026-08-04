-- Object.lua
local Vector = require('Libraries.transform.vector')
local Rotation = require('Libraries.transform.rotation')
local Transform = require('Libraries.transform.transform')

local Object = {}
Object.__index = Object

function Object.new(position,rotation)
    local self = setmetatable({}, Object)
    self.trasform = Transform.new(position,rotation)
    return self
end

return Object