local Vector = require('Libraries.transform.vector')
return {
    { id = "emitter", prefab = "Emitter",        position = Vector.new(50, 150), rotation = math.rad(2) },
    { id = "mirror",  prefab = "MirrorFlatHoriz", position = Vector.new(500, 165.7) },
}
