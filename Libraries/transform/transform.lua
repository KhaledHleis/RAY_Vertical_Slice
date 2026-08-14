
-- Position, rotation and uniform scale, optionally parented to another
-- transform.
--
--
-- position, rotation and scale are LOCAL to the parent. For an unparented
-- transform -- which is every object in the game until someone sets a parent
-- -- local and world are identical, so existing code that reads
-- `transform.position` directly is still correct.
--
-- The number-returning accessors (World, TransformPoint) exist because they
-- run per object per frame and allocate nothing. WorldPosition returns a
-- Vector for convenience; prefer World() in a draw path.

local Vector = require('Libraries.transform.vector')
local Rotation = require('Libraries.transform.rotation')

local Transform = {}
Transform.__index = Transform

function Transform.new(position, rotation, scale)
    local self = setmetatable({}, Transform)
    self.position = position or Vector.new(0, 0)
    self.rotation = Rotation.new(rotation or 0)
    self.scale = scale or 1
    self.parent = nil
    self.children = {}
    -- Set by Object.new so a hierarchy walk can get back to the objects.
    self.object = nil
    return self
end

--------------------------------------------------------------- composition

-- Returns x, y, angle, scale in world space. One walk, four numbers, no
-- allocation. Recursion depth is hierarchy depth.
function Transform:World()
    local parent = self.parent
    if not parent then
        return self.position.x, self.position.y, self.rotation.angle, self.scale
    end

    local px, py, pa, ps = parent:World()
    local c, s = math.cos(pa), math.sin(pa)
    local lx, ly = self.position.x * ps, self.position.y * ps

    return px + lx * c - ly * s,
           py + lx * s + ly * c,
           pa + self.rotation.angle,
           ps * self.scale
end

function Transform:WorldPosition()
    local x, y = self:World()
    return Vector.new(x, y)
end

function Transform:WorldAngle()
    local _, _, angle = self:World()
    return angle
end

function Transform:WorldScale()
    local _, _, _, scale = self:World()
    return scale
end

-- Local space -> world space. Takes and returns plain numbers; LightCollider
-- calls this for every segment endpoint every frame.
function Transform:TransformPoint(x, y)
    local wx, wy, wa, ws = self:World()
    local c, s = math.cos(wa), math.sin(wa)
    local sx, sy = x * ws, y * ws
    return wx + sx * c - sy * s, wy + sx * s + sy * c
end

-- World space -> local space. The inverse of TransformPoint.
function Transform:InverseTransformPoint(x, y)
    local wx, wy, wa, ws = self:World()
    local c, s = math.cos(-wa), math.sin(-wa)
    local dx, dy = x - wx, y - wy
    return (dx * c - dy * s) / ws, (dx * s + dy * c) / ws
end

------------------------------------------------------------------ hierarchy

function Transform:IsDescendantOf(other)
    local node = self.parent
    while node do
        if node == other then return true end
        node = node.parent
    end
    return false
end

-- Reparents, keeping the LOCAL transform. The object therefore moves in world
-- space to wherever the new parent puts it, which is the predictable default;
--
-- The RigidBody rule is enforced one level up, in Object:SetParent
function Transform:SetParent(parent)
    assert(parent ~= self, "Transform:SetParent: cannot parent a transform to itself")
    assert(not (parent and parent:IsDescendantOf(self)),
        "Transform:SetParent: that would make a cycle")

    local old = self.parent
    if old then
        for i = #old.children, 1, -1 do
            if old.children[i] == self then
                table.remove(old.children, i)
                break
            end
        end
    end

    self.parent = parent
    if parent then table.insert(parent.children, self) end
end

function Transform:__tostring()
    return "Transform: " .. tostring(self.position) .. " \n " .. tostring(self.rotation)
end

return Transform
