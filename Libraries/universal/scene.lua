local EventBus = require('Libraries.universal.event_bus')

local Scene = {}
Scene.__index = Scene

function Scene.new()
    local self = setmetatable({}, Scene)
    self.objects = {}
    self.pendingDestroy = {}
    return self
end

function Scene:Spawn(object)
    table.insert(self.objects, object)
    -- Fires after the object is in self.objects, so anything reacting to
    -- this (a spawn counter, a minimap) can safely query the scene.
    EventBus.publish("scene:spawned", object)
    return object
end

-- Queues the object and every descendant. Destroying a parent destroys its
-- children, as in Unity; the subtree is collected now rather than at flush
-- time so a reparent in between cannot orphan half of it.
function Scene:Destroy(object)
    for _, member in ipairs(object:GetSubtree()) do
        table.insert(self.pendingDestroy, member)
    end
end

function Scene:Update(dt)
    for _, object in ipairs(self.objects) do
        object:Update(dt)
    end
end

-- Separate pass so components that read world transforms see them settled.
-- Kept out of Update because Update is where transforms are *written* --
-- physics readback, Spinner, PlayerController -- and a child reading its
-- parent mid-pass would be a frame behind depending on level file order.
function Scene:LateUpdate(dt)
    for _, object in ipairs(self.objects) do
        object:LateUpdate(dt)
    end
    self:_flushDestroyed()
end

function Scene:Draw()
    for _, object in ipairs(self.objects) do
        object:Draw()
    end
end

function Scene:_flushDestroyed()
    if #self.pendingDestroy == 0 then return end

    for _, object in ipairs(self.pendingDestroy) do
        object:Destroy()
        for i = #self.objects, 1, -1 do
            if self.objects[i] == object then
                table.remove(self.objects, i)
                break
            end
        end
        -- Fires after Object:Destroy (and its own component teardown/
        -- UnsubscribeAll), and after removal from self.objects.
        EventBus.publish("scene:destroyed", object)
    end

    self.pendingDestroy = {}
end

return Scene
