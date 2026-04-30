-- Severity.lua : 0-5 tension engine. Decays over time, spikes on threat events.
local _, ns = ...
local Severity = { value = 0, lastEmit = -1 }
ns.Severity = Severity

local DECAY_PER_SEC = 0.5

function Severity:Init()
    local f = CreateFrame("Frame")
    f.t = 0
    f:SetScript("OnUpdate", function(_, dt)
        f.t = f.t + dt
        if f.t >= 0.5 then
            self.value = math.max(0, self.value - DECAY_PER_SEC * f.t)
            f.t = 0
            self:Emit()
        end
    end)

    ns.EventBus:On("PLAYER_REGEN_DISABLED", function() self:Bump(2) end)
    ns.EventBus:On("PLAYER_DEAD",           function() self:Bump(5) end)
    ns.EventBus:On("UNIT_HEALTH", function()
        local p = ns.State.player
        if p.hpMax > 0 then
            local pct = p.hp / p.hpMax
            if pct < 0.25 then self:Bump(3)
            elseif pct < 0.5 then self:Bump(1) end
        end
    end)
end

function Severity:Bump(n)
    self.value = math.min(5, self.value + n)
    self:Emit()
end

function Severity:Emit()
    local lvl = math.floor(self.value + 0.5)
    if lvl ~= self.lastEmit then
        self.lastEmit = lvl
        ns.EventBus:Emit("SEVERITY", lvl)
    end
end
