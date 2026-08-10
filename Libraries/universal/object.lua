-- Object.lua
local Vector = require('Libraries.transform.vector')
local Rotation = require('Libraries.transform.rotation')
local Transform = require('Libraries.transform.transform')

local Object = {}
Object.__index = Object

function Object.new(position, rotation, scale)
    local self = setmetatable({}, Object)
    self.transform = Transform.new(position, rotation, scale)
    self.transform.object = self
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

------------------------------------------------------------------ hierarchy

-- Parents this object to another, or to nothing when parent is nil.
--
-- A child may not have a RigidBody. Box2D owns the transform of anything with
-- a body -- RigidBody:Update writes the body's world position straight into
-- the transform every frame -- so a parented body has two writers and physics
-- wins. Unity has the same rule and quietly ignores the parent; failing here
-- instead means the mistake is found at load, not three levels later.
--
-- Body-to-body attachment is a HingeJoint, which is what the lamp in demo.lua
-- already does.
--
-- A parent may have a RigidBody. That is the useful direction: physics drives
-- the parent, and non-physics children (a LightCollider, a LightSource, a
-- SpriteRenderer) ride along.
function Object:SetParent(parent)
    assert(not self.components["RigidBody"],
        "Object:SetParent: '" .. tostring(self) .. "' has a RigidBody and cannot be a child. "
        .. "Box2D owns its transform. Use a HingeJoint to attach one body to another.")

    self.transform:SetParent(parent and parent.transform or nil)
    return self
end

function Object:GetParent()
    local parent = self.transform.parent
    return parent and parent.object or nil
end

-- Direct children only, in attach order.
function Object:GetChildren()
    local out = {}
    for _, child in ipairs(self.transform.children) do
        if child.object then table.insert(out, child.object) end
    end
    return out
end

-- This object and every descendant, parents before children.
function Object:GetSubtree(out)
    out = out or {}
    table.insert(out, self)
    for _, child in ipairs(self.transform.children) do
        if child.object then child.object:GetSubtree(out) end
    end
    return out
end

-------------------------------------------------------------------- updates

function Object:Update(dt)
    for _, component in pairs(self.components) do
        if component.enabled ~= false and component.Update then component:Update(self, dt) end
    end
end

-- Runs after every object's Update, so anything reading a transform here sees
-- it settled -- no assumptions about component or object ordering. LightSource
-- casts from here for exactly that reason.
function Object:LateUpdate(dt)
    for _, component in pairs(self.components) do
        if component.enabled ~= false and component.LateUpdate then component:LateUpdate(self, dt) end
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
    -- Leave the hierarchy first, so nothing can observe a half-torn-down
    -- subtree through the parent's children list.
    self.transform:SetParent(nil)

    for _, component in pairs(self.components) do
        if component.OnDestroy then component:OnDestroy(self) end
        -- Tears down any EventBus subscriptions made via Component:Subscribe,
        -- regardless of whether the component overrode OnDestroy.
        if component.UnsubscribeAll then component:UnsubscribeAll() end
    end
    self.components = {}
end

function Object:__tostring()
    return self.prefab or "Object"
end

return Object
