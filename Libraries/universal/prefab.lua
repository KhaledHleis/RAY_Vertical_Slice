local Object = require('Libraries.universal.object')
local ComponentRegistry = require('Libraries.universal.component_registry')

local Prefab = {}
local definitions = {}

function Prefab.Register(defs)
    for name, def in pairs(defs) do
        definitions[name] = def
    end
end

local function mergeArgs(base, override)
    local result = {}
    for k, v in pairs(base or {}) do result[k] = v end
    for k, v in pairs(override or {}) do result[k] = v end
    return result
end

function Prefab.Instantiate(name, overrides)
    overrides = overrides or {}
    local def = definitions[name]
    assert(def, "Prefab.Instantiate: unknown prefab '" .. tostring(name) .. "'")

    local object = Object.new(overrides.position, overrides.rotation)
    object.prefab = name

    local componentOverrides = overrides.components or {}

    for _, compDef in ipairs(def.components or {}) do
        local ComponentClass = ComponentRegistry[compDef.type]
        assert(ComponentClass, "Prefab.Instantiate: unknown component type '" .. tostring(compDef.type) .. "'")
        local args = mergeArgs(compDef.args, componentOverrides[compDef.type])
        object:AddComponent(ComponentClass.new(args))
    end

    return object
end

return Prefab
