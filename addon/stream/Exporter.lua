-- Exporter.lua : emit NDJSON to a private chat channel that /chatlog captures.
--
-- DESIGN: We must NOT use DEFAULT_CHAT_FRAME:AddMessage — other addons
-- (e.g. TextAdventurer) hook the chat frame to harvest game text, and our
-- 2 Hz JSON snapshots will firehose them into instability.
--
-- Instead we JoinTemporaryChannel("asciimud_data"), which:
--   * creates a private channel only this character is in
--   * triggers CHAT_MSG_CHANNEL when we SendChatMessage to it
--   * is captured by /chatlog into Logs/WoWChatLog.txt
--   * we then yank from every visible ChatFrame so the user never sees it
local _, ns = ...
local Exporter = {}
ns.Exporter = Exporter

local PREFIX        = "ASCIIMUD"
local CHANNEL_NAME  = "asciimud"
local SNAPSHOT_HZ   = 2
local MAX_LINE      = 240  -- WoW chat hard limit ~255 bytes; keep safety margin

local lastSnapshot  = 0
local channelIndex  = nil
local pendingQueue  = {}

local function hideChannelFromAllFrames()
    for i = 1, NUM_CHAT_WINDOWS do
        local frame = _G["ChatFrame" .. i]
        if frame then
            ChatFrame_RemoveChannel(frame, CHANNEL_NAME)
        end
    end
end

local function tryJoinChannel()
    local idx = GetChannelName(CHANNEL_NAME)
    if idx and idx > 0 then
        channelIndex = idx
        hideChannelFromAllFrames()
        return true
    end
    JoinTemporaryChannel(CHANNEL_NAME)
    idx = GetChannelName(CHANNEL_NAME)
    if idx and idx > 0 then
        channelIndex = idx
        hideChannelFromAllFrames()
        return true
    end
    return false
end

local function flushPending()
    if not channelIndex or #pendingQueue == 0 then return end
    for i = 1, #pendingQueue do
        SendChatMessage(pendingQueue[i], "CHANNEL", nil, channelIndex)
    end
    pendingQueue = {}
end

local function emit(obj)
    local line = PREFIX .. "|" .. ns.json.encode(obj)
    if #line > MAX_LINE then
        -- Truncate-with-marker. Companion will still see the prefix
        -- and skip the malformed JSON gracefully.
        line = line:sub(1, MAX_LINE - 4) .. "...}"
    end
    if not channelIndex then
        if #pendingQueue < 16 then table.insert(pendingQueue, line) end
        return
    end
    SendChatMessage(line, "CHANNEL", nil, channelIndex)
end

function Exporter:Init()
    -- Channels can't be joined until after PLAYER_ENTERING_WORLD; retry.
    local attempts, retry = 0, nil
    retry = function()
        attempts = attempts + 1
        if tryJoinChannel() then
            flushPending()
            return
        end
        if attempts < 20 then
            C_Timer.After(1, retry)
        else
            print("|cffff5555ASCIIMUD|r: failed to join data channel after 20 attempts.")
        end
    end
    C_Timer.After(2, retry)

    -- Re-hide the channel any time chat windows reload (Blizzard re-adds it).
    local f = CreateFrame("Frame")
    f:RegisterEvent("CHAT_MSG_CHANNEL_NOTICE")
    f:RegisterEvent("UPDATE_CHAT_WINDOWS")
    f:SetScript("OnEvent", function() hideChannelFromAllFrames() end)

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
