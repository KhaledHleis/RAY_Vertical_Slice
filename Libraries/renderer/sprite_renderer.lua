local SpriteRenderer = {}
SpriteRenderer.__index = SpriteRenderer

function SpriteRenderer.new(args)
    local self = setmetatable({}, SpriteRenderer)
    
    return self
end

function SpriteRenderer:__tostring()
    return "SpriteRenderer"
end

return SpriteRenderer