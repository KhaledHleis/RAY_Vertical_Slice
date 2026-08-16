-- animation_player.lua
--
-- Plays a named clip and writes the resulting frame into a sibling renderer.
-- It never draws. That is the whole point: SpriteRenderer owns the drawing,
-- AnimationPlayer owns the playhead, and neither knows why a clip changed.
--
--   { type = "SpriteRenderer",  args = { scale = { x = 1, y = 1 } } },
--   { type = "AnimationPlayer", args = { clips = { "CoinSpin" }, autoPlay = "CoinSpin" } },
--
-- Declaration order matters: components attach in order, and OnAttach looks
-- the target up by name, so the renderer must come first.
--
-- args:
--   clips      list of clip names to resolve up front. Optional -- Play
--              resolves on demand -- but preloading here means a missing
--              sheet is a load-time crash instead of a mid-level one.
--   autoPlay   clip to start on attach.
--   target     which sibling receives frames. Default "SpriteRenderer".
--              Anything exposing SetSheet(image, w, h) and SetFrame(col, row)
--              works, which is how PlayerRenderer -- foot-anchored and
--              squash-aware, so not a SpriteRenderer -- is driven by the same
--              component.
--   speed      playback multiplier, on top of the clip's own.
--
-- Events. A clip's events fire the frame they are declared on, both on the
-- EventBus and to local listeners:
--
--   player:On("finished", function(clipName) ... end)
--   EventBus.subscribe("animation:finished", function(object, clipName) ... end)
--
-- What is deliberately absent: any notion of *why* a clip should change.
-- No parameters, no conditions, no transitions. That is the Animator's job,
-- and it will sit on top of this and call Play() -- the same way an Animator
-- drives a SpriteRenderer in Unity rather than replacing it.

local Component = require('Libraries.universal.component')
local EventBus  = require('Libraries.universal.event_bus')
local Clip      = require('Libraries.animation.clip')
local Playhead  = require('Libraries.animation.playhead')

local AnimationPlayer = setmetatable({}, { __index = Component })
AnimationPlayer.__index = AnimationPlayer

function AnimationPlayer.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, AnimationPlayer)

    self.targetName    = args.target or "SpriteRenderer"
    self.clips         = args.clips
    self.autoPlay      = args.autoPlay
    self.publishEvents = args.publishEvents ~= false

    self.playhead = Playhead.new()
    self.playhead.speed = args.speed or 1

    self.clipName  = nil
    self.target    = nil
    self.object    = nil
    self.listeners = {}

    return self
end

function AnimationPlayer:__tostring()
    return "AnimationPlayer"
end

function AnimationPlayer:OnAttach(object)
    self.object = object
    self.target = object:GetComponent(self.targetName)

    if not self.target then
        error(("AnimationPlayer: no %s on this object. Declare it before "
            .. "AnimationPlayer in the prefab, or set `target`."):format(self.targetName))
    end
    if not (self.target.SetSheet and self.target.SetFrame) then
        error(("AnimationPlayer: %s cannot receive frames -- it needs "
            .. "SetSheet(image, w, h) and SetFrame(col, row)."):format(self.targetName))
    end

    for _, name in ipairs(self.clips or {}) do
        Clip.Resolve(name)
    end

    if self.autoPlay then self:Play(self.autoPlay) end
end

------------------------------------------------------------------- playback

-- Starts `name`. Restarting the clip that is already running is a no-op
-- unless `force` is true, so a caller can drive this from a state every
-- frame without stuttering the animation back to frame 1.
function AnimationPlayer:Play(name, force)
    if name == nil then return end
    if not force and self.clipName == name and self.playhead.playing then return end

    local clip = Clip.Resolve(name)
    self.clipName = name
    self.playhead:SetClip(clip, 1)
    self:_apply()
    self:_fireFrameEvents(1)
end

function AnimationPlayer:Stop()
    self.playhead:Stop()
    self:_apply()
end

function AnimationPlayer:Pause()
    self.playhead.playing = false
end

function AnimationPlayer:Resume()
    if self.playhead.clip then self.playhead.playing = true end
end

-- No argument: is anything playing. With a name: is *that* clip playing.
function AnimationPlayer:IsPlaying(name)
    if not self.playhead.playing then return false end
    return name == nil or self.clipName == name
end

function AnimationPlayer:SetSpeed(speed)
    self.playhead.speed = speed or 1
end

function AnimationPlayer:CurrentClip()
    return self.clipName
end

-- 1-based position in the current clip's frame list.
function AnimationPlayer:CurrentFrame()
    return self.playhead.index
end

function AnimationPlayer:FrameCount()
    return self.playhead:FrameCount()
end

-- Jumps to a 1-based position in the current clip and pushes that frame to
-- the target immediately, without waiting for an Update. Holds there unless
-- keepPlaying is true.
--
-- This is the "snap to a pose" primitive: a door that should start already
-- open, a level editor scrubbing a clip, a cutscene skip. Frame events are
-- deliberately not fired -- the frames in between were never played, so a
-- footstep or a sound cue on them would be a lie.
function AnimationPlayer:Seek(index, keepPlaying)
    local playhead = self.playhead
    if not playhead.clip then return end

    playhead:SetClip(playhead.clip, index)
    playhead.playing = keepPlaying == true
    self:_apply()
    playhead.dirty = false
end

function AnimationPlayer:NormalizedTime()
    return self.playhead:NormalizedTime()
end

-- Local listener, torn down with the object. Event names: "finished", and
-- any event name declared on a clip.
function AnimationPlayer:On(eventName, callback)
    local bucket = self.listeners[eventName]
    if not bucket then
        bucket = {}
        self.listeners[eventName] = bucket
    end
    table.insert(bucket, callback)
    return callback
end

--------------------------------------------------------------------- update

function AnimationPlayer:Update(object, dt)
    local playhead = self.playhead
    if not playhead.clip then return end

    local crossed = playhead:Advance(dt)
    for i = 1, #crossed do
        self:_fireFrameEvents(crossed[i])
    end

    if playhead.dirty then
        self:_apply()
        playhead.dirty = false
    end

    if playhead.finished then
        playhead.finished = false
        self:_emit("finished", self.clipName)
        if self.publishEvents then
            EventBus.publish("animation:finished", object, self.clipName)
        end
    end
end

function AnimationPlayer:_apply()
    local clip = self.playhead.clip
    local target = self.target
    if not (clip and target) then return end

    local frame = clip.frames[self.playhead.index]
    if not frame then return end

    target:SetSheet(clip.image, clip.frameWidth, clip.frameHeight)
    target:SetFrame(frame.col, frame.row)
end

function AnimationPlayer:_fireFrameEvents(index)
    local clip = self.playhead.clip
    local byFrame = clip and clip.eventsByFrame
    if not byFrame then return end

    local names = byFrame[index]
    if not names then return end

    for i = 1, #names do
        local name = names[i]
        self:_emit(name, self.clipName, index)
        if self.publishEvents then
            EventBus.publish(name, self.object, self.clipName, index)
        end
    end
end

function AnimationPlayer:_emit(eventName, ...)
    local bucket = self.listeners[eventName]
    if not bucket then return end
    for i = 1, #bucket do
        bucket[i](...)
    end
end

function AnimationPlayer:OnDestroy()
    self.listeners = {}
    self.target = nil
end

return AnimationPlayer
