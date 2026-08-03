function love.conf(t)
    local GAME_W, GAME_H = 320, 240


    local isHandheld = (os.getenv("RAY_HANDHELD") == "1")
    local isDesktop  = not isHandheld

    t.identity = "raylight"
    t.version  = "11.4"
    t.console  = false

    t.window.title      = "RAY"
    t.window.width      = isDesktop and GAME_W * 3 or GAME_W
    t.window.height     = isDesktop and GAME_H * 3 or GAME_H
    t.window.resizable  = isDesktop
    t.window.fullscreen = not isDesktop
    t.window.vsync      = 1
    t.window.msaa       = 0
    t.window.highdpi    = false

    -- Modules the game never touches. Off on principle: on the handheld each
    -- one is startup time and resident memory for nothing.
    t.modules.physics = false
    t.modules.video   = false
    t.modules.touch   = false
end
