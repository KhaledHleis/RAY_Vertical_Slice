local Object = require('Libraries.universal.object')

local Box = setmetatable({}, { __index = Object })
Box.__index = Box

function Box.new(args)
    local self = Object.new(baseArgs)
    self = setmetatable(self, Box)
    
    return self
end

function Box:__tostring()
    return "BaseTile"
end

return Box