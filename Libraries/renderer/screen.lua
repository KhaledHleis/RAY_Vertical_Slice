local Screen = {}
Screen.WIDTH = 320
Screen.HEIGHT = 240

local canvas = nil
local scale = 1

function Screen.init()
    canvas = love.graphics.newCanvas(Screen.WIDTH, Screen.HEIGHT)
    canvas:setFilter("nearest", "nearest")
    Screen.updateScale()
end

function Screen.updateScale()
    local w, h = love.graphics.getDimensions()
    scale = math.max(1, math.floor(math.min(w / Screen.WIDTH, h / Screen.HEIGHT)))
end

function Screen.beginDraw()
    love.graphics.setCanvas(canvas)
    love.graphics.clear()
end

function Screen.endDraw()
    love.graphics.setCanvas()
    local w, h = love.graphics.getDimensions()
    local x = math.floor((w - Screen.WIDTH * scale) / 2)
    local y = math.floor((h - Screen.HEIGHT * scale) / 2)
    love.graphics.draw(canvas, x, y, 0, scale, scale)
end

return Screen
