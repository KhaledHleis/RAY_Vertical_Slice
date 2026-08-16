-- door.lua
--
-- The other half of a light puzzle: a LightDetector says "I am lit", and this
-- says what that is worth. It opens when a detector on its channel lights up,
-- and when the player walks into the open doorway it hands the level over.
--
-- Neither side knows about the other. The detector publishes "light:hit" on
-- the EventBus (LightWorld.resolveDetectors does it), the door subscribes, and
-- the only thing they agree on is a string -- so a level can wire three
-- detectors to one door, or two doors to one detector, without either
-- component changing.
--
--   { type = "SpriteRenderer",  args = { path = "...", frameWidth = 64, frameHeight = 64 } },
--   { type = "AnimationPlayer", args = { clips = { "DoorOpen", "DoorClose" } } },
--   { type = "RigidBody",       args = { bodyType = "static", sensor = true, width = 28, height = 56 } },
--   { type = "Door",            args = { nextLevel = "Frontend.levels.level_complete" } },
--
-- Declaration order matters, as everywhere else: OnAttach resolves the
-- AnimationPlayer by name, so it has to be attached by then.
--
-- args, all optional:
--
--   channel       only detectors carrying this channel count. nil (the
--                 default) means any detector opens this door.
--   openClip      clip played on opening. Default "DoorOpen".
--   closeClip     clip played on closing. With none, closing snaps back to the
--                 first frame of openClip instead.
--   autoClose     shut again when the last matching detector goes dark.
--                 Default false: a puzzle you have solved should usually stay
--                 solved while you walk to the exit.
--   startsOpen    begin fully open, no animation.
--   nextLevel     module path loaded when the player enters. Leave it out for
--                 a door that is only ever scenery or a physical gate.
--   requireInput  wait for up/W before triggering, instead of firing on
--                 contact. Default false.
--   trigger       component name that marks something as "the player".
--                 Default "PlayerController".
--   animator      which sibling plays the clips. Default "AnimationPlayer".
--
-- Events published: "door:opening", "door:opened", "door:closed",
-- "door:entered" (object, whoever walked in).

local Component = require('Libraries.universal.component')
local EventBus  = require('Libraries.universal.event_bus')
local Input     = require('Libraries.universal.input')

local Door = setmetatable({}, { __index = Component })
Door.__index = Door

-- Required lazily rather than at the top of the file. component_registry
-- requires this module, LevelManager requires Level which requires
-- component_registry -- so a require here at load time would re-enter
-- component_registry while it is still executing and never come back. By the
-- time anything calls this, every module is in package.loaded and the lookup
-- is a table read.
local function levelManager()
    return require('Libraries.universal.level_manager')
end

function Door.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, Door)

    self.channel      = args.channel
    self.openClip     = args.openClip or "DoorOpen"
    self.closeClip    = args.closeClip
    self.autoClose    = args.autoClose or false
    self.startsOpen   = args.startsOpen or false
    self.nextLevel    = args.nextLevel
    self.requireInput = args.requireInput or false
    self.triggerName  = args.trigger or "PlayerController"
    self.animatorName = args.animator or "AnimationPlayer"

    -- Three states, not two: `opening` is "has been told to open", `open` is
    -- "the animation got there". The player must not be able to step through
    -- a door that is still a slit.
    self.opening = false
    self.open    = false

    self.lit       = {}     -- detector -> true, the ones currently shining
    self.occupants = {}     -- object -> true, whatever is inside the doorway
    self.entered   = false  -- one-shot latch; the level switch is deferred

    return self
end

function Door:__tostring()
    return "Door"
end

function Door:OnAttach(object)
    self.object = object
    self.animator = object:GetComponent(self.animatorName)

    if self.animator then
        self.animator:On("finished", function(clipName)
            if clipName == self.openClip then
                self.open = true
                EventBus.publish("door:opened", object)
            elseif clipName == self.closeClip then
                self.open = false
                EventBus.publish("door:closed", object)
            end
        end)
    end

    self:Subscribe("light:hit", function(detector)
        if not self:_matches(detector) then return end
        self.lit[detector] = true
        self:Open()
    end)

    self:Subscribe("light:lost", function(detector)
        if not self:_matches(detector) then return end
        self.lit[detector] = nil
        if self.autoClose and next(self.lit) == nil then self:Close() end
    end)

    -- The sensor fixture reports the doorway being entered and left. Tracking
    -- occupancy rather than acting on the contact itself matters: the player
    -- can be standing in a closed doorway when the puzzle is solved, and that
    -- beginContact happened seconds ago.
    self:Subscribe("physics:collisionBegin", function(a, b)
        local other = self:_other(a, b)
        if other and self:_isTrigger(other) then self.occupants[other] = true end
    end)

    self:Subscribe("physics:collisionEnd", function(a, b)
        local other = self:_other(a, b)
        if other then self.occupants[other] = nil end
    end)

    if self.startsOpen then self:Open(true) end
end

function Door:OnDestroy(object)
    self.animator  = nil
    self.lit       = {}
    self.occupants = {}
end

-------------------------------------------------------------------- helpers

function Door:_matches(detector)
    if self.channel == nil then return true end
    return detector and detector.channel == self.channel
end

-- Which side of a contact is not us. nil when the contact is nothing to do
-- with this door, which is most of them.
function Door:_other(a, b)
    if a == self.object then return b end
    if b == self.object then return a end
    return nil
end

function Door:_isTrigger(object)
    if not (object and object.GetComponent) then return false end
    return object:GetComponent(self.triggerName) ~= nil
end

------------------------------------------------------------------- commands

-- Opens the door. `instant` skips the animation and lands on the last frame,
-- which is what startsOpen wants and what a debug key would want.
function Door:Open(instant)
    if self.opening then return end
    self.opening = true

    if not self.animator then
        self.open = true
        EventBus.publish("door:opened", self.object)
        return
    end

    self.animator:Play(self.openClip, true)

    if instant then
        -- Play lands on frame 1 and starts running; hold the last frame
        -- instead, applied straight away rather than one Update later.
        self.animator:Seek(self.animator:FrameCount())
        self.open = true
        EventBus.publish("door:opened", self.object)
        return
    end

    EventBus.publish("door:opening", self.object)
end

function Door:Close()
    if not self.opening then return end
    self.opening = false
    self.open = false

    if not self.animator then
        EventBus.publish("door:closed", self.object)
        return
    end

    if self.closeClip then
        self.animator:Play(self.closeClip, true)
    else
        -- No reverse clip authored: rewind the open clip to its first frame,
        -- which for a door sheet is the shut one. Play first so Stop has the
        -- right clip to rewind, even if the door was never opened.
        self.animator:Play(self.openClip, true)
        self.animator:Stop()
        EventBus.publish("door:closed", self.object)
    end
end

function Door:IsOpen()
    return self.open
end

--------------------------------------------------------------------- update

function Door:Update(object, dt)
    if self.entered or not self.open then return end

    local occupant = next(self.occupants)
    if not occupant then return end

    if self.requireInput and not Input.state.up then return end

    -- Latched: LevelManager.load only queues the switch, so this Update runs
    -- again before the level actually goes away.
    self.entered = true
    EventBus.publish("door:entered", object, occupant)

    if self.nextLevel then
        levelManager().load(self.nextLevel)
    end
end

return Door
