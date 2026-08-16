-- Minimal headless stand-in for love, just enough to boot the engine and
-- run frames outside of LOVE. Test-only.

local mock = {}

local liveBodies, liveJoints, liveWorlds = 0, 0, 0
local liveImages = 0
local liveBatches = 0

function mock.counts()
    return { bodies = liveBodies, joints = liveJoints, worlds = liveWorlds,
             images = liveImages, batches = liveBatches }
end

local function noop() end

-- graphics -----------------------------------------------------------------

local function newImage(path)
    liveImages = liveImages + 1
    local image = {}
    -- Real dimensions for any sheet whose frame maths a test depends on. Clip
    -- maps flat frame indices through floor(imageWidth / frameWidth), so a
    -- stubbed 64x64 collapses every sheet into a single column and quietly
    -- rewrites the animation out from under the assertion.
    local w, h = 64, 64
    local name = tostring(path)
    if name:find("venus_animation") then w, h = 2352, 24 end
    if name:find("Name") then w, h = 65, 7 end
    if name:find("door/door") then w, h = 384, 64 end
    if name:find("sprites/detector") then w, h = 36, 32 end
    if name:find("ray_walk") then w, h = 192, 32 end
    if name:find("ray_idle") then w, h = 96, 32 end
    function image:getDimensions() return w, h end
    function image:getWidth() return w end
    function image:getHeight() return h end
    function image.setFilter() end
    return image
end

-- The viewport is tracked for real: SpriteRenderer:SetImage re-derives the
-- current cell from it when swapping sheets, so a stub that forgot it would
-- silently pass a test that the game fails.
local quad = {}
quad.__index = quad
function quad:setViewport(x, y, w, h)
    self.x, self.y, self.w, self.h = x, y, w, h
end
function quad:getViewport()
    return self.x or 0, self.y or 0, self.w or 0, self.h or 0
end
function quad.release() end

-- Counted, because Tilemap allocates one batch per map and LevelManager's
-- teardown test asserts that a level switch leaves nothing behind.
local function newSpriteBatch()
    liveBatches = liveBatches + 1
    local batch = { sprites = 0, released = false }
    function batch:add() self.sprites = self.sprites + 1 end
    function batch:clear() self.sprites = 0 end
    function batch:getCount() return self.sprites end
    function batch:release()
        if self.released then return end
        self.released = true
        liveBatches = liveBatches - 1
    end
    return batch
end

local graphics = {
    newImage = newImage,
    newQuad = function(x, y, w, h)
        return setmetatable({ x = x or 0, y = y or 0, w = w or 0, h = h or 0 }, quad)
    end,
    newSpriteBatch = newSpriteBatch,
    newFont = function() return { getHeight = function() return 8 end,
                                  getWidth = function() return 8 end,
                                  release = noop } end,
    newCanvas = function() return { setFilter = noop } end,
    newMesh = function() return { setVertices = noop } end,
    setDefaultFilter = noop, setLineStyle = noop, setLineWidth = noop,
    setColor = noop, setCanvas = noop, setFont = noop, clear = noop,
    draw = noop, line = noop, circle = noop, polygon = noop,
    rectangle = noop, print = noop, printf = noop,
    push = noop, pop = noop, translate = noop, rotate = noop,
    getFont = function() return { getHeight = function() return 8 end } end,
    getDimensions = function() return 960, 720 end,
    getWidth = function() return 960 end,
    getHeight = function() return 720 end,
}

-- physics ------------------------------------------------------------------

local physics = {}

function physics.setMeter() end

function physics.newWorld()
    liveWorlds = liveWorlds + 1
    local world = { destroyed = false, bodies = {} }
    function world:setCallbacks() end
    function world:update() end
    function world:rayCast() end
    function world:isDestroyed() return self.destroyed end
    function world:destroy()
        if self.destroyed then return end
        for _, body in ipairs(self.bodies) do body:destroy() end
        self.destroyed = true
        liveWorlds = liveWorlds - 1
    end
    return world
end

function physics.newBody(world, x, y, bodyType)
    liveBodies = liveBodies + 1
    local body = { x = x or 0, y = y or 0, angle = 0, vx = 0, vy = 0, destroyed = false }
    table.insert(world.bodies, body)
    function body:getPosition() return self.x, self.y end
    function body:setPosition(nx, ny) self.x, self.y = nx, ny end
    function body:getAngle() return self.angle end
    function body:setAngle(a) self.angle = a end
    function body:getLinearVelocity() return self.vx, self.vy end
    function body:setLinearVelocity(vx, vy) self.vx, self.vy = vx, vy end
    function body:applyForce() end
    function body:setBullet() end
    function body:setFixedRotation() end
    function body:setGravityScale() end
    function body:isDestroyed() return self.destroyed end
    function body:destroy()
        if self.destroyed then return end
        self.destroyed = true
        liveBodies = liveBodies - 1
    end
    return body
end

function physics.newRectangleShape() return {} end
function physics.newCircleShape() return {} end

function physics.newFixture(body)
    local fixture = { userData = nil, sensor = false }
    function fixture:getBody() return body end
    function fixture:setUserData(d) self.userData = d end
    function fixture:getUserData() return self.userData end
    function fixture:setFriction() end
    function fixture:setRestitution() end
    function fixture:setSensor(v) self.sensor = v and true or false end
    function fixture:isSensor() return self.sensor end
    function fixture:setDensity() end
    return fixture
end

function physics.newRevoluteJoint()
    liveJoints = liveJoints + 1
    local joint = { destroyed = false }
    function joint:setLimits() end
    function joint:setLimitsEnabled() end
    function joint:setMotorEnabled() end
    function joint:setMotorSpeed() end
    function joint:setMaxMotorTorque() end
    function joint:isDestroyed() return self.destroyed end
    function joint:destroy()
        if self.destroyed then return end
        self.destroyed = true
        liveJoints = liveJoints - 1
    end
    return joint
end

-- the rest -----------------------------------------------------------------

function mock.install()
    _G.love = {
        graphics = graphics,
        physics = physics,
        audio = { newSource = function()
            local source = { playing = false }
            function source:play() self.playing = true end
            function source:stop() self.playing = false end
            function source:isPlaying() return self.playing end
            return source
        end },
        keyboard = { isDown = function() return false end },
        joystick = { getJoysticks = function() return {} end },
        timer = { getFPS = function() return 60 end },
        event = { quit = noop },
        filesystem = {
            getInfo = function() return nil end,
            load = function() return nil end,
            write = noop,
        },
        window = {},
    }
    return _G.love
end

return mock
