local Vector = require('Libraries.transform.vector')
local Prefab = require('Libraries.universal.prefab')
local ComponentRegistry = require('Libraries.universal.component_registry')

local Level = {}

local function toVector(v)
    if not v then return nil end
    return Vector.new(v.x or 0, v.y or 0)
end

function Level.load(modulePath, scene)
    local defs = require(modulePath)
    local objectsById = {}
    local instances = {}

    for _, entry in ipairs(defs) do
        local object = Prefab.Instantiate(entry.prefab, {
            position = toVector(entry.position),
            rotation = entry.rotation,
            scale = entry.scale,
            components = entry.components,
        })

        scene:Spawn(object)
        if entry.id then objectsById[entry.id] = object end
        table.insert(instances, { object = object, def = entry })
    end

    -- Parenting resolves here, in the same second pass as connectedObjectId,
    -- so a parent may appear anywhere in the file relative to its children.
    --
    -- `position`, `rotation` and `scale` on a parented entry are LOCAL to the
    -- parent, matching what Unity's inspector shows. They were applied as-is
    -- during the first pass, which is exactly right: setting the parent here
    -- keeps the local transform and lets the world position fall out of it.
    for _, instance in ipairs(instances) do
        local parentId = instance.def.parent
        if parentId then
            local parent = objectsById[parentId]
            assert(parent, "Level.load: unknown parent id '" .. tostring(parentId)
                .. "' on '" .. tostring(instance.def.id or instance.def.prefab) .. "'")
            -- Object:SetParent carries the RigidBody assert and the cycle check.
            instance.object:SetParent(parent)
        end
    end

    for _, instance in ipairs(instances) do
        for _, compDef in ipairs(instance.def.extraComponents or {}) do
            local args = {}
            for k, v in pairs(compDef.args or {}) do args[k] = v end

            if args.connectedObjectId then
                args.connectedObject = objectsById[args.connectedObjectId]
                assert(args.connectedObject, "Level.load: unknown connectedObjectId '" .. tostring(args.connectedObjectId) .. "'")
                args.connectedObjectId = nil
            end

            if args.anchor then
                args.anchor = toVector(args.anchor)
            end

            local ComponentClass = ComponentRegistry[compDef.type]
            assert(ComponentClass, "Level.load: unknown component type '" .. tostring(compDef.type) .. "'")
            instance.object:AddComponent(ComponentClass.new(args))
        end
    end

    return objectsById
end

return Level
