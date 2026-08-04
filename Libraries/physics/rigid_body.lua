local RigidBody = {}
RigidBody.__index = RigidBody

function RigidBody.new(args)
    local self = setmetatable({}, RigidBody)
    
    return self
end

function RigidBody:__tostring()
    return "RigidBody"
end

return RigidBody