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
                    path = "Resources/sprites/physics_objects/box.png",
                    scale = { x = 2, y = 2 },
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
    Player = {
        components = {
            {
                type = "RigidBody",
                args = {
                    bodyType = "dynamic",
                    width = 32,
                    height = 32,
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
                args = {
                    animations = {
                        idle = "PlayerIdle",
                        run = "PlayerRun",
                        jump = "PlayerJump",
                        fall = "PlayerFall",
                    },
                },
            },
            {
                type = "AnimationPlayer",
                args = {
                    target = "PlayerRenderer",
                },
            },
            {
                type = "LightCollider",
                args = {
                    dynamic = true,
                    segments = {
                        { a = Vector.new(-16, -16), b = Vector.new(16, -16), absorption = 1 },
                        { a = Vector.new(16, -16), b = Vector.new(16, 16), absorption = 1 },
                        { a = Vector.new(16, 16), b = Vector.new(-16, 16), absorption = 1 },
                        { a = Vector.new(-16, 16), b = Vector.new(-16, -16), absorption = 1 },
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
                    path = "Resources/sprites/physics_objects/mirror.png",
                    scale = { x = 1, y = 1 },
                    color = {1, 1, 1, 1},
                },
            },
            {
                type = "RigidBody",
                args = {
                    bodyType = "dynamic",
                    width = 32,
                    height = 32,
                    offset = { x = 0, y = 0 },
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
                        { a = Vector.new(-7, -10), b = Vector.new(14, 10), reflective = 1.0, absorption = 0 },
                        { a = Vector.new(-16, 16), b = Vector.new(-16, -16), reflective = 0, absorption = 1 },
                        { a = Vector.new(16, 16), b = Vector.new(-16, 16), reflective = 0, absorption = 1 },
                        { a = Vector.new(16, 16), b = Vector.new(14, 10), reflective = 0, absorption = 1 },
                        { a = Vector.new(-16, -16), b = Vector.new(-7, -10), reflective = 0, absorption = 1 },
                    },
                },
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
                    path = "Resources/sprites/physics_objects/box.png",
                    offset = { x = 0, y = 0 },
                    scale = { x = 0.5, y = 0.5 },
                },
            },
            {
                type = "RigidBody",
                args = {
                    bodyType = "dynamic",
                    width = 16,
                    height = 16,
                    offset = { x = 0, y = 0 },
                    friction = 0.3,
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

    -- Scenery only. The grid draws as one SpriteBatch and registers nothing
    -- with the physics world or LightWorld -- put RigidBody and LightCollider
    -- objects over the tiles by hand, which is what makes a wall a wall.
    --
    -- Everything here is a placeholder: the tileset, the map size and the tile
    -- data all arrive as per-instance overrides from the level editor, because
    -- two rooms sharing one prefab must not share one grid.
    Tilemap = {
        components = {
            {
                type = "Tilemap",
                args = {
                    tileWidth = 16,
                    tileHeight = 16,
                    width = 0,
                    height = 0,
                    tiles = {},
                },
            },
        },
    },

    switch = {
        components = {
            {
                type = "SpriteRenderer",
                args = {
                    path = "Resources/sprites/switch/switch_up.png",
                },
            },
        },
    },

    invisible_collider = {
        components = {
            {
                type = "RigidBody",
                args = {},
            },
        },
    },

    barrel = {
        components = {
            {
                type = "SpriteRenderer",
                args = {
                    path = "Resources/craftpix/3 Objects/Barrel/2.png",
                },
            },
            {
                type = "RigidBody",
                args = {
                    width = 22,
                    height = 25,
                    offset = { x = 0, y = 0 },
                },
            },
            {
                type = "LightCollider",
                args = {
                    dynamic = true,
                    segments = {
                        { a = Vector.new(-11, -9), b = Vector.new(-3, -13), reflective = 0, absorption = 1 },
                        { a = Vector.new(-11, -9), b = Vector.new(-10, 13), reflective = 0, absorption = 1 },
                        { a = Vector.new(-10, 13), b = Vector.new(11, 13), reflective = 0, absorption = 1 },
                        { a = Vector.new(10, -10), b = Vector.new(11, 13), reflective = 0, absorption = 1 },
                        { a = Vector.new(10, -10), b = Vector.new(7, -13), reflective = 0, absorption = 1 },
                        { a = Vector.new(7, -13), b = Vector.new(-3, -13), reflective = 0, absorption = 1 },
                    },
                },
            },
        },
    },

    -- SpriteRenderer first: LightDetector resolves it by name in OnAttach to
    -- swap the lens between its dark and lit states, the same ordering rule
    -- AnimationPlayer follows.
    detector = {
        components = {
            {
                type = "SpriteRenderer",
                args = {
                    path = "Resources/sprites/detector/detector_off.png",
                    color = {1, 1, 1, 1},
                },
            },
            {
                type = "LightCollider",
                args = {
                    segments = {
                        { a = Vector.new(-4, -12), b = Vector.new(4, -12), reflective = 0, absorption = 1 },
                        { a = Vector.new(-13, -3), b = Vector.new(-4, -12), reflective = 0, absorption = 1 },
                        { a = Vector.new(-13, 3), b = Vector.new(-13, -3), reflective = 0, absorption = 1 },
                        { a = Vector.new(-5, 12), b = Vector.new(-13, 3), reflective = 0, absorption = 1 },
                        { a = Vector.new(4, 12), b = Vector.new(-5, 12), reflective = 0, absorption = 1 },
                        { a = Vector.new(4, 12), b = Vector.new(12, 3), reflective = 0, absorption = 1 },
                        { a = Vector.new(12, -3), b = Vector.new(12, 3), reflective = 0, absorption = 1 },
                        { a = Vector.new(12, -3), b = Vector.new(4, -12), reflective = 0, absorption = 1 },
                    },
                },
            },
            {
                type = "LightDetector",
                args = {
                    litSprite = "Resources/sprites/detector/detector_on.png",
                    unlitSprite = "Resources/sprites/detector/detector_off.png",
                },
            },
        },
    },

    -- Opens when any detector lights up (no channel = listen to all of them),
    -- and hands the level over once the player walks into the open doorway.
    --
    -- Order is load-bearing twice over: AnimationPlayer needs the
    -- SpriteRenderer to already exist, and Door needs the AnimationPlayer.
    --
    -- The RigidBody is a sensor, so it is a doorway rather than a wall -- the
    -- player walks straight through it and Box2D just reports the overlap. It
    -- is deliberately narrower and shorter than the 64x64 sprite: the trigger
    -- should be the gap you step into, not the frame around it.
    door = {
        components = {
            {
                type = "SpriteRenderer",
                args = {
                    path = "Resources/sprites/door/door.png",
                    frameWidth = 64,
                    frameHeight = 64,
                },
            },
            {
                type = "AnimationPlayer",
                args = {
                    clips = { "DoorOpen", "DoorClose" },
                },
            },
            {
                type = "RigidBody",
                args = {
                    bodyType = "static",
                    sensor = true,
                    width = 28,
                    height = 56,
                },
            },
            {
                type = "Door",
                args = {
                    openClip = "DoorOpen",
                    closeClip = "DoorClose",
                    nextLevel = "Frontend.levels.level_complete",
                },
            },
        },
    },
}
