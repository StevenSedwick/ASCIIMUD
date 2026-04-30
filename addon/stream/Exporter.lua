-- Exporter.lua : enable game logs and let the engine write to disk.
--
-- Classic Era addons cannot write arbitrary files. The two file paths
-- the game engine itself provides are:
--   * Logs/WoWChatLog.txt    (when LoggingChat(true)) — server chat events
--   * Logs/WoWCombatLog.txt  (when LoggingCombat(true)) — combat events
--
-- We can't fake CHAT_MSG_* events, but EVERY combat event the player is
-- involved in is real and will be written by the engine. The companion
-- tails WoWCombatLog.txt and parses standard combat-log format.
--
-- This module is intentionally tiny: just turn the loggers on, idempotent.
local _, ns = ...
local Exporter = {}
ns.Exporter = Exporter

local function enableLogs()
    -- Always force-set; the no-arg getter is unreliable on Classic Era.
    local okC, errC = pcall(LoggingCombat, true)
    local okT, errT = pcall(LoggingChat, true)
    print(string.format(
        "|cff66ccffASCIIMUD|r: LoggingCombat(true)=%s LoggingChat(true)=%s",
        okC and "ok" or ("ERR:" .. tostring(errC)),
        okT and "ok" or ("ERR:" .. tostring(errT))
    ))
end

function Exporter:Init()
    -- Defer slightly: LoggingChat is a no-op if called before chat is wired.
    C_Timer.After(2, enableLogs)
    -- Re-assert on any reload/zone in case Blizzard turned it off.
    local f = CreateFrame("Frame")
    f:RegisterEvent("PLAYER_ENTERING_WORLD")
    f:SetScript("OnEvent", function() C_Timer.After(1, enableLogs) end)
end
