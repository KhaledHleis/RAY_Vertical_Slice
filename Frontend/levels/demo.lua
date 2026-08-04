local Vector = require('Libraries.transform.vector')

return {{
    id = "floor",
    prefab = "Box",
    position = {
        x = 160,
        y = 220
    },
    components = {
        SpriteRenderer = {
            scale = {
                x = 20,
                y = 1
            }
        },
        RigidBody = {
            bodyType = "static",
            width = 320,
            height = 16
        }
    }
}, {
    id = "box",
    prefab = "Box",
    position = {
        x = 150,
        y = 20
    },
    components = {
        RigidBody = {
            restitution = 0.3
        }
    }
}, {
    id = "ceiling",
    prefab = "Anchor",
    position = {
        x = 260,
        y = 20
    }
}, {
    id = "lamp",
    prefab = "Box",
    position = {
        x = 300,
        y = 60
    },
    extraComponents = {{
        type = "HingeJoint",
        args = {
            connectedObjectId = "ceiling",
            anchor = {
                x = 260,
                y = 20
            }
        }
    }}
}, {
    prefab = "LightCone",
    position = Vector.new(100, 100),
    rotation = math.pi / 2
}, {
    prefab = "LightWall",
    position = Vector.new(100, 250)
}}
