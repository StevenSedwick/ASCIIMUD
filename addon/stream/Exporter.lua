-- Exporter.lua : emits NDJSON lines into the chat log so the companion can tail them.
-- Each line: a single JSON object on the SAY channel via the addon comm channel,
-- prefixed so the companion can filter cleanly: `ASCIIMUD|{...}`
local _, ns = ...
local Exporter = {}
ns.Exporter = Exporter

local PREFIX = "ASCIIMUD"
local lastSnapshot = 0
local SNAPSHOT_HZ = 2  -- twice a second

local function emit(obj)
    local line = PREFIX .. "|" .. ns.json.encode(obj)
    -- DEFAULT_CHAT_FRAME prints to the chat window, which /chatlog mirrors
    -- to Logs/WoWChatLog.txt. The companion tails that file.
    DEFAULT_CHAT_FRAME:AddMessage(line)
end

function Exporter:Init()
    ns.EventBus:On("STATE_CHANGED", function(s)
        local now = GetTime()
        if now - lastSnapshot < (1 / SNAPSHOT_HZ) then return end
        lastSnapshot = now
        emit({ t = "snapshot", data = s })
    end)
    ns.EventBus:On("SEVERITY", function(level)
        emit({ t = "severity", level = level })
    end)
    ns.EventBus:On("PLAYER_DEAD", function()
        emit({ t = "death", player = ns.State.player.name })
    end)
    ns.EventBus:On("COMBAT_SUMMARY", function(s)
        emit({ t = "combat_summary", spell = s.spell, count = s.count, total = s.total })
    end)
end
