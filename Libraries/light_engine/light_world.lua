local RayMath = require('Libraries.light_engine.utils.ray_math')
local EventBus = require('Libraries.universal.event_bus')

local LightWorld = {}
local segments = {}
local detectors = {}
local frameHits = {}

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

return LightWorld