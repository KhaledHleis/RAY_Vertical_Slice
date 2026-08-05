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
    local deferred = nil
    for _, component in pairs(self.components) do
        if component.enabled ~= false and component.Draw then
            if component.isDebugOverlay then
                deferred = deferred or {}
                table.insert(deferred, component)
            else
                component:Draw(self)
            end
        end
    end
    if deferred then
        for _, component in ipairs(deferred) do
            component:Draw(self)
        end
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