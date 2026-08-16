-- light_detector.lua
--
-- Turns "light landed on this object's segments" into a piece of state and a
-- pair of events. LightWorld.resolveDetectors owns the transition: it flips
-- `lit`, calls OnHit/OnLost, and publishes "light:hit" / "light:lost" on the
-- EventBus so anything else can react without holding a reference here.
--
-- args, all optional:
--
--   channel      a name other systems can filter on. A Door with
--                channel = "vault" only listens to detectors carrying the same
--                string; a Door with no channel listens to all of them. Kept a
--                plain string so a prefab stays round-trippable through
--                Tools/prefab_editor.
--   litSprite    image swapped into the sibling renderer while lit.
--   unlitSprite  image swapped back in when the light is lost. Defaults to
--                whatever the renderer was already holding, so a prefab only
--                has to name the lit one.
--   litColor     tint applied while lit, e.g. {1, 0.9, 0.6, 1}.
--   unlitColor   tint applied when unlit. Defaults to the renderer's own.
--   renderer     which sibling to drive. Default "SpriteRenderer".
--
-- The renderer is looked up in OnAttach, so it must be declared before the
-- LightDetector in the prefab -- the same rule AnimationPlayer follows. A
-- detector with no renderer at all is fine; it just has no visual state.

local Component = require('Libraries.universal.component')
local LightWorld = require('Libraries.light_engine.light_world')
local SpriteRenderer = require('Libraries.renderer.sprite_renderer')

local LightDetector = setmetatable({}, { __index = Component })
LightDetector.__index = LightDetector

function LightDetector.new(args)
    args = args or {}
    local self = Component.new()
    setmetatable(self, LightDetector)

    self.lit = false
    self.hits = nil

    self.channel      = args.channel
    self.litSprite    = args.litSprite
    self.unlitSprite  = args.unlitSprite
    self.litColor     = args.litColor
    self.unlitColor   = args.unlitColor
    self.rendererName = args.renderer or "SpriteRenderer"

    self.renderer   = nil
    self.litImage   = nil
    self.unlitImage = nil

    return self
end

function LightDetector:__tostring()
    return "LightDetector"
end

function LightDetector:OnAttach(object)
    self.object = object
    self.renderer = object:GetComponent(self.rendererName)

    if self.renderer then
        self.litImage = SpriteRenderer.Load(self.litSprite)
        -- No unlitSprite means "whatever the renderer already draws", which is
        -- the common case: the prefab names one path for the off state and one
        -- for the on state, and only the second one is news to this component.
        self.unlitImage = SpriteRenderer.Load(self.unlitSprite) or self.renderer.image
        self.unlitColor = self.unlitColor or self.renderer.color
    end

    LightWorld.registerDetector(self)
    self:Apply()
end

function LightDetector:OnDestroy(object)
    LightWorld.unregisterDetector(self)
    self.renderer   = nil
    self.litImage   = nil
    self.unlitImage = nil
    self.hits       = nil
end

-- Pushes the current lit state onto the renderer. Idempotent and cheap --
-- SetImage returns immediately when the image is already the right one -- so
-- it is safe to call from anywhere, including a "change" that turns out not to
-- be one.
function LightDetector:Apply()
    local renderer = self.renderer
    if not renderer then return end

    local image = self.lit and self.litImage or self.unlitImage
    if image then renderer:SetImage(image) end

    local color = self.lit and self.litColor or self.unlitColor
    if color then renderer.color = color end
end

function LightDetector:IsLit()
    return self.lit
end

-- Called by LightWorld.resolveDetectors, which has already set self.lit.
function LightDetector:OnHit(hits)
    self.hits = hits
    self:Apply()
end

function LightDetector:OnLost()
    self.hits = nil
    self:Apply()
end

return LightDetector
