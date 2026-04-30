-- Exporter.lua : keep WoW's chat & combat logs *flushed* on a tick.
--
-- WoW buffers /chatlog and /combatlog writes in-process. The buffer is only
-- flushed when:
--   * the player logs out
--   * /chatlog or /combatlog is toggled off (which closes the current file)
--
-- We exploit (2): every TICK_SECS we toggle each logger off→on. Each toggle
-- closes the current log (flushing it to disk) and immediately re-enables a
-- fresh timestamped file. The companion globs the directory for the newest
-- WoWChatLog-* / WoWCombatLog-* and reads each completed slice.
--
-- Latency = TICK_SECS. The cost is a "Combat logging enabled/disabled"
-- system message every tick, which we suppress via a chat-frame filter.
local _, ns = ...
local Exporter = {}
ns.Exporter = Exporter

local TICK_SECS = 30

local function flushOnce()
    -- Same-frame off+on is collapsed by WoW into a no-op.
    -- We need a real frame gap so the engine actually closes the file.
    if LoggingCombat then pcall(LoggingCombat, false) end
    if LoggingChat   then pcall(LoggingChat,   false) end
    C_Timer.After(0.75, function()
        if LoggingCombat then pcall(LoggingCombat, true) end
        if LoggingChat   then pcall(LoggingChat,   true) end
    end)
end

local function suppressLogToggleSpam(_, _, msg)
    if not msg then return end
    -- Match Blizzard's localized strings (English at least):
    --   "Combat logging enabled.", "Combat logging disabled."
    --   "Chat logging enabled.",   "Chat logging disabled."
    if msg:find("logging enabled%.") or msg:find("logging disabled%.") then
        return true  -- swallow
    end
    return false
end

function Exporter:Init()
    -- Start logs immediately, then re-flush on a fixed cadence.
    C_Timer.After(2, function()
        flushOnce()
        print(string.format(
            "|cff66ccffASCIIMUD|r: tick-flush logger online (every %ds).", TICK_SECS))
    end)

    if ChatFrame_AddMessageEventFilter then
        ChatFrame_AddMessageEventFilter("CHAT_MSG_SYSTEM", suppressLogToggleSpam)
    end

    local ticker = C_Timer.NewTicker(TICK_SECS, flushOnce)
    self._ticker = ticker

    -- Re-assert after any reload/zone in case Blizzard reset state.
    local f = CreateFrame("Frame")
    f:RegisterEvent("PLAYER_ENTERING_WORLD")
    f:SetScript("OnEvent", function() C_Timer.After(1, flushOnce) end)
end

