-- SpellRegistry.lua
--
-- The QR payload is byte-tight: cast bars, buffs and debuffs ride as bare
-- 16-bit spell IDs. To make those readable in the overlay (icon + name +
-- rank) we resolve them once *in-game* via GetSpellInfo and ship the
-- metadata over the existing chat-log NDJSON side channel.
--
-- We also dump the action-bar layout (which spell sits in which of the 10
-- slots ScreenGrid reports cooldowns for) whenever it changes so the
-- overlay can render the bar with proper icons.
--
-- Persistence: ASCIIMUDDB.knownSpells records every ID we've already
-- reported so we don't spam the chat log on every /reload.

local _, ns = ...
local SpellRegistry = {}
ns.SpellRegistry = SpellRegistry

local PREFIX = "ASCIIMUD~"
local ACTION_BAR_TICK = 5  -- seconds

local known = {}              -- [id] = true   (in-memory cache)
local lastBarSig = nil        -- string signature of last reported bar
local pendingFlush = false    -- coalesce multiple Observe() in one frame

local function emit(tbl)
    -- Keep the line short. WoW's chat frame truncates ~255 chars.
    local ok, j = pcall(ns.json.encode, tbl)
    if ok and j then
        print(PREFIX .. j)
    end
end

local function iconShortName(texturePath)
    if not texturePath then return nil end
    local s = tostring(texturePath)
    -- "Interface\\Icons\\Spell_Fire_Flamebolt"  ->  "spell_fire_flamebolt"
    -- Numeric file IDs are returned by some Classic patches; pass through.
    local tail = s:match("[^\\/]+$") or s
    return tail:lower()
end

local function inferSchool(iconName)
    if not iconName then return "physical" end
    local n = iconName:lower()
    if n:find("fire")    then return "fire"    end
    if n:find("frost")   then return "frost"   end
    if n:find("nature")  or n:find("lightning") or n:find("heal") then return "nature" end
    if n:find("shadow")  or n:find("death")     then return "shadow"  end
    if n:find("holy")    or n:find("light")     then return "holy"    end
    if n:find("arcane")  or n:find("magic")     then return "arcane"  end
    return "physical"
end

local function reportSpell(id)
    if not id or id == 0 or known[id] then return end
    known[id] = true
    if ASCIIMUDDB and ASCIIMUDDB.knownSpells then
        ASCIIMUDDB.knownSpells[id] = true
    end
    if not GetSpellInfo then return end
    local name, rank, icon, castTime = GetSpellInfo(id)
    if not name then return end
    local iconName = iconShortName(icon)
    emit({
        t        = "spell_meta",
        id       = id,
        name     = name,
        rank     = rank or "",
        icon     = iconName or "",
        school   = inferSchool(iconName),
        castMs   = castTime or 0,
    })
end

function SpellRegistry:Observe(id)
    if not id or id == 0 then return end
    if known[id] then return end
    -- Defer to next frame so we don't spam during a single snapshot.
    if pendingFlush then
        reportSpell(id)
    else
        pendingFlush = true
        local target = id
        C_Timer.After(0, function()
            pendingFlush = false
            reportSpell(target)
        end)
    end
end

function SpellRegistry:ObserveMany(ids)
    if not ids then return end
    for _, id in ipairs(ids) do
        if id and id ~= 0 then reportSpell(id) end
    end
end

local function pollActionBar()
    if not GetActionInfo then return end
    local slots = {}
    local sigParts = {}
    for slot = 1, 10 do
        local actionType, actionId = GetActionInfo(slot)
        local entry
        if actionType == "spell" and actionId and actionId ~= 0 then
            local name, _, icon = GetSpellInfo(actionId)
            entry = {
                slot = slot,
                type = "spell",
                id   = actionId,
                name = name or "?",
                icon = iconShortName(icon) or "",
            }
            reportSpell(actionId)
        elseif actionType == "macro" and actionId then
            local macroName, macroIcon = (GetMacroInfo and GetMacroInfo(actionId)) or "?"
            entry = {
                slot = slot,
                type = "macro",
                id   = actionId,
                name = macroName or "?",
                icon = iconShortName(macroIcon) or "",
            }
        elseif actionType == "item" and actionId then
            local itemName, _, _, _, _, _, _, _, _, itemIcon =
                GetItemInfo and GetItemInfo(actionId)
            entry = {
                slot = slot,
                type = "item",
                id   = actionId,
                name = itemName or "?",
                icon = iconShortName(itemIcon) or "",
            }
        else
            entry = { slot = slot, type = "empty" }
        end
        slots[slot] = entry
        sigParts[slot] = (entry.type or "?") .. ":" .. tostring(entry.id or 0)
    end
    local sig = table.concat(sigParts, "|")
    if sig == lastBarSig then return end
    lastBarSig = sig
    emit({ t = "action_bar", slots = slots })
end

function SpellRegistry:Init()
    -- Restore SavedVariables.
    if not ASCIIMUDDB then ASCIIMUDDB = {} end
    if not ASCIIMUDDB.knownSpells then ASCIIMUDDB.knownSpells = {} end
    for id, _ in pairs(ASCIIMUDDB.knownSpells) do
        known[tonumber(id) or 0] = true
    end

    -- First pass after the world settles, then every ACTION_BAR_TICK.
    C_Timer.After(3, pollActionBar)
    C_Timer.NewTicker(ACTION_BAR_TICK, pollActionBar)

    -- Re-poll on the obvious mutation events.
    local f = CreateFrame("Frame")
    f:RegisterEvent("ACTIONBAR_SLOT_CHANGED")
    f:RegisterEvent("UPDATE_BONUS_ACTIONBAR")
    f:RegisterEvent("PLAYER_ENTERING_WORLD")
    f:SetScript("OnEvent", function() C_Timer.After(0.5, pollActionBar) end)
end
