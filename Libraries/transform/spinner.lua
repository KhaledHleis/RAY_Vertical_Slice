local Component = require('Libraries.universal.component')
local Spinner = setmetatable({}, { __index = Component })
Spinner.__index = Spinner

function Spinner.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, Spinner)
    self.speed = args.speed or math.pi
    return self
end

function Spinner:Update(object,dt)
    object.transform.rotation.angle = object.transform.rotation.angle + self.speed*dt
end

function Spinner:__tostring()
    return "Spinner"
end

return Spinner