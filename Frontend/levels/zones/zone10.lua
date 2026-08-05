local Vector = require('Libraries.transform.vector')
return {
    { id = "emitter",  prefab = "FanEmitter",       position = Vector.new(50, 150) },
    { id = "mirror",   prefab = "MirrorDiag2",      position = Vector.new(400, 90) },
    { id = "absorber", prefab = "AbsorberVertical", position = Vector.new(450, 150) },
    { id = "glass",    prefab = "GlassFaceVertical",position = Vector.new(400, 230) },
}
