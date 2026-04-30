-- Coalesce.lua : collapse combat-log spam into summary lines.
-- e.g. "Sinister Strike x6 (1245 dmg)" instead of six separate entries.
local _, ns = ...
local Coalesce = {}
ns.Coalesce = Coalesce

local WINDOW = 1.5
local buckets = {}

function Coalesce:Init()
    ns.EventBus:On("COMBAT_LOG_EVENT_UNFILTERED", function()
        local _, sub, _, srcGUID, srcName, _, _, _, _, _, _, _, spellName, _, amount =
            CombatLogGetCurrentEventInfo()
        if not srcName or srcGUID ~= UnitGUID("player") then return end
        if sub ~= "SPELL_DAMAGE" and sub ~= "SWING_DAMAGE" then return end
        local key = spellName or "Melee"
        local b = buckets[key] or { count = 0, total = 0, last = 0 }
        b.count = b.count + 1
        b.total = b.total + (tonumber(amount) or 0)
        b.last  = GetTime()
        buckets[key] = b
    end)

    local f = CreateFrame("Frame")
    f.t = 0
    f:SetScript("OnUpdate", function(_, dt)
        f.t = f.t + dt
        if f.t < 0.5 then return end
        f.t = 0
        local now = GetTime()
        for k, b in pairs(buckets) do
            if now - b.last > WINDOW then
                ns.Feed:Push(string.format("|cffffaa44%s x%d (%d dmg)|r", k, b.count, b.total))
                buckets[k] = nil
            end
        end
    end)
end
