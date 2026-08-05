local Vector = require('Libraries.transform.vector')
return {
    { id = "emitter",  prefab = "Emitter",           position = Vector.new(50, 150) },
    { id = "wall",     prefab = "AbsorberVertical",  position = Vector.new(300, 150) },
    { id = "detector", prefab = "Detector",          position = Vector.new(400, 150) },
}
