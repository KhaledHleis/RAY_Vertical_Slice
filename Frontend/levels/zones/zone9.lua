local Vector = require('Libraries.transform.vector')
-- Scaffold for when LightCollider recomputes worldSegments from the live
-- transform each frame. Right now the mirror's segments are frozen at
-- OnAttach, so this will read lit=false regardless of the hinge/physics.
return {
    { id = "emitter",  prefab = "Emitter",     position = Vector.new(50, 150) },
    { id = "anchor",   prefab = "Anchor",      position = Vector.new(300, 130) },
    { id = "mirror",   prefab = "HingeMirror", position = Vector.new(300, 150),
        extraComponents = { { type = "HingeJoint", args = { connectedObjectId = "anchor", anchor = { x = 300, y = 130 } } } } },
    { id = "detector", prefab = "DetectorHoriz", position = Vector.new(300, 310) },
}
