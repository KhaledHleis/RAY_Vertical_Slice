local Vector = require('Libraries.transform.vector')

-- Requires DebugLightRenderer registered in component_registry.lua:
--   DebugLightRenderer = require('Libraries.light_engine.debug_light_renderer'),
-- (copy debug_light_renderer.lua into Libraries/light_engine/ first)

return {
    Emitter = {
        components = {
            { type = "LightSource", args = { rayCount = 2, coneAngle = 0, maxDepth = 4, minIntensity = 0.05 } },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    FanEmitter = {
        components = {
            { type = "LightSource", args = { rayCount = 40, coneAngle = math.rad(60), maxDepth = 4, minIntensity = 0.05 } },
            { type = "GodrayRenderer", args = {} },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    -- "\" diagonal, reflects rightward<->downward
    MirrorDiag1 = {
        components = {
            { type = "LightCollider", args = {
                segments = { { a = Vector.new(-35, -35), b = Vector.new(35, 35), reflective = 1, absorption = 0 } },
            } },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    -- "/" diagonal
    MirrorDiag2 = {
        components = {
            { type = "LightCollider", args = {
                segments = { { a = Vector.new(-35, 35), b = Vector.new(35, -35), reflective = 1, absorption = 0 } },
            } },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    PartialMirrorDiag1 = {
        components = {
            { type = "LightCollider", args = {
                segments = { { a = Vector.new(-35, -35), b = Vector.new(35, 35), reflective = 0.5, absorption = 0.5 } },
            } },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    -- horizontal, only crosses non-horizontal rays -- used for grazing test & box zone
    MirrorFlatHoriz = {
        components = {
            { type = "LightCollider", args = {
                segments = { { a = Vector.new(-60, 0), b = Vector.new(60, 0), reflective = 1, absorption = 0 } },
            } },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    -- vertical, blocks horizontal-ish rays
    AbsorberVertical = {
        components = {
            { type = "LightCollider", args = {
                segments = { { a = Vector.new(0, -40), b = Vector.new(0, 40), reflective = 0, absorption = 1 } },
            } },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    GlassFaceVertical = {
        components = {
            { type = "LightCollider", args = {
                segments = { { a = Vector.new(0, -60), b = Vector.new(0, 60), reflective = 0, refractiveIndex = 1.5, absorption = 0 } },
            } },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    -- vertical plate, catches horizontal-ish rays
    Detector = {
        components = {
            { type = "LightCollider", args = {
                segments = { { a = Vector.new(0, -25), b = Vector.new(0, 25), reflective = 0, absorption = 1 } },
            } },
            { type = "LightDetector", args = {} },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    -- horizontal plate, catches vertical-ish rays
    DetectorHoriz = {
        components = {
            { type = "LightCollider", args = {
                segments = { { a = Vector.new(-25, 0), b = Vector.new(25, 0), reflective = 0, absorption = 1 } },
            } },
            { type = "LightDetector", args = {} },
            { type = "DebugLightRenderer", args = {} },
        },
    },
    HingeMirror = {
        components = {
            { type = "LightCollider", args = {
                segments = { { a = Vector.new(-40, -40), b = Vector.new(40, 40), reflective = 1, absorption = 0 } },
            } },
            { type = "RigidBody", args = { bodyType = "dynamic", width = 80, height = 4 } },
            { type = "DebugLightRenderer", args = {} },
        },
    },
}
