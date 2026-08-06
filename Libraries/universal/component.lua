local EventBus = require('Libraries.universal.event_bus')

local Component = {}
Component.__index = Component

function Component.new()
    local self = setmetatable({}, Component)
    self.enabled = true
    self._subscriptions = {}
    return self
end

function Component:OnAttach(object) end
function Component:Update(object, dt) end
function Component:Draw(object) end
function Component:OnDestroy(object) end

-- Subscribes to an EventBus event and remembers the handle so it gets torn
-- down automatically by Object:Destroy (via UnsubscribeAll below). Prefer
-- this over calling EventBus.subscribe directly from a component.
function Component:Subscribe(eventName, callback)
    local handle = EventBus.subscribe(eventName, callback)
    table.insert(self._subscriptions, handle)
    return handle
end

-- Removes a single subscription made through Component:Subscribe.
function Component:Unsubscribe(handle)
    if not handle then return end
    EventBus.unsubscribe(handle)
    for i = #self._subscriptions, 1, -1 do
        if self._subscriptions[i] == handle then
            table.remove(self._subscriptions, i)
            break
        end
    end
end

-- Removes every subscription this component has made. Called automatically
-- by Object:Destroy after OnDestroy, so components don't need to remember
-- to clean up their own listeners.
function Component:UnsubscribeAll()
    for _, handle in ipairs(self._subscriptions) do
        EventBus.unsubscribe(handle)
    end
    self._subscriptions = {}
end

function Component:__tostring()
    return "Component"
end

return Component
