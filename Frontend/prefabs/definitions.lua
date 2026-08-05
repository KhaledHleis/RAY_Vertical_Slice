local Vector = require('Libraries.transform.vector')
local math = require('math')
return {
    Box = {
        components = {{
            type = "SpriteRenderer",
            args = {
                path = "Resources/sprites/test/box.png",
                scale = {
                    x = 4,
                    y = 4
                }
            }
        }, {
            type = "RigidBody",
            args = {
                bodyType = "dynamic",
                width = 64,
                height = 64
            }
        }, {
            type = "CollisionRenderer",
            args = {}
        }}
    },

    Anchor = {
        components = {{
            type = "RigidBody",
            args = {
                bodyType = "static",
                width = 4,
                height = 4
            }
        }, {
            type = "CollisionRenderer",
            args = {}
        }}
    },

    LightCone = {
        components = {{
            type = "LightSource",
            args = {
                rayCount = 32,
                coneAngle = math.pi / 3,
                maxDepth = 4
            }
        }, {
            type = "GodrayRenderer",
            args = {}
        }}
    },

    LightWall = {
        components = {{
            type = "LightCollider",
            args = {
                segments = {{
                    a = Vector.new(-32, 0),
                    b = Vector.new(32, 0),
                    reflective = 0.6,
                    absorption = 0.1
                }}
            }
        }, {
            type = "CollisionRenderer",
            args = {}
        }}
    },

    -- A physical mirror: falls under gravity and collides like any other
    -- RigidBody, while its LightCollider surface is fully reflective and
    -- stays glued to it every frame (dynamic = true) so it keeps bouncing
    -- light correctly as it moves.
    Mirror = {
        components = {{
            type = "SpriteRenderer",
            args = {
                path = "Resources/sprites/test/mirror.png",
                scale = {
                    x = 2,
                    y = 0.5
                },
                color = {0.75, 0.9, 1, 1}
            }
        }, {
            type = "RigidBody",
            args = {
                bodyType = "dynamic",
                width = 64,
                height = 8,
                density = 2.5,
                friction = 0.3,
                restitution = 0.1,
                fixedRotation = true
            }
        }, {
            type = "LightCollider",
            args = {
                dynamic = true,
                segments = {{
                    a = Vector.new(-32, 0),
                    b = Vector.new(32, 0),
                    reflective = 1.0,
                    absorption = 0
                }}
            }
        }, {
            type = "CollisionRenderer",
            args = {}
        }}
    }
}
