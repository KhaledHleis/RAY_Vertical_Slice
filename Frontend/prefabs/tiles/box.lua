local Object = require('Libraries.universal.object')
local SpriteRenderer = require('Libraries.renderer.sprite_renderer')
local RigidBody = require('Libraries.physics.rigid_body')

local Box = setmetatable({}, { __index = Object })
Box.__index = Box

function Box.new(args)
    args = args or {}
    local self = Object.new(args.position, args.rotation)
    self = setmetatable(self, Box)

    local sprite = args.sprite or {}
    self:AddComponent(SpriteRenderer.new({
        path = sprite.path or "Resources/sprites/test/box.png",
        scale = sprite.scale or { x = 4, y = 4 },
        offset = sprite.offset,
        color = sprite.color,
    }))

    local rigidBody = args.rigidBody or {}
    self:AddComponent(RigidBody.new({
        bodyType = rigidBody.bodyType or "dynamic",
        width = rigidBody.width or 64,
        height = rigidBody.height or 64,
        density = rigidBody.density,
        friction = rigidBody.friction,
        restitution = rigidBody.restitution,
        fixedRotation = rigidBody.fixedRotation,
    }))

    return self
end

function Box:__tostring()
    return "Box"
end

return Box
