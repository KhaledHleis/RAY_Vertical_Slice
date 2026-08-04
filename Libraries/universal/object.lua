-- Object.lua
local Vector = require('Libraries.transform.vector')
local Rotation = require('Libraries.transform.rotation')
local Transform = require('Libraries.transform.transform')

local Object = {}
Object.__index = Object

function Object.new(position, rotation)
    local self = setmetatable({}, Object)
    self.transform = Transform.new(position, rotation)
    self.components = {}
    return self
end

function Object:AddComponent(component)
    self.components[tostring(component)] = component
    if component.OnAttach then component:OnAttach(self) end
    return component
end

function Object:GetComponent(name)
    return self.components[name]
end

function Object:RemoveComponent(name)
    self.components[name] = nil
end

function Object:Update(dt)
    for _, component in pairs(self.components) do
        if component.enabled ~= false and component.Update then component:Update(self, dt) end
    end
end

function Object:Draw()
    for _, component in pairs(self.components) do
        if component.enabled ~= false and component.Draw then component:Draw(self) end
    end
end

function Object:Destroy()
    for _, component in pairs(self.components) do
        if component.OnDestroy then component:OnDestroy(self) end
    end
    self.components = {}
end

function Object:__tostring()
    return self.prefab or "Object"
end

return Object