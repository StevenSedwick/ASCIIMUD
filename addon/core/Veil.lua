-- Veil.lua : opaque full-screen black frame that covers the 3D world AND the UI.
-- Parented to WorldFrame (NOT UIParent) so it stays visible even if some other
-- addon hides UIParent. Uses TOOLTIP strata so it sits above every standard
-- Blizzard frame. Initialized at file-load time (not PLAYER_LOGIN) so the
-- screen is already black before the loading screen finishes fading out.
local _, ns = ...
local Veil = {}
ns.Veil = Veil

function Veil:Init()
    if self.frame then return end

    -- Parent to WorldFrame (always exists, never gets hidden by other addons).
    local f = CreateFrame("Frame", "ASCIIMUDVeil", WorldFrame)
    f:SetFrameStrata("TOOLTIP")  -- above every standard frame
    f:SetFrameLevel(100)
    f:SetAllPoints(WorldFrame)
    f:EnableMouse(true)
    f:EnableKeyboard(false)      -- don't swallow ESC, chat, etc.

    local tex = f:CreateTexture(nil, "BACKGROUND")
    tex:SetAllPoints()
    tex:SetColorTexture(0, 0, 0, 1)
    self.bg = tex

    -- Re-assert visibility whenever the world frame resizes (alt-tab, etc.).
    f:SetScript("OnSizeChanged", function(self)
        self:SetAllPoints(WorldFrame)
    end)

    self.frame = f
    self.shown = true
    f:Show()
end

function Veil:Show()
    if not self.frame then self:Init() end
    self.frame:Show()
    self.frame:Raise()
    self.shown = true
end

function Veil:Hide()
    if not self.frame then return end
    self.frame:Hide()
    self.shown = false
end

function Veil:Toggle()
    if self.shown then self:Hide() else self:Show() end
end

-- Initialize immediately at file-load time so the screen is black from frame 1,
-- before PLAYER_LOGIN and before the loading-screen fadeout completes.
Veil:Init()
