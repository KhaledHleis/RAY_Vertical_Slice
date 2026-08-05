local Vector = require('Libraries.transform.vector')
return {
    { id = "emitter",  prefab = "Emitter",     position = Vector.new(50, 150) },
    { id = "mirrorA",  prefab = "MirrorDiag1", position = Vector.new(300, 150) },
    { id = "mirrorB",  prefab = "MirrorDiag1", position = Vector.new(300, 310) },
    { id = "detector", prefab = "Detector",    position = Vector.new(460, 310) },
}
