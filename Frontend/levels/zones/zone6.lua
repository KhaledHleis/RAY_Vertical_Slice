local Vector = require('Libraries.transform.vector')
return {
    { id = "emitter",  prefab = "Emitter",             position = Vector.new(50, 150) },
    { id = "wall",     prefab = "PartialMirrorDiag1",  position = Vector.new(300, 150) },
    { id = "detector", prefab = "DetectorHoriz",       position = Vector.new(300, 310) },
}
