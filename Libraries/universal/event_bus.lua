-- event_bus.lua
--
-- Global publish/subscribe hub. Lets systems that shouldn't know about each
-- other (light, physics, scene, gameplay) communicate without direct
-- references -- a publisher fires a named event with any payload, and
-- anything can subscribe to it independently.
--
-- This does not replace direct component calls like LightDetector:OnHit();
-- those still fire for whoever owns the component. EventBus is for the
-- *other* listeners: a door that should open when a specific detector is
-- lit, a UI popup on collision, a level-complete check on spawn count, etc.
--
-- Usage:
--   local EventBus = require('Libraries.universal.event_bus')
--
--   local handle = EventBus.subscribe("light:hit", function(detector, hits)
--       print(tostring(detector), "was hit by", #hits, "ray(s)")
--   end)
--
--   EventBus.publish("light:hit", someDetector, hits)
--   EventBus.unsubscribe(handle)
--
-- Components should prefer Component:Subscribe (see component.lua), which
-- auto-unsubscribes when the owning object is destroyed. Call EventBus
-- functions directly only from non-component code (main.lua, managers, etc.)
-- where there's no component lifecycle to hook cleanup into.

local EventBus = {}

local listeners = {} -- eventName -> array of { callback = fn, id = n }
local nextId = 1

-- Registers callback for eventName. Returns an opaque handle to pass to
-- EventBus.unsubscribe. Safe to call from inside a publish callback --
-- new subscribers only take effect on the next publish.
function EventBus.subscribe(eventName, callback)
    assert(type(eventName) == "string", "EventBus.subscribe: eventName must be a string")
    assert(type(callback) == "function", "EventBus.subscribe: callback must be a function")

    listeners[eventName] = listeners[eventName] or {}

    local id = nextId
    nextId = nextId + 1
    table.insert(listeners[eventName], { callback = callback, id = id })

    return { eventName = eventName, id = id }
end

-- Removes a single listener via the handle returned by subscribe(). No-op
-- if the handle is nil or already unsubscribed.
function EventBus.unsubscribe(handle)
    if not handle then return end
    local bucket = listeners[handle.eventName]
    if not bucket then return end

    for i = #bucket, 1, -1 do
        if bucket[i].id == handle.id then
            table.remove(bucket, i)
            break
        end
    end
end

-- Calls every current subscriber of eventName with the given args, in
-- subscription order. Dispatches over a snapshot of the listener list, so a
-- callback that subscribes/unsubscribes during publish doesn't affect the
-- current dispatch.
function EventBus.publish(eventName, ...)
    local bucket = listeners[eventName]
    if not bucket or #bucket == 0 then return end

    local snapshot = {}
    for i, entry in ipairs(bucket) do snapshot[i] = entry end

    for _, entry in ipairs(snapshot) do
        entry.callback(...)
    end
end

-- Removes every listener for every event. Intended for level reloads and
-- tests, mirroring World.reset -- most gameplay code should never need this
-- since Component:Subscribe cleans up per-object listeners automatically.
function EventBus.clear()
    listeners = {}
end

return EventBus
