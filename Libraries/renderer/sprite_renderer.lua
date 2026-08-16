local Component = require('Libraries.universal.component')

local SpriteRenderer = setmetatable({}, { __index = Component })
SpriteRenderer.__index = SpriteRenderer

-- One love Image per path, shared by every renderer that names it. Images are
-- immutable here, so sharing is free, and it means a component that swaps
-- between two sprites (LightDetector lit/unlit, a switch flipping) can do so
-- every frame without reuploading a texture.
--
-- The cache deliberately outlives a level switch, exactly like Clip's -- see
-- clip.lua. Call ClearImages after replacing art on disk.
local imageCache = {}

function SpriteRenderer.Load(path)
    if not path then return nil end
    local image = imageCache[path]
    if not image then
        image = love.graphics.newImage(path)
        imageCache[path] = image
    end
    return image
end

function SpriteRenderer.ClearImages()
    imageCache = {}
end

function SpriteRenderer.new(args)
    args = args or {}
    local self = Component.new()
    self = setmetatable(self, SpriteRenderer)

    self.image = args.image or SpriteRenderer.Load(args.path)
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

-- Swaps the atlas this renderer draws from and rebuilds the quad against the
-- new dimensions. AnimationPlayer calls this every frame, so the no-op case
-- has to be cheap: a quad's reference dimensions are baked in at creation, so
-- a new image means a new quad, but the same image means no work at all.
function SpriteRenderer:SetSheet(image, frameWidth, frameHeight)
    if not image then return end
    if self.image == image
        and self.frameWidth == frameWidth
        and self.frameHeight == frameHeight
        and self.quad then
        return
    end

    self.image = image
    self.frameWidth = frameWidth
    self.frameHeight = frameHeight
    self.quad = love.graphics.newQuad(0, 0, frameWidth, frameHeight, image:getDimensions())
end

-- Swaps the image while keeping the frame layout. This is the two-state
-- sibling of SetSheet: SetSheet is for an animation clip handing over a new
-- atlas *and* a new frame size, this is for a component flipping between two
-- stills of the same shape -- a detector going lit, a switch flipping -- where
-- a one-frame clip each way would be ceremony for nothing.
function SpriteRenderer:SetImage(image)
    if not image or self.image == image then return end

    -- The current cell has to be re-derived: a quad's reference dimensions are
    -- baked in at creation, so a new image always means a new quad, and
    -- rebuilding at 0,0 would silently snap an atlas back to its first frame.
    local col, row = 0, 0
    if self.quad and self.frameWidth and self.frameHeight then
        local viewportX, viewportY = self.quad:getViewport()
        col = math.floor(viewportX / self.frameWidth)
        row = math.floor(viewportY / self.frameHeight)
    end

    self.image = image

    if self.frameWidth and self.frameHeight then
        self.quad = love.graphics.newQuad(
            col * self.frameWidth, row * self.frameHeight,
            self.frameWidth, self.frameHeight,
            image:getDimensions()
        )
    else
        self.quad = nil
    end
end

function SpriteRenderer:SetFrame(col, row)
    if not self.quad then return end
    self.quad:setViewport(col * self.frameWidth, row * self.frameHeight, self.frameWidth, self.frameHeight)
end

function SpriteRenderer:Draw(object)
    if not self.visible or not self.image then return end

    -- World, so a parented sprite follows its parent. The transform's uniform
    -- scale multiplies this component's own per-axis scale rather than
    -- replacing it: one is "how big is this object", the other is "how is this
    -- particular image stretched onto it".
    local x, y, angle, scale = object.transform:World()
    local sx, sy = self.scale.x * scale, self.scale.y * scale
    local ox, oy = x + self.offset.x * scale, y + self.offset.y * scale

    love.graphics.setColor(self.color)
    if self.quad then
        love.graphics.draw(self.image, self.quad, ox, oy, angle, sx, sy,
                           self.frameWidth / 2, self.frameHeight / 2)
    else
        local iw, ih = self.image:getDimensions()
        love.graphics.draw(self.image, ox, oy, angle, sx, sy, iw / 2, ih / 2)
    end
    love.graphics.setColor(1, 1, 1, 1)
end

function SpriteRenderer:__tostring()
    return "SpriteRenderer"
end

return SpriteRenderer
