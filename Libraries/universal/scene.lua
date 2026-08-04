local Scene = {}
Scene.__index = Scene

function Scene.new()
    local self = setmetatable({}, Scene)
    self.objects = {}
    self.pendingDestroy = {}
    return self
end

function Scene:Spawn(object)
    table.insert(self.objects, object)
    return object
end

function Scene:Destroy(object)
    table.insert(self.pendingDestroy, object)
end

function Scene:Update(dt)
    for _, object in ipairs(self.objects) do
        object:Update(dt)
    end
    self:_flushDestroyed()
end

function Scene:Draw()
    for _, object in ipairs(self.objects) do
        object:Draw()
    end
end

function Scene:_flushDestroyed()
    if #self.pendingDestroy == 0 then return end

    for _, object in ipairs(self.pendingDestroy) do
        object:Destroy()
        for i = #self.objects, 1, -1 do
            if self.objects[i] == object then
                table.remove(self.objects, i)
                break
            end
        end
    end

    self.pendingDestroy = {}
end

return Scene
