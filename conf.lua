function love.conf(t)
    local Screen = require('Libraries.renderer.screen')
    local GAME_W, GAME_H = Screen.WIDTH, Screen.HEIGHT

    local isHandheld = (os.getenv("RAY_HANDHELD") == "1")
    local isDesktop  = not isHandheld

    t.identity = "raylight"
    t.version  = "11.4"
    t.console  = true

    t.window.title      = "RAY"
    t.window.width      = isDesktop and GAME_W or GAME_W
    t.window.height     = isDesktop and GAME_H or GAME_H
    t.window.resizable  = isDesktop
    t.window.fullscreen = not isDesktop
    t.window.vsync      = 1
    t.window.msaa       = 0
    t.window.highdpi    = false

    -- video/touch: unused by the game. Off on principle; on the handheld
    -- each one is startup time and resident memory for nothing.
    t.modules.video   = false
    t.modules.touch   = false
end
