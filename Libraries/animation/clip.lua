-- clip.lua
--
-- An animation clip is *data*, not a component -- the same relationship a
-- Unity AnimationClip has to an Animator. A clip knows which sheet it lives
-- on, which cells it walks through, how long each cell lasts and what events
-- fire on the way. It knows nothing about who is playing it, which is what
-- lets an Animator or an AnimationTree reuse the exact same tables later.
--
-- Clips are registered by name, like prefabs:
--
--   local Clip = require('Libraries.animation.clip')
--   Clip.Register(require('Frontend.animations.definitions'))
--
-- and referenced by name from component args, so a prefab stays serializable
-- by the PyQt editor (a list of strings, not a nested animation table).
--
-- A definition looks like:
--
--   CoinSpin = {
--       path        = "Resources/sprites/test/coin.png",
--       frameWidth  = 16,          -- optional, see below
--       frameHeight = 16,          -- optional, defaults to the image height
--       fps         = 10,
--       mode        = "loop",      -- "loop" | "once" | "pingpong"
--       frames      = { 0, 1, 2, 3 },
--       durations   = { 0.3, 0.1, 0.1, 0.1 },      -- optional, per frame
--       events      = { { at = 1, name = "coin:glint" } },
--   }
--
-- `frames` accepts three shapes:
--
--   * a flat list of cell indices, counted left-to-right then wrapping down
--     the sheet -- the usual case;
--   * a list of { col, row } pairs (or { col = , row = }) for sheets whose
--     rows are not uniform;
--   * no `frames` at all, plus `row` and `count`, which walks `count` cells
--     along one row starting at `first` (default 0).
--
-- Frame *cells* are 0-based, matching SpriteRenderer's frameX/frameY. Event
-- `at` is a 1-based position in the clip's own frame list, matching every
-- other Lua index -- deliberately a different word so the two never get
-- confused. An event fires the moment its frame is entered, including the
-- frame a clip starts on.
--
-- Nothing here touches love until Clip.Resolve is called, so definitions can
-- be registered and inspected outside the game (tests, tools).

local Clip = {}

local definitions = {}   -- name -> raw definition table
local resolved    = {}   -- name -> normalized clip
local imageCache  = {}   -- path -> love Image

-- Indirection so tests (and any future asset manager) can supply images
-- without love.graphics existing.
function Clip.loadImage(path)
    local image = imageCache[path]
    if not image then
        image = love.graphics.newImage(path)
        imageCache[path] = image
    end
    return image
end

local function fail(name, message)
    error(("Clip '%s': %s"):format(tostring(name), message), 3)
end

-- Registers a table of name -> definition. Re-registering a name replaces it
-- and drops the cached resolution, which is all a hot reload needs.
function Clip.Register(defs)
    assert(type(defs) == "table", "Clip.Register: expected a table of definitions")
    for name, def in pairs(defs) do
        assert(type(def) == "table", "Clip.Register: definition '" .. tostring(name) .. "' is not a table")
        definitions[name] = def
        resolved[name] = nil
    end
end

function Clip.Has(name)
    return definitions[name] ~= nil
end

function Clip.Names()
    local names = {}
    for name in pairs(definitions) do names[#names + 1] = name end
    table.sort(names)
    return names
end

-- Drops every cached resolution (not the definitions). Call after swapping
-- art on disk; the next Resolve rebuilds quads against the new dimensions.
function Clip.Reload()
    resolved = {}
    imageCache = {}
end

-- Test hook: forget everything.
function Clip.Clear()
    definitions, resolved, imageCache = {}, {}, {}
end

local function buildFrames(name, def, columns)
    local frames = {}

    if def.frames then
        for i, entry in ipairs(def.frames) do
            if type(entry) == "number" then
                if columns < 1 then
                    fail(name, "cannot map flat frame indices: the sheet is narrower than one frame")
                end
                frames[i] = { col = entry % columns, row = math.floor(entry / columns) }
            elseif type(entry) == "table" then
                frames[i] = { col = entry.col or entry[1] or 0, row = entry.row or entry[2] or 0 }
            else
                fail(name, "frame " .. i .. " is a " .. type(entry) .. "; expected a number or a { col, row } pair")
            end
        end
    else
        local count = def.count or 1
        local first = def.first or 0
        local row   = def.row or 0
        for i = 1, count do
            frames[i] = { col = first + i - 1, row = row }
        end
    end

    if #frames == 0 then
        fail(name, "has no frames")
    end
    return frames
end

local function buildEvents(name, def, frameCount)
    if not def.events then return nil, nil end

    local events, byFrame = {}, {}
    for i, event in ipairs(def.events) do
        local at = event.at or event.frame
        local eventName = event.name or event[1]
        if type(at) ~= "number" then
            fail(name, "event " .. i .. " has no `at` (1-based position in the frame list)")
        end
        if at < 1 or at > frameCount then
            fail(name, ("event %d fires at frame %d, but the clip only has %d frames")
                :format(i, at, frameCount))
        end
        if type(eventName) ~= "string" then
            fail(name, "event " .. i .. " has no `name`")
        end
        events[i] = { at = at, name = eventName }
        byFrame[at] = byFrame[at] or {}
        table.insert(byFrame[at], eventName)
    end
    return events, byFrame
end

-- Returns the normalized clip for `name`, building it on first use. Raises if
-- the clip is unknown or malformed -- a silently missing animation is much
-- harder to notice than a crash on load.
function Clip.Resolve(name)
    local clip = resolved[name]
    if clip then return clip end

    local def = definitions[name]
    if not def then
        error("Clip.Resolve: unknown clip '" .. tostring(name) .. "'. Registered: "
            .. table.concat(Clip.Names(), ", "), 2)
    end

    local image = def.image
    if not image and def.path then image = Clip.loadImage(def.path) end
    if not image then fail(name, "needs a `path` or an `image`") end

    local imageWidth, imageHeight = image:getDimensions()

    -- A single-row strip of square frames is the common case and needs no
    -- frame size at all: the height is the frame height, and square is the
    -- overwhelmingly likely intent.
    local frameHeight = def.frameHeight or imageHeight
    local frameWidth  = def.frameWidth or frameHeight
    if frameWidth <= 0 or frameHeight <= 0 then
        fail(name, "frame size must be positive")
    end

    local columns = math.floor(imageWidth / frameWidth)
    local frames = buildFrames(name, def, columns)
    local events, eventsByFrame = buildEvents(name, def, #frames)

    local mode = def.mode
    if not mode then
        mode = (def.loop == false) and "once" or "loop"
    end
    if mode ~= "loop" and mode ~= "once" and mode ~= "pingpong" then
        fail(name, "unknown mode '" .. tostring(mode) .. "'; expected loop, once or pingpong")
    end

    local fps = def.fps or 8
    if fps <= 0 then fail(name, "fps must be positive") end

    clip = {
        name          = name,
        image         = image,
        path          = def.path,
        frameWidth    = frameWidth,
        frameHeight   = frameHeight,
        columns       = columns,
        frames        = frames,
        frameTime     = 1 / fps,
        durations     = def.durations,
        mode          = mode,
        speed         = def.speed or 1,
        events        = events,
        eventsByFrame = eventsByFrame,
    }

    resolved[name] = clip
    return clip
end

return Clip
