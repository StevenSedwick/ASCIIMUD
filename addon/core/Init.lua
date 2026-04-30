-- Init.lua : bootstrap, slash commands, /chatlog auto-enable.
-- ASCIIMUD is a HEADLESS pipeline addon — it draws no UI of its own.
-- The in-game UI is owned by TextAdventurer. ASCIIMUD only observes
-- game state and emits NDJSON events to the chat log for the companion
-- process (which feeds the OBS overlay and Twitch extension).
local addonName, ns = ...
ASCIIMUD = ns

ns.version = "0.2.0"

local function safeChatLog()
    C_Timer.After(2, function()
        if not LoggingChat() then
            LoggingChat(true)
            print("|cff66ccffASCIIMUD|r: chat log enabled (Logs/WoWChatLog.txt).")
        end
    end)
end

local function bootstrap()
    ns.State:Init()
    ns.EventBus:Init()
    ns.Severity:Init()
    ns.Coalesce:Init()
    ns.Exporter:Init()
    safeChatLog()
    print(string.format("|cff66ccffASCIIMUD|r v%s online (headless stream pipeline).", ns.version))
end

local f = CreateFrame("Frame")
f:RegisterEvent("PLAYER_LOGIN")
f:SetScript("OnEvent", function(_, event)
    if event == "PLAYER_LOGIN" then bootstrap() end
end)

SLASH_ASCIIMUD1 = "/asciimud"
SLASH_ASCIIMUD2 = "/mud"
SlashCmdList.ASCIIMUD = function(msg)
    msg = (msg or ""):lower():match("^%s*(.-)%s*$")
    if msg == "status" then
        local s = ns.State:Snapshot()
        print(string.format("|cff66ccffASCIIMUD|r tick=%d zone=%s combat=%s",
            s.tick, s.zone.name, tostring(s.combat)))
    elseif msg == "reload" then
        ReloadUI()
    elseif msg == "chatlog" then
        if LoggingChat() then
            print("|cff66ccffASCIIMUD|r: chat log already enabled.")
        else
            LoggingChat(true)
            print("|cff66ccffASCIIMUD|r: chat log enabled.")
        end
    else
        print("|cff66ccffASCIIMUD|r commands: /mud [status|reload|chatlog]")
        print("  This addon is headless. Use TextAdventurer for the in-game UI.")
    end
end
