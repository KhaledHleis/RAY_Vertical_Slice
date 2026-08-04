return {
    Box = {
        components = {
            { type = "SpriteRenderer", args = { path = "Resources/sprites/test/box.png", scale = { x = 4, y = 4 } } },
            { type = "RigidBody", args = { bodyType = "dynamic", width = 64, height = 64 } },
        },
    },

    Anchor = {
        components = {
            { type = "RigidBody", args = { bodyType = "static", width = 4, height = 4 } },
        },
    },
}
