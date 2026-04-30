-- Effects.lua : screen shake, flash, sounds keyed off severity.
local _, ns = ...
local Effects = {}
ns.Effects = Effects

function Effects:Init()
    local flash = ns.Veil.frame:CreateTexture(nil, "OVERLAY")
    flash:SetAllPoints()
    flash:SetColorTexture(1, 0, 0, 0)
    self.flash = flash

    ns.EventBus:On("SEVERITY", function(level) self:React(level) end)
end

function Effects:Flash(r, g, b, a)
    self.flash:SetColorTexture(r, g, b, a)
    UIFrameFadeOut(self.flash, 0.4, a, 0)
end

function Effects:Shake(amount, duration)
    local v = ns.Veil.frame
    local t, elapsed = duration or 0.25, 0
    v:SetScript("OnUpdate", function(self, dt)
        elapsed = elapsed + dt
        if elapsed >= t then
            self:ClearAllPoints(); self:SetAllPoints(UIParent); self:SetScript("OnUpdate", nil); return
        end
        self:ClearAllPoints()
        self:SetPoint("TOPLEFT", UIParent, "TOPLEFT",
            math.random(-amount, amount), math.random(-amount, amount))
    end)
end

function Effects:React(level)
    if level >= 5 then self:Flash(1, 0, 0, 0.5); self:Shake(8, 0.4); PlaySound(8959)
    elseif level >= 4 then self:Flash(1, 0.4, 0, 0.3); self:Shake(4, 0.25)
    elseif level >= 3 then self:Flash(1, 1, 0, 0.15)
    end
end
