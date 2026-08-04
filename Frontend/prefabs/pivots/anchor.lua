local Object = require('Libraries.universal.object')
local RigidBody = require('Libraries.physics.rigid_body')

local Anchor = setmetatable({}, { __index = Object })
Anchor.__index = Anchor

function Anchor.new(args)
    args = args or {}
    local self = Object.new(args.position, args.rotation)
    self = setmetatable(self, Anchor)

    self:AddComponent(RigidBody.new({
        bodyType = "static",
        width = args.width or 4,
        height = args.height or 4,
    }))

    return self
end

function Anchor:__tostring()
    return "Anchor"
end

return Anchor
