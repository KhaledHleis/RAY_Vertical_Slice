local RayMath = require('Libraries.light_engine.utils.ray_math')
local EventBus = require('Libraries.universal.event_bus')

local LightWorld = {}
local segments = {}
local detectors = {}
local frameHits = {}
local dynamicColliders = {}

function LightWorld.registerSegments(owner, segmentList)
    for _, seg in ipairs(segmentList) do
        seg.owner = owner
        table.insert(segments, seg)
    end
end

function LightWorld.unregisterSegments(owner)
    for i = #segments, 1, -1 do
        if segments[i].owner == owner then
            table.remove(segments, i)
        end
    end
end

-- Dynamic colliders are synced here, in one pass, rather than from each
-- collider's Update. Two reasons, and the second is the important one.
--
-- Scene:Update walks objects in level-file order, so a collider that syncs
-- during Update bakes whatever the transform held at that moment. A source
-- appearing earlier in the file then casts against last frame's segments --
-- a lag that depends on file order and shows up as light lagging behind a
-- moving mirror. And with parenting, a child collider whose parent appears
-- later in the file has the same problem one level up.
--
-- Syncing all of them between Update and LateUpdate removes both: every
-- transform has settled, and every source casts afterwards.
function LightWorld.registerCollider(collider)
    table.insert(dynamicColliders, collider)
end

function LightWorld.unregisterCollider(collider)
    for i = #dynamicColliders, 1, -1 do
        if dynamicColliders[i] == collider then
            table.remove(dynamicColliders, i)
        end
    end
end

function LightWorld.syncColliders()
    for i = 1, #dynamicColliders do
        local collider = dynamicColliders[i]
        if collider.object then collider:syncSegments(collider.object) end
    end
end

function LightWorld.registerDetector(detector)
    table.insert(detectors, detector)
end

function LightWorld.unregisterDetector(detector)
    for i = #detectors, 1, -1 do
        if detectors[i] == detector then
            table.remove(detectors, i)
        end
    end
end

function LightWorld.raycast(origin, dir, maxDist)
    local closest = nil
    local closestT = maxDist
    for _, seg in ipairs(segments) do
        local t, point, normal = RayMath.segmentIntersect(origin, dir, closestT, seg.a, seg.b)
        if t then
            closest = { t = t, point = point, normal = normal, segment = seg }
            closestT = t
        end
    end
    if closest then
        table.insert(frameHits, closest)
    end
    return closest
end

function LightWorld.resolveDetectors()
    local hitOwners = {}
    for _, hit in ipairs(frameHits) do
        hitOwners[hit.segment.owner] = hitOwners[hit.segment.owner] or {}
        table.insert(hitOwners[hit.segment.owner], hit)
    end

    for _, detector in ipairs(detectors) do
        local owner = detector.object
        local hits = hitOwners[owner]
        if hits and not detector.lit then
            detector.lit = true
            detector:OnHit(hits)
            -- Lets anything else (a door, a UI cue, a puzzle manager) react
            -- to this specific detector lighting up without needing to be a
            -- LightDetector subclass or hold a reference to it.
            EventBus.publish("light:hit", detector, hits)
        elseif not hits and detector.lit then
            detector.lit = false
            detector:OnLost()
            EventBus.publish("light:lost", detector)
        end
    end

    frameHits = {}
end

-- Registration counts: segments, detectors, dynamic colliders. Nothing in the
-- render path uses these -- they exist so a level switch can be leak-checked
-- from a test or a debug overlay, where "all three are zero after unload" is
-- the whole assertion.
function LightWorld.stats()
    return #segments, #detectors, #dynamicColliders
end

-- Drops every registration in one go. Colliders, detectors and segments all
-- unregister themselves from OnDestroy, so this is not the normal path -- it
-- is the level-switch path, where "almost everything unregistered" is not
-- good enough. A single segment left behind holds a reference to its owner
-- Object, which holds its components, which holds the level.
function LightWorld.clear()
    segments = {}
    detectors = {}
    frameHits = {}
    dynamicColliders = {}
end

return LightWorld