-- playhead.lua
--
-- The playback maths, and nothing else: given a clip and a dt, which frame
-- are we on now, and which frames did we pass through getting here?
--
-- Deliberately free of love, EventBus and the component system. Two reasons.
-- It runs under a bare Lua interpreter, so the awkward parts (pingpong at the
-- ends, a clip whose fps is higher than the frame rate, a `once` clip landing
-- exactly on its last frame) are testable without launching the game. And
-- when an Animator or AnimationTree arrives, each blend node owns its own
-- Playhead -- the layer above changes, this does not.
--
--   local ph = Playhead.new()
--   ph:SetClip(clip)
--   local crossed = ph:Advance(dt)   -- array of frame indices entered
--   if ph.dirty then draw(clip.frames[ph.index]) ; ph.dirty = false end
--
-- `crossed` lists *every* frame entered this tick, not just the final one.
-- At 12 fps on a device dropping to 20 fps, a naive playhead skips frames and
-- silently swallows their events -- a footstep that never plays. This one
-- reports them all, in order, so the caller can fire each.
--
-- The returned array is reused between calls. Read it before the next
-- Advance; do not keep it. That is a small ugliness bought on purpose: this
-- runs every frame for every animated object on a handheld, and allocating a
-- fresh table per object per frame is exactly the kind of garbage that shows
-- up as stutter on the R36S.

local Playhead = {}
Playhead.__index = Playhead

-- Frames advanced in a single Advance before we give up and resynchronise.
-- Only reachable via a pathological dt (a debugger pause, a level load), and
-- the alternative is a frozen game inside a while loop.
local MAX_STEPS_PER_TICK = 64

-- Accumulated time is a running subtraction of frame durations, so a boundary
-- that should land exactly on zero lands a few ulps under instead: 0.05 +
-- 0.06 - 0.1 is 0.009999999999999995, not 0.01. Without this slack a clip
-- whose fps divides the frame rate drops a frame every so often, which reads
-- as an intermittent hitch and is miserable to track down.
local EPSILON = 1e-9

function Playhead.new()
    return setmetatable({
        clip      = nil,
        index     = 1,      -- 1-based position in clip.frames
        time      = 0,      -- seconds spent on the current frame
        direction = 1,      -- +1 forward, -1 returning (pingpong only)
        playing   = false,
        finished  = false,  -- latched on a completed `once`; caller clears it
        speed     = 1,
        dirty     = true,   -- the visible frame changed and needs applying
        crossed   = {},
    }, Playhead)
end

function Playhead:SetClip(clip, startIndex)
    local count = clip and #clip.frames or 1
    self.clip      = clip
    self.index     = math.max(1, math.min(startIndex or 1, count))
    self.time      = 0
    self.direction = 1
    self.playing   = clip ~= nil
    self.finished  = false
    self.dirty     = true
end

function Playhead:Stop()
    self.playing = false
    self.index   = 1
    self.time    = 0
    self.direction = 1
    self.dirty   = true
end

function Playhead:FrameDuration()
    local clip = self.clip
    if not clip then return 0 end
    local durations = clip.durations
    return (durations and durations[self.index]) or clip.frameTime
end

function Playhead:FrameCount()
    return self.clip and #self.clip.frames or 0
end

-- 0..1 across the whole clip, fractional within the current frame. Handy for
-- blending later; not used by AnimationPlayer itself.
function Playhead:NormalizedTime()
    local count = self:FrameCount()
    if count == 0 then return 0 end
    local duration = self:FrameDuration()
    local within = (duration > 0) and math.min(self.time / duration, 1) or 0
    return (self.index - 1 + within) / count
end

-- Decides the next index, handling the ends. Returns the index, or nil when
-- the clip has run out (a `once` clip holding on its last frame).
function Playhead:_step()
    local count = #self.clip.frames
    local mode  = self.clip.mode
    local next_ = self.index + self.direction

    if next_ > count then
        if mode == "loop" then return 1 end
        if mode == "pingpong" then
            self.direction = -1
            return count - 1
        end
        return nil
    end

    if next_ < 1 then
        if mode == "loop" then return count end
        if mode == "pingpong" then
            self.direction = 1
            return 2
        end
        return nil
    end

    return next_
end

-- Advances by dt and returns the (reused) list of frame indices entered.
function Playhead:Advance(dt)
    local crossed = self.crossed
    for i = #crossed, 1, -1 do crossed[i] = nil end

    local clip = self.clip
    if not clip or not self.playing or dt <= 0 then return crossed end

    local count = #clip.frames
    if count <= 1 then
        -- A one-frame clip has nowhere to go. `once` is done the moment it
        -- starts; `loop` just sits there.
        if clip.mode == "once" then
            self.playing  = false
            self.finished = true
        end
        return crossed
    end

    self.time = self.time + dt * self.speed * clip.speed

    local steps = 0
    while true do
        local duration = self:FrameDuration()
        if duration <= 0 then break end          -- a held frame
        if self.time + EPSILON < duration then break end

        self.time = self.time - duration

        local next_ = self:_step()
        if not next_ then
            -- `once` finished: hold the last frame, latch, and stop.
            self.playing  = false
            self.finished = true
            self.time     = 0
            break
        end

        self.index = next_
        self.dirty = true
        crossed[#crossed + 1] = next_

        steps = steps + 1
        if steps >= MAX_STEPS_PER_TICK then
            self.time = 0
            break
        end
    end

    return crossed
end

return Playhead
