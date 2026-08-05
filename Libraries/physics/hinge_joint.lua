local World = require('Libraries.physics.world')
local Component = require('Libraries.universal.component')

local HingeJoint = setmetatable({}, { __index = Component })
HingeJoint.__index = HingeJoint

function HingeJoint.new(args)
    args = args or {}
    local self = Component.new()
    self = setmetatable(self, HingeJoint)

    self.connectedObject = args.connectedObject
    self.anchor = args.anchor
    self.enableLimit = args.enableLimit or false
    self.lowerAngle = args.lowerAngle or 0
    self.upperAngle = args.upperAngle or 0
    self.enableMotor = args.enableMotor or false
    self.motorSpeed = args.motorSpeed or 0
    self.maxMotorTorque = args.maxMotorTorque or 0

    self.joint = nil

    return self
end

function HingeJoint:OnAttach(object)
    local bodyA = self.connectedObject:GetComponent("RigidBody")
    local bodyB = object:GetComponent("RigidBody")
    assert(bodyA and bodyA.body, "HingeJoint: connectedObject needs a RigidBody attached first")
    assert(bodyB and bodyB.body, "HingeJoint: owning object needs a RigidBody attached before HingeJoint")

    local anchor = World.toMeters(self.anchor)
    self.joint = love.physics.newRevoluteJoint(bodyA.body, bodyB.body, anchor.x, anchor.y, anchor.x, anchor.y, false)

    if self.enableLimit then
        self.joint:setLimits(self.lowerAngle, self.upperAngle)
        self.joint:setLimitsEnabled(true)
    end

    if self.enableMotor then
        self.joint:setMotorSpeed(self.motorSpeed)
        self.joint:setMaxMotorTorque(self.maxMotorTorque)
        self.joint:setMotorEnabled(true)
    end
end

function HingeJoint:OnDestroy(object)
    if self.joint and not self.joint:isDestroyed() then
        self.joint:destroy()
    end
end

function HingeJoint:__tostring()
    return "HingeJoint"
end

return HingeJoint
