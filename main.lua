local Object = require('Libraries.universal.Object')
local Vector = require('Libraries.transform.vector')
local Box = require('Frontend.prefabs.tiles.box')

function love.load()
    love.graphics.setDefaultFilter("nearest", "nearest")
    love.graphics.setLineStyle("rough")
    
    
end


function love.update(dt)
    
end

function love.draw()
end

function love.keypressed(key, scancode, isrepeat)
    if key == "escape" then print("quit game"); love.event.quit() end
end

function love.gamepadpressed(joystick, button)
    
end

function love.resize(w, h)
    
end