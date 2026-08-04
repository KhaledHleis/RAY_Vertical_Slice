local Vector = require('Libraries.transform.vector')
local Ray = {}
Ray.__index = Ray

function Ray.new()
    local self = setmetatable({},Ray)
    return self
end


return Ray
