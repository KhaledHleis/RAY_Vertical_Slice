local Vector = require('Libraries.transform.vector')
return {
    { id = "boxtop",    prefab = "MirrorFlatHoriz", position = Vector.new(300, 90) },
    { id = "boxbottom", prefab = "MirrorFlatHoriz", position = Vector.new(300, 190) },
    { id = "emitter",   prefab = "FanEmitter",      position = Vector.new(300, 140) },
}
