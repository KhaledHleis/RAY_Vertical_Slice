local Component = {}
Component.__index = Component

function Component.new()
    local self = setmetatable({}, Component)
    self.enabled = true
    return self
end

function Component:OnAttach(object) end
function Component:Update(object, dt) end
function Component:Draw(object) end
function Component:OnDestroy(object) end

function Component:__tostring()
    return "Component"
end

return Component
