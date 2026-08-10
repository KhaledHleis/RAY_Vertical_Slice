-- Prefab definitions.
--
-- Edited with Tools/prefab_editor. Hand edits are preserved on the next load
-- as long as they stay inside the supported data subset (tables, numbers,
-- strings, booleans, Vector.new and math.*).

local Vector = require('Libraries.transform.vector')
local math = require('math')

return {
    Box = {
        components = {
            {
                type = "SpriteRenderer",
                args = {
                    path = "Resources/sprites/test/box.png",
                    scale = { x = 4, y = 4 },
                },
            },
            {
                type = "RigidBody",
                args = {
                    bodyType = "dynamic",
                    width = 64,
                    height = 64,
                },
            },
            {
                type = "CollisionRenderer",
                args = {},
            },
            {
                type = "LightCollider",
                args = {
                    dynamic = true,
                    segments = {
                        { a = Vector.new(-32, -32), b = Vector.new(32, -32), reflective = 0, refractiveIndex = 1, absorption = 1 },
                        { a = Vector.new(-32, -32), b = Vector.new(-32, 32), reflective = 0, refractiveIndex = 1, absorption = 1 },
                        { a = Vector.new(-32, 32), b = Vector.new(32, 32), reflective = 0, refractiveIndex = 1, absorption = 1 },
                        { a = Vector.new(32, 32), b = Vector.new(32, -32), reflective = 0, refractiveIndex = 1, absorption = 1 },
                    },
                },
            },
        },
    },

    -- RigidBody must come first: PlayerController grabs it in OnAttach, and
    -- prefab components are attached in declaration order.
    --
    -- The player is 6x12 at 8px-tile scale, which is what the Tune defaults
    -- were dialled in against. Density is well above the crates' so pushing
    -- actually moves them; friction is forced to 0 by the controller.
    Player = {
        components = {
            {
                type = "RigidBody",
                args = {
                    bodyType = "dynamic",
                    width = 6,
                    height = 12,
                    density = 10,
                    friction = 0,
                    restitution = 0,
                    fixedRotation = true,
                    bullet = true,
                    gravityScale = 0,
                },
            },
            {
                type = "PlayerController",
                args = {},
            },
            {
                type = "PlayerRenderer",
                args = {},
            },
            {
                type = "LightCollider",
                args = {
                    dynamic = true,
                    segments = {
                        { a = Vector.new(-3, -6), b = Vector.new(3, -6), absorption = 1 },
                        { a = Vector.new(3, -6), b = Vector.new(3, 6), absorption = 1 },
                        { a = Vector.new(3, 6), b = Vector.new(-3, 6), absorption = 1 },
                        { a = Vector.new(-3, 6), b = Vector.new(-3, -6), absorption = 1 },
                    },
                },
            },
        },
    },

    -- Drop through by holding down and pressing jump.
    OneWayPlatform = {
        components = {
            {
                type = "RigidBody",
                args = {
                    bodyType = "static",
                    width = 64,
                    height = 4,
                    oneWay = true,
                },
            },
            {
                type = "CollisionRenderer",
                args = {},
            },
        },
    },

    Anchor = {
        components = {
            {
                type = "RigidBody",
                args = {
                    bodyType = "static",
                    width = 4,
                    height = 4,
                },
            },
            {
                type = "CollisionRenderer",
                args = {},
            },
        },
    },

    LightCone = {
        components = {
            {
                type = "LightSource",
                args = {
                    rayCount = 32,
                    coneAngle = math.pi / 3,
                    maxDepth = 4,
                },
            },
            {
                type = "GodrayRenderer",
                args = {},
            },
        },
    },

    LightWall = {
        components = {
            {
                type = "LightCollider",
                args = {
                    segments = {
                        { a = Vector.new(-32, 0), b = Vector.new(32, 0), reflective = 0.6, absorption = 0.1 },
                    },
                },
            },
            {
                type = "CollisionRenderer",
                args = {},
            },
        },
    },

    -- A physical mirror: falls under gravity and collides like any other
    -- RigidBody, while its LightCollider surface is fully reflective and
    -- stays glued to it every frame (dynamic = true) so it keeps bouncing
    -- light correctly as it moves.
    Mirror = {
        components = {
            {
                type = "SpriteRenderer",
                args = {
                    path = "Resources/sprites/test/mirror.png",
                    scale = { x = 2, y = 0.5 },
                    color = {0.75, 0.9, 1, 1},
                },
            },
            {
                type = "RigidBody",
                args = {
                    bodyType = "dynamic",
                    width = 64,
                    height = 8,
                    density = 2.5,
                    friction = 0.3,
                    restitution = 0.1,
                    fixedRotation = true,
                },
            },
            {
                type = "LightCollider",
                args = {
                    dynamic = true,
                    segments = {
                        { a = Vector.new(-32, 0), b = Vector.new(32, 0), reflective = 1.0, absorption = 0 },
                    },
                },
            },
            {
                type = "CollisionRenderer",
                args = {},
            },
        },
    },

    SpinningMirror = {
        components = {
            {
                type = "LightCollider",
                args = {
                    dynamic = true,
                    segments = {
                        { a = Vector.new(-8, -4), b = Vector.new(8, -4), reflective = 1.0, absorption = 0 },
                        { a = Vector.new(-8, -4), b = Vector.new(-8, 4), reflective = 1 },
                        { a = Vector.new(-8, 4), b = Vector.new(8, 4), reflective = 1 },
                        { a = Vector.new(8, -4), b = Vector.new(8, 4), reflective = 1 },
                    },
                },
            },
            {
                type = "Spinner",
                args = {
                    speed = math.pi / 4,
                },
            },
            {
                type = "CollisionRenderer",
                args = {},
            },
            {
                type = "SpriteRenderer",
                args = {
                    path = "Resources/sprites/test/mirror.png",
                    scale = { x = 0.5, y = 0.5 },
                },
            },
        },
    },

    SmallBox = {
        components = {
            {
                type = "SpriteRenderer",
                args = {
                    path = "Resources/sprites/test/box.png",
                    scale = { x = 1, y = 1 },
                },
            },
            {
                type = "RigidBody",
                args = {
                    bodyType = "dynamic",
                    width = 16,
                    height = 16,
                    offset = { x = 0, y = 0 },
                },
            },
            {
                type = "CollisionRenderer",
                args = {},
            },
            {
                type = "LightCollider",
                args = {
                    dynamic = true,
                    segments = {
                        { a = Vector.new(-8, -8), b = Vector.new(8, -8), reflective = 0, refractiveIndex = 1, absorption = 1 },
                        { a = Vector.new(-8, -8), b = Vector.new(-8, 8), reflective = 0, refractiveIndex = 1, absorption = 1 },
                        { a = Vector.new(-8, 8), b = Vector.new(8, 8), reflective = 0, refractiveIndex = 1, absorption = 1 },
                        { a = Vector.new(8, 8), b = Vector.new(8, -8), reflective = 0, refractiveIndex = 1, absorption = 1 },
                    },
                },
            },
        },
    },

    -- SpriteRenderer first: AnimationPlayer looks its target up in OnAttach,
    -- and prefab components attach in declaration order. The renderer needs
    -- no path or frame size -- the clip supplies both on the first frame.
    AnimatedCoin = {
        components = {
            {
                type = "SpriteRenderer",
                args = {
                    scale = { x = 1, y = 1 },
                },
            },
            {
                type = "AnimationPlayer",
                args = {
                    clips = { "CoinSpin" },
                    autoPlay = "CoinSpin",
                },
            },
        },
    },
}
