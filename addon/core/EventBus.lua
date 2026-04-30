-- EventBus.lua : Blizzard events -> typed internal events.
local _, ns = ...
local Bus = { handlers = {} }
ns.EventBus = Bus

function Bus:On(event, fn)
    self.handlers[event] = self.handlers[event] or {}
    table.insert(self.handlers[event], fn)
end

function Bus:Emit(event, payload)
    local list = self.handlers[event]
    if not list then return end
    for _, fn in ipairs(list) do
        local ok, err = pcall(fn, payload)
        if not ok then
            print("|cffff5555ASCIIMUD EventBus error:|r " .. tostring(err))
        end
    end
end

local BLIZZ = {
    "PLAYER_ENTERING_WORLD",
    "ZONE_CHANGED", "ZONE_CHANGED_NEW_AREA", "ZONE_CHANGED_INDOORS",
    "PLAYER_REGEN_DISABLED", "PLAYER_REGEN_ENABLED",
    "UNIT_HEALTH", "UNIT_POWER_UPDATE", "PLAYER_LEVEL_UP",
    "PLAYER_TARGET_CHANGED",
    "COMBAT_LOG_EVENT_UNFILTERED",
    "CHAT_MSG_SAY", "CHAT_MSG_YELL", "CHAT_MSG_EMOTE", "CHAT_MSG_MONSTER_SAY",
    "PLAYER_DEAD",
}

function Bus:Init()
    local f = CreateFrame("Frame")
    for _, ev in ipairs(BLIZZ) do f:RegisterEvent(ev) end
    f:SetScript("OnEvent", function(_, event, ...)
        local S = ns.State
        S.tick = S.tick + 1
        if event == "PLAYER_REGEN_DISABLED" then S.combat = true
        elseif event == "PLAYER_REGEN_ENABLED" then S.combat = false end
        if event:find("ZONE_CHANGED") or event == "PLAYER_ENTERING_WORLD" then S:UpdateZone() end
        if event == "UNIT_HEALTH" or event == "UNIT_POWER_UPDATE" or event == "PLAYER_LEVEL_UP" then S:UpdatePlayer() end
        if event == "PLAYER_TARGET_CHANGED" then S:UpdateTarget() end
        Bus:Emit(event, { ... })
        Bus:Emit("STATE_CHANGED", S:Snapshot())
    end)
    -- Prime initial state.
    ns.State:UpdatePlayer()
    ns.State:UpdateZone()
end
