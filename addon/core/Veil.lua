-- Veil.lua : opaque full-screen black backdrop that hides UIParent.
local _, ns = ...
local Veil = {}
ns.Veil = Veil

function Veil:Init()
    local f = CreateFrame("Frame", "ASCIIMUDVeil", UIParent)
    f:SetFrameStrata("FULLSCREEN")
    f:SetAllPoints(UIParent)
    f:EnableMouse(true)

    local tex = f:CreateTexture(nil, "BACKGROUND")
    tex:SetAllPoints()
    tex:SetColorTexture(0, 0, 0, 1)

    self.frame = f
    self.shown = true
    self:Show()
end

function Veil:Show()
    self.frame:Show()
    UIParent:Hide()
    self.shown = true
end

function Veil:Hide()
    self.frame:Hide()
    UIParent:Show()
    self.shown = false
end

function Veil:Toggle()
    if self.shown then self:Hide() else self:Show() end
end
