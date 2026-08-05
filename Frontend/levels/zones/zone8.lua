local Vector = require('Libraries.transform.vector')
return {
    { id = "emitter", prefab = "Emitter",     position = Vector.new(50, 150) },
    { id = "mirrorA", prefab = "MirrorDiag2", position = Vector.new(265, 150) },
    { id = "mirrorB", prefab = "MirrorDiag1", position = Vector.new(335, 150) },
}
