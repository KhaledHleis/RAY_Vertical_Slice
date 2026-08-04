local Component = require('Libraries.universal.component')

local SpriteRenderer = setmetatable({}, { __index = Component })
SpriteRenderer.__index = SpriteRenderer

function SpriteRenderer.new(args)
    args = args or {}
    local self = Component.new()
    self = setmetatable(self, SpriteRenderer)

    self.image = args.image or (args.path and love.graphics.newImage(args.path))
    self.offset = args.offset or { x = 0, y = 0 }
    self.scale = args.scale or { x = 1, y = 1 }
    self.color = args.color or { 1, 1, 1, 1 }
    self.visible = true

    self.frameWidth = args.frameWidth
    self.frameHeight = args.frameHeight
    self.quad = args.quad

    if not self.quad and self.frameWidth and self.frameHeight and self.image then
        local frameX = args.frameX or 0
        local frameY = args.frameY or 0
        self.quad = love.graphics.newQuad(
            frameX * self.frameWidth, frameY * self.frameHeight,
            self.frameWidth, self.frameHeight,
            self.image:getDimensions()
        )
    end

    return self
end

function SpriteRenderer:SetFrame(col, row)
    if not self.quad then return end
    self.quad:setViewport(col * self.frameWidth, row * self.frameHeight, self.frameWidth, self.frameHeight)
end

function SpriteRenderer:Draw(object)
    if not self.visible or not self.image then return end

    local pos = object.transform.position
    local angle = object.transform.rotation and object.transform.rotation.angle or 0

    love.graphics.setColor(self.color)
    if self.quad then
        love.graphics.draw(self.image, self.quad, pos.x + self.offset.x, pos.y + self.offset.y, angle, self.scale.x, self.scale.y)
    else
        love.graphics.draw(self.image, pos.x + self.offset.x, pos.y + self.offset.y, angle, self.scale.x, self.scale.y)
    end
    love.graphics.setColor(1, 1, 1, 1)
end

function SpriteRenderer:__tostring()
    return "SpriteRenderer"
end

return SpriteRenderer
