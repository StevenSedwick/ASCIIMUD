-- Init.lua : bootstrap, slash commands, /chatlog auto-enable.
local addonName, ns = ...
ASCIIMUD = ns

ns.version = "0.1.0"

local function safeChatLog()
    -- Blizzard silently no-ops LoggingChat if called too early on login.
    -- Defer to ensure the chat system is fully wired up first.
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
    ns.Veil:Init()
    ns.Header:Init()
    ns.Grid:Init()
    ns.Feed:Init()
    ns.Effects:Init()
    ns.Severity:Init()
    ns.Coalesce:Init()
    ns.Exporter:Init()
    safeChatLog()
    ns.Feed:Push("ASCIIMUD v" .. ns.version .. " online.")
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
    if msg == "off" or msg == "hide" then
        ns.Veil:Hide()
    elseif msg == "on" or msg == "show" then
        ns.Veil:Show()
    elseif msg == "toggle" or msg == "" then
        ns.Veil:Toggle()
    elseif msg == "reload" then
        ReloadUI()
    else
        print("|cff66ccffASCIIMUD|r commands: /mud [on|off|toggle|reload]")
    end
end
