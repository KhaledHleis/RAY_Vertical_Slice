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
        }}
    }
}
