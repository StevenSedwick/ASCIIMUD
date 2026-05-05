-- ScreenGrid.lua : tick-flushed real-time data channel via screenshots.
--
-- v2 schema (Phase B). Grid is now 128 cols * 16 rows = 2048 bits = 256
-- bytes per tick (vs. 64 in v1). Bit-packed payload schema (must match
-- companion/screen_decoder.py):
--
-- ====== legacy bytes 0..62 (preserved 1:1 from v1) =========================
--   byte 0       magic 0xA5
--   byte 1       tick % 256
--   byte 2-3     hp                (u16 BE)
--   byte 4-5     hpMax             (u16 BE)
--   byte 6-7     mp                (u16 BE)
--   byte 8-9     mpMax             (u16 BE)
--   byte 10      bits 7..1: level (1-127), bit 0: resting
--   byte 11      bits 7..4: classID (1-11), bits 3..0: raceID (1-8)
--   byte 12      flags: combat/gender/faction/mounted/pvp/grouped/hasPet
--   byte 13      bits 7..1: xpPct, bit 0: rested-xp present
--   byte 14-15   zone hash (u16 BE)
--   byte 16      mapX (0-255)
--   byte 17      mapY (0-255)
--   byte 18      facing
--   byte 19      durability%<<1 | bag_full
--   byte 20-22   gold (u24 BE)
--   byte 23      bag free slots
--   byte 24-25   target hp           (u16)
--   byte 26-27   target hp max       (u16)
--   byte 28      target level<<1 | has_target
--   byte 29      target flags: hostile/isPlayer/classification(3b)
--   byte 30-31   target cast spell id (u16)
--   byte 32      target cast progress (0-100)
--   byte 33-34   player cast spell id (u16)
--   byte 35      player cast progress
--   byte 36-43   player buffs:    4 x u16 BE spell ids
--   byte 44-51   player debuffs:  4 x u16 BE spell ids
--   byte 52-61   action bar:      10 x u8 cooldown remaining seconds
--   byte 62      bits 7..5: combo, bits 4..2: powerType, bits 1..0: reserved
-- ====== v2 additions =======================================================
--   byte 63      schema_version (= 2). v1 used this byte for checksum;
--                v2 moves checksum to byte 255.
--   byte 64-73   quest 1: id u24, mapX, mapY, obj1..obj4 (each: hi-nib cur, lo-nib req,
--                                                          both 0..15), flags
--   byte 74-83   quest 2 (same shape)
--   byte 84-93   quest 3 (same shape)
--   byte 94-95   subzone hash u16
--   byte 96-97   world X (i16; raw WoW coord / 4 to fit signed range)
--   byte 98-99   world Y (i16)
--   byte 100     threat % (0-100; 0 if API unavailable)
--   byte 101     ambient flags:
--                  bit0 rare nearby      bit1 elite nearby     bit2 boss nearby
--                  bit3 enemy player nearby   bit4 player channeling
--                  bit5 target channeling     bit6 stealthed
--                  bit7 ghost (dead)
--   byte 102     pet hpPct (0-100; 0 if no pet)
--   byte 103     pet level (0-255; 0 if no pet)
--   byte 104     pet flags: bits 7..6 happiness(0-3), bit 5 exists,
--                bits 4..0 reserved
--   byte 105-106 reputation: tracked faction id u16 (0 = not tracked)
--   byte 107     reputation: bar % within current standing (0-100)
--   byte 108     reputation: bits 7..4 standing tier (1=Hated..8=Exalted)
--   byte 109     talent points tree 1
--   byte 110     talent points tree 2
--   byte 111     talent points tree 3
--   byte 112-116 skills: 5 x u8, value scaled to 0-255 (raw skill / 300 * 255)
--   byte 117     group: number of party members (0-4)
--   byte 118-120 mate1: classID<<4|raceID, level, hpPct
--   byte 121-123 mate2
--   byte 124-126 mate3
--   byte 127-129 mate4
--   byte 130-131 death: killer name hash u16 (0 = alive / no recent death)
--   byte 132-133 death: last damage spell id u16
--   byte 134     death: ticks since death (0 = alive, 255 = >=255 ticks)
--   byte 135-137 loot roll: item id u24 (0 = no active roll)
--   byte 138     loot roll: my roll value (0 = not rolling, 1-100)
--   byte 139-140 NPC chat: speaker name hash u16
--   byte 141-142 NPC chat: text hash u16
--   byte 143     NPC chat: ticks since (255 = none recent)
--   byte 144     NPC chat: type id (0=say,1=yell,2=emote,3=monster_party,4=whisper)
--   byte 145-146 player cast target name hash u16
--   byte 147-148 player cast total ms u16
--   byte 149-150 target cast target name hash u16
--   byte 151-152 target cast total ms u16
--   byte 153-170 bag samples: 6 x (item id u16 truncated, count u8)
--   byte 171-218 equipment: 16 slots x u24 item id  (slot order:
--                head, neck, shoulder, chest, waist, legs, feet, wrist,
--                hands, finger1, finger2, trinket1, trinket2, back,
--                mainHand, offHand)
--   byte 219-234 expanded buffs (slots 5..8): 4 x (id u16, stack u8, dur u8)
--   byte 235-250 expanded debuffs (slots 5..8): 4 x (id u16, stack u8, dur u8)
--   byte 251-254 reserved (zero-padded)
--   byte 255     checksum = sum(bytes 0..254) % 256

local _, ns = ...
local ScreenGrid = {}
ns.ScreenGrid = ScreenGrid

-- ----- Tunables ------------------------------------------------------------
local TICK_SECS    = 2.0
local CELL_PX      = 12
local GRID_COLS    = 128
local GRID_ROWS    = 16
local TOTAL_BYTES  = (GRID_COLS * GRID_ROWS) / 8       -- 256
local TOTAL_CELLS  = GRID_COLS * GRID_ROWS             -- 2048
local CORNER_OFF_X = 8
local CORNER_OFF_Y = 8
local QUIET_PX     = 12
local SCHEMA_VER   = 2

local SIZE_W = CELL_PX * GRID_COLS                     -- 1536 px
local SIZE_H = CELL_PX * GRID_ROWS                     -- 192 px

-- Throttle expensive scans (multiple of TICK_SECS)
local EQUIP_REFRESH_TICKS  = 5     -- 10 s
local TALENT_REFRESH_TICKS = 30    -- 60 s
local SKILL_REFRESH_TICKS  = 30    -- 60 s
local QUEST_REFRESH_TICKS  = 3     -- 6 s
local BAG_REFRESH_TICKS    = 5     -- 10 s
local NEARBY_REFRESH_TICKS = 5     -- 10 s

-- ----- Module state --------------------------------------------------------
local frame, cells, ticker
local tickCounter = 0
local byteBuf = {}            -- byte index -> 0..255 (source of truth for checksum)
for i = 0, TOTAL_BYTES - 1 do byteBuf[i] = 0 end

-- Cached scan results (refreshed at their own cadences)
local cachedEquip   = {}      -- 16 itemIDs
local cachedTalents = {0,0,0}
local cachedSkills  = {0,0,0,0,0}
local cachedQuests  = {{},{},{}}
local cachedBag     = {}      -- 6 entries: {id,count}
local cachedNearby  = 0       -- ambient flag bits 0..3 (rare/elite/boss/enemyPlayer)

-- Ephemeral state captured by event handlers
local lastDeath = { killerHash = 0, spellId = 0, deathTick = nil }
local lastDamageToPlayer = { sourceName = nil, spellId = 0 }
local lastNpcChat = { nameHash = 0, textHash = 0, tick = nil, kind = 0 }
local lastLootRoll = { itemId = 0, myRoll = 0 }
local lastCastTarget = { player = 0, target = 0,
                          playerTotalMs = 0, targetTotalMs = 0 }

-- ----- Bit helpers ---------------------------------------------------------
local function setCellBit(idx, bit)
    local cell = cells[idx + 1]
    if bit == 1 then
        cell:SetColorTexture(1, 1, 1, 1)
    else
        cell:SetColorTexture(0, 0, 0, 1)
    end
end

local function setByte(byteIdx, value)
    value = math.floor(value or 0) % 256
    byteBuf[byteIdx] = value
    for b = 0, 7 do
        local bit = math.floor(value / (2 ^ (7 - b))) % 2
        setCellBit(byteIdx * 8 + b, bit)
    end
end

local function setU16(byteIdx, value)
    value = math.floor(value or 0) % 65536
    setByte(byteIdx,     math.floor(value / 256))
    setByte(byteIdx + 1, value % 256)
end

local function setU24(byteIdx, value)
    value = math.floor(value or 0) % 16777216
    setByte(byteIdx,     math.floor(value / 65536))
    setByte(byteIdx + 1, math.floor(value / 256) % 256)
    setByte(byteIdx + 2, value % 256)
end

local function setI16(byteIdx, value)
    value = math.floor(value or 0)
    if value < -32768 then value = -32768 end
    if value >  32767 then value =  32767 end
    if value < 0 then value = value + 65536 end
    setU16(byteIdx, value)
end

-- Polynomial hash matching companion's hash16().
local function hash16(s)
    local h = 0
    if not s or s == "" then return 0 end
    for i = 1, #s do
        h = (h * 31 + s:byte(i)) % 65536
    end
    return h
end

-- ----- Frame setup ---------------------------------------------------------
local function build()
    if frame then return end
    frame = CreateFrame("Frame", "ASCIIMUDGrid", UIParent)
    frame:SetScale(1 / UIParent:GetEffectiveScale())
    frame:SetSize(SIZE_W, SIZE_H)
    frame:SetPoint("BOTTOMRIGHT", UIParent, "BOTTOMRIGHT", -CORNER_OFF_X, CORNER_OFF_Y)
    frame:SetFrameStrata("TOOLTIP")

    local bg = frame:CreateTexture(nil, "BACKGROUND")
    bg:SetColorTexture(0, 0, 0, 1)
    bg:SetPoint("TOPLEFT",     -QUIET_PX,  QUIET_PX)
    bg:SetPoint("BOTTOMRIGHT",  QUIET_PX, -QUIET_PX)
    frame.bg = bg

    cells = {}
    for row = 0, GRID_ROWS - 1 do
        for col = 0, GRID_COLS - 1 do
            local idx = row * GRID_COLS + col
            local t = frame:CreateTexture(nil, "OVERLAY")
            t:SetSize(CELL_PX, CELL_PX)
            t:SetPoint("TOPLEFT", frame, "TOPLEFT",
                       col * CELL_PX, -row * CELL_PX)
            t:SetColorTexture(0, 0, 0, 1)
            cells[idx + 1] = t
        end
    end
end

-- ----- Lookup tables -------------------------------------------------------
local CLASS_ID = {
    WARRIOR = 1, PALADIN = 2, HUNTER = 3, ROGUE = 4, PRIEST = 5,
    SHAMAN = 7, MAGE = 8, WARLOCK = 9, DRUID = 11,
}
local RACE_ID = {
    Human = 1, Orc = 2, Dwarf = 3, NightElf = 4, Scourge = 5,
    Tauren = 6, Gnome = 7, Troll = 8,
}
local CLASSIFICATION_ID = {
    normal = 0, elite = 1, rareelite = 2, rare = 3,
    worldboss = 4, trivial = 5, minus = 6,
}
local CHAT_KIND = {
    SAY = 0, YELL = 1, EMOTE = 2, PARTY = 3, WHISPER = 4,
}
-- Equipment slot order matches schema docstring above
local EQUIP_SLOT_IDS = { 1, 2, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17 }

-- ----- Helpers -------------------------------------------------------------
local function safeUnit(fn, ...)
    local ok, a, b, c = pcall(fn, ...)
    if ok then return a, b, c end
end

local function getMapPos()
    if not C_Map or not C_Map.GetBestMapForUnit then return 127, 127 end
    local mapID = safeUnit(C_Map.GetBestMapForUnit, "player")
    if not mapID then return 127, 127 end
    local pos = safeUnit(C_Map.GetPlayerMapPosition, mapID, "player")
    if not pos then return 127, 127 end
    local px, py = pos:GetXY()
    if not px or not py then return 127, 127 end
    if px < 0 then px = 0 elseif px > 1 then px = 1 end
    if py < 0 then py = 0 elseif py > 1 then py = 1 end
    return math.floor(px * 255), math.floor(py * 255)
end

local function getWorldPos()
    -- Classic Era exposes coords via the player position table.
    -- Fallback: use C_Map mapX*100 / mapY*100 scaled (no real world coords).
    local mapID = C_Map and C_Map.GetBestMapForUnit and
                  safeUnit(C_Map.GetBestMapForUnit, "player")
    if not mapID then return 0, 0 end
    if not C_Map.GetWorldPosFromMapPos then return 0, 0 end
    local pos = safeUnit(C_Map.GetPlayerMapPosition, mapID, "player")
    if not pos then return 0, 0 end
    -- Convert mapPos -> world
    local _, world = safeUnit(C_Map.GetWorldPosFromMapPos, mapID, pos)
    if not world then return 0, 0 end
    local wx, wy = world:GetXY()
    if not wx or not wy then return 0, 0 end
    -- WoW world coords are roughly +/- 17000; divide by 4 to fit i16.
    return math.floor(wx / 4), math.floor(wy / 4)
end

local function topAuras(unit, helpful, fromIdx, count)
    local ids   = {}
    local stacks= {}
    local durs  = {}
    for i = 1, count do ids[i] = 0; stacks[i] = 0; durs[i] = 0 end
    local fn = helpful and UnitBuff or UnitDebuff
    if not fn then return ids, stacks, durs end
    for i = 1, count do
        local realIdx = fromIdx + i - 1
        local _, _, c, _, _, expire, _, _, _, sId = fn(unit, realIdx)
        if sId then
            ids[i] = sId % 65536
            stacks[i] = math.min(255, math.max(0, c or 0))
            if expire and expire > 0 then
                local rem = expire - GetTime()
                if rem < 0 then rem = 0 end
                if rem > 255 then rem = 255 end
                durs[i] = math.floor(rem)
            end
        end
    end
    return ids, stacks, durs
end

local function actionBarCooldowns()
    local out = {0,0,0,0,0,0,0,0,0,0}
    if not GetActionInfo or not GetActionCooldown then return out end
    for slot = 1, 10 do
        local start, duration = GetActionCooldown(slot)
        if start and duration and duration > 1.5 then
            local remain = (start + duration) - GetTime()
            if remain < 0 then remain = 0
            elseif remain > 255 then remain = 255 end
            out[slot] = math.floor(remain)
        end
    end
    return out
end

local function castInfo(unit)
    -- Returns spellId, progressPct, totalMs, targetNameHash
    local spellId, progressPct, totalMs, targetHash = 0, 0, 0, 0
    if not UnitCastingInfo then return spellId, progressPct, totalMs, targetHash end
    local _, _, _, startMs, endMs, _, _, _, sId = UnitCastingInfo(unit)
    local channel = false
    if not sId and UnitChannelInfo then
        local _, _, _, sMs, eMs, _, _, _, csId = UnitChannelInfo(unit)
        if csId then sId, startMs, endMs, channel = csId, sMs, eMs, true end
    end
    if not sId then return spellId, progressPct, totalMs, targetHash end
    spellId = sId % 65536
    local now = GetTime() * 1000
    local total = (endMs or now) - (startMs or now)
    if total > 0 then
        totalMs = math.min(65535, math.floor(total))
        local elapsed = now - (startMs or now)
        if channel then elapsed = total - (now - (startMs or now)) end
        progressPct = math.floor((elapsed / total) * 100)
        if progressPct < 0 then progressPct = 0
        elseif progressPct > 100 then progressPct = 100 end
    end
    -- Target hint: if "player" cast, use UnitName("target"); for "target" cast,
    -- UnitName("targettarget").
    local nameRef = (unit == "player") and "target" or "targettarget"
    local nm = UnitName and UnitName(nameRef)
    if nm then targetHash = hash16(nm) end
    return spellId, progressPct, totalMs, targetHash
end

-- ----- Throttled scans -----------------------------------------------------
local function scanEquipment()
    local out = {}
    if not GetInventoryItemID then
        for i = 1, 16 do out[i] = 0 end
        return out
    end
    for i, slotId in ipairs(EQUIP_SLOT_IDS) do
        out[i] = (GetInventoryItemID("player", slotId) or 0) % 16777216
    end
    return out
end

local function scanTalents()
    local out = {0, 0, 0}
    if not GetTalentTabInfo then return out end
    for tab = 1, 3 do
        local ok, _, _, ps = pcall(GetTalentTabInfo, tab)
        if ok and ps then
            out[tab] = math.min(99, math.max(0, ps))
        end
    end
    return out
end

local function scanSkills()
    local out = {0, 0, 0, 0, 0}
    if not GetNumSkillLines or not GetSkillLineInfo then return out end
    local picked = 0
    for i = 1, GetNumSkillLines() do
        if picked >= 5 then break end
        local ok, _, header, _, currentRank = pcall(GetSkillLineInfo, i)
        if ok and not header and currentRank and currentRank > 0 then
            picked = picked + 1
            out[picked] = math.min(255, math.floor((currentRank / 300) * 255))
        end
    end
    return out
end

local function questObjRatio(cur, req)
    if not req or req == 0 then return 0 end
    local c = math.floor((cur / req) * 15)
    if c < 0 then c = 0 elseif c > 15 then c = 15 end
    local r = math.min(15, req)
    return c * 16 + r
end

local function scanQuests()
    local out = {{},{},{}}
    if not GetNumQuestLogEntries then return out end
    local picked = 0
    local n = GetNumQuestLogEntries()
    for idx = 1, n do
        if picked >= 3 then break end
        local title, _, _, isHeader, _, isComplete, _, questID =
            GetQuestLogTitle(idx)
        if title and not isHeader then
            picked = picked + 1
            local objs = {0, 0, 0, 0}
            if GetNumQuestLeaderBoards and GetQuestLogLeaderBoard then
                local nb = GetNumQuestLeaderBoards(idx) or 0
                for o = 1, math.min(4, nb) do
                    local text, _, finished = GetQuestLogLeaderBoard(o, idx)
                    if text then
                        local cur, req = string.match(text, "(%d+)%s*/%s*(%d+)")
                        if cur and req then
                            objs[o] = questObjRatio(tonumber(cur), tonumber(req))
                        elseif finished then
                            objs[o] = questObjRatio(1, 1)
                        end
                    end
                end
            end
            local flags = 0
            if isComplete and isComplete > 0 then flags = flags + 128 end
            out[picked] = {
                id    = (questID or 0) % 16777216,
                mapX  = 0, mapY = 0,
                obj1  = objs[1], obj2 = objs[2],
                obj3  = objs[3], obj4 = objs[4],
                flags = flags,
            }
        end
    end
    for i = 1, 3 do
        if not out[i].id then
            out[i] = { id=0, mapX=0, mapY=0, obj1=0, obj2=0, obj3=0, obj4=0, flags=0 }
        end
    end
    return out
end

local function scanBag()
    local out = {{0,0},{0,0},{0,0},{0,0},{0,0},{0,0}}
    local picked = 0
    local entries = {}
    local container = C_Container or _G
    local getInfo = (C_Container and C_Container.GetContainerItemInfo) or
                    GetContainerItemInfo
    local numSlots = (C_Container and C_Container.GetContainerNumSlots) or
                    GetContainerNumSlots
    if not numSlots or not getInfo then return out end
    for bag = 0, 4 do
        local n = numSlots(bag) or 0
        for slot = 1, n do
            local info
            if C_Container and C_Container.GetContainerItemInfo then
                local ok, r = pcall(C_Container.GetContainerItemInfo, bag, slot)
                if ok and r then
                    info = { itemID = r.itemID, count = r.stackCount or 1 }
                end
            else
                local _, count, _, _, _, _, _, _, _, itemID = pcall(GetContainerItemInfo, bag, slot)
                if count and itemID then info = { itemID = itemID, count = count } end
            end
            if info and info.itemID then
                entries[#entries + 1] = info
            end
        end
    end
    -- Sort by stack size desc, take top 6
    table.sort(entries, function(a, b)
        return (a.count or 0) > (b.count or 0)
    end)
    for i = 1, math.min(6, #entries) do
        out[i] = { entries[i].itemID % 65536, math.min(255, entries[i].count or 1) }
    end
    return out
end

local function scanNearbyAmbient()
    -- Cheap: examine target/mouseover classification + nameplate units.
    local flags = 0
    local function check(unit)
        if not UnitExists or not UnitExists(unit) then return end
        local cls = (UnitClassification and UnitClassification(unit)) or "normal"
        if cls == "rare" or cls == "rareelite" then flags = bit.bor(flags, 1) end
        if cls == "elite" then flags = bit.bor(flags, 2) end
        if cls == "worldboss" then flags = bit.bor(flags, 4) end
        if UnitIsPlayer and UnitIsPlayer(unit) and UnitCanAttack and
           UnitCanAttack("player", unit) then
            flags = bit.bor(flags, 8)
        end
    end
    check("target")
    check("mouseover")
    for i = 1, 5 do check("nameplate" .. i) end
    return flags
end

-- ----- Event capture: damage / death / chat / loot -------------------------
local eventFrame
local function setupEvents()
    if eventFrame then return end
    eventFrame = CreateFrame("Frame")
    eventFrame:RegisterEvent("COMBAT_LOG_EVENT_UNFILTERED")
    eventFrame:RegisterEvent("PLAYER_DEAD")
    eventFrame:RegisterEvent("PLAYER_ALIVE")
    eventFrame:RegisterEvent("PLAYER_UNGHOST")
    eventFrame:RegisterEvent("CHAT_MSG_MONSTER_SAY")
    eventFrame:RegisterEvent("CHAT_MSG_MONSTER_YELL")
    eventFrame:RegisterEvent("CHAT_MSG_MONSTER_EMOTE")
    eventFrame:RegisterEvent("CHAT_MSG_MONSTER_PARTY")
    eventFrame:RegisterEvent("CHAT_MSG_MONSTER_WHISPER")
    eventFrame:RegisterEvent("START_LOOT_ROLL")
    eventFrame:RegisterEvent("CONFIRM_LOOT_ROLL")
    eventFrame:RegisterEvent("LOOT_ROLLS_COMPLETE")

    eventFrame:SetScript("OnEvent", function(_, event, ...)
        if event == "COMBAT_LOG_EVENT_UNFILTERED" then
            local args = { CombatLogGetCurrentEventInfo() }
            -- args[2]=subevent, args[7]=destGUID, args[9]=destName
            -- args[5]=sourceName, args[12]=spellId (for SPELL_ events)
            local sub = args[2]
            local destGUID = args[8]
            if destGUID == UnitGUID("player") then
                if sub and sub:find("DAMAGE") then
                    lastDamageToPlayer.sourceName = args[5]
                    if sub:sub(1, 6) == "SPELL_" then
                        lastDamageToPlayer.spellId = (args[12] or 0) % 65536
                    end
                end
            end
        elseif event == "PLAYER_DEAD" then
            lastDeath.killerHash = hash16(lastDamageToPlayer.sourceName or "")
            lastDeath.spellId    = lastDamageToPlayer.spellId or 0
            lastDeath.deathTick  = tickCounter
        elseif event == "PLAYER_ALIVE" or event == "PLAYER_UNGHOST" then
            -- Keep death visible for a short time, then it ages out via tick diff.
        elseif event == "CHAT_MSG_MONSTER_SAY" then
            local msg, sender = ...
            lastNpcChat = { nameHash = hash16(sender or ""), textHash = hash16(msg or ""), tick = tickCounter, kind = CHAT_KIND.SAY }
        elseif event == "CHAT_MSG_MONSTER_YELL" then
            local msg, sender = ...
            lastNpcChat = { nameHash = hash16(sender or ""), textHash = hash16(msg or ""), tick = tickCounter, kind = CHAT_KIND.YELL }
        elseif event == "CHAT_MSG_MONSTER_EMOTE" then
            local msg, sender = ...
            lastNpcChat = { nameHash = hash16(sender or ""), textHash = hash16(msg or ""), tick = tickCounter, kind = CHAT_KIND.EMOTE }
        elseif event == "CHAT_MSG_MONSTER_PARTY" then
            local msg, sender = ...
            lastNpcChat = { nameHash = hash16(sender or ""), textHash = hash16(msg or ""), tick = tickCounter, kind = CHAT_KIND.PARTY }
        elseif event == "CHAT_MSG_MONSTER_WHISPER" then
            local msg, sender = ...
            lastNpcChat = { nameHash = hash16(sender or ""), textHash = hash16(msg or ""), tick = tickCounter, kind = CHAT_KIND.WHISPER }
        elseif event == "START_LOOT_ROLL" then
            local rollID = ...
            local _, _, _, _, _, _, _, _ = GetLootRollItemInfo and GetLootRollItemInfo(rollID)
            local link = GetLootRollItemLink and GetLootRollItemLink(rollID)
            if link then
                local idStr = link:match("item:(%d+):")
                lastLootRoll.itemId = tonumber(idStr) or 0
                lastLootRoll.myRoll = 0
            end
        elseif event == "CONFIRM_LOOT_ROLL" then
            local _, rollType = ...
            -- rollType: 1=need, 2=greed, 3=disenchant; map to a token roll value
            lastLootRoll.myRoll = (rollType or 0) * 33
        elseif event == "LOOT_ROLLS_COMPLETE" then
            lastLootRoll = { itemId = 0, myRoll = 0 }
        end
    end)
end

-- Difference between current tick and a captured tick, accounting for wrap.
local function ticksSince(stamp)
    if not stamp then return 255 end
    local d = tickCounter - stamp
    if d < 0 then d = d + 256 end
    if d > 255 then d = 255 end
    return d
end

-- ----- Encode --------------------------------------------------------------
local function encodeSnapshot()
    tickCounter = (tickCounter + 1) % 256

    -- ====== legacy fields (bytes 0..62) ====================================
    local hp     = UnitHealth("player")    or 0
    local hpMax  = UnitHealthMax("player") or 0
    local mp     = UnitPower("player")     or 0
    local mpMax  = UnitPowerMax("player")  or 0
    if hp > 65535 then hp = 65535 end
    if hpMax > 65535 then hpMax = 65535 end
    if mp > 65535 then mp = 65535 end
    if mpMax > 65535 then mpMax = 65535 end

    local level = UnitLevel("player") or 1
    if level < 1 then level = 1 end
    if level > 127 then level = 127 end

    local _, classToken, classID = UnitClass("player")
    if not classID then classID = CLASS_ID[classToken or ""] or 0 end
    local _, raceToken = UnitRace("player")
    local raceID = RACE_ID[(raceToken or ""):gsub("%s", "")] or 0

    local genderIdx = (UnitSex and UnitSex("player")) or 1
    local gender = (genderIdx == 3) and 1 or 0
    local factionGroup = UnitFactionGroup("player")
    local faction = (factionGroup == "Horde") and 1 or 0
    local mounted = (IsMounted and IsMounted()) and 1 or 0
    local pvp = (UnitIsPVP and UnitIsPVP("player")) and 1 or 0
    local grouped = (IsInGroup and IsInGroup()) and 1 or 0
    local hasPet  = (UnitExists and UnitExists("pet")) and 1 or 0
    local inCombat = UnitAffectingCombat("player") and 1 or 0
    local resting  = (IsResting and IsResting()) and 1 or 0

    local xp     = UnitXP and UnitXP("player") or 0
    local xpMax  = UnitXPMax and UnitXPMax("player") or 0
    local xpPct  = (xpMax > 0) and math.floor((xp / xpMax) * 100) or 0
    if xpPct > 100 then xpPct = 100 end
    local restedXP = (GetXPExhaustion and (GetXPExhaustion() or 0) > 0) and 1 or 0

    local zoneName = GetZoneText() or ""
    local zoneHash = hash16(zoneName)
    local subzoneName = (GetSubZoneText and GetSubZoneText()) or ""
    local subzoneHash = hash16(subzoneName)
    local mapX, mapY = getMapPos()
    local worldX, worldY = getWorldPos()
    local facing = 0
    if GetPlayerFacing then
        local f = GetPlayerFacing() or 0
        facing = math.floor((f / (2 * math.pi)) * 256) % 256
    end

    local money = GetMoney and GetMoney() or 0
    local goldPieces = math.floor(money / 10000)
    if goldPieces > 16777215 then goldPieces = 16777215 end

    local freeSlots = 0
    local numFreeFn = (C_Container and C_Container.GetContainerNumFreeSlots) or
                      GetContainerNumFreeSlots
    if numFreeFn then
        for bag = 0, 4 do
            local n = numFreeFn(bag) or 0
            freeSlots = freeSlots + n
        end
    end
    if freeSlots > 255 then freeSlots = 255 end
    local bagFull = (freeSlots == 0) and 1 or 0

    local dura = 100
    if GetInventoryItemDurability then
        local total, totalMax = 0, 0
        for slot = 1, 18 do
            local cur, max = GetInventoryItemDurability(slot)
            if cur and max and max > 0 then
                total = total + cur
                totalMax = totalMax + max
            end
        end
        if totalMax > 0 then dura = math.floor((total / totalMax) * 100) end
    end
    if dura > 100 then dura = 100 end
    if dura < 0 then dura = 0 end

    local hasTarget = UnitExists("target") and 1 or 0
    local tHp, tHpMax, tLevel = 0, 0, 0
    local tHostile, tIsPlayer, tClass = 0, 0, 0
    if hasTarget == 1 then
        tHp    = UnitHealth("target") or 0
        tHpMax = UnitHealthMax("target") or 0
        if tHp > 65535 then tHp = 65535 end
        if tHpMax > 65535 then tHpMax = 65535 end
        local lvl = UnitLevel("target") or 0
        if lvl < 0 then lvl = 0 end
        if lvl > 99 then lvl = 99 end
        tLevel = lvl
        tHostile  = UnitCanAttack("player", "target") and 1 or 0
        tIsPlayer = UnitIsPlayer("target") and 1 or 0
        local cls = (UnitClassification and UnitClassification("target")) or "normal"
        tClass = CLASSIFICATION_ID[cls] or 0
    end

    local pCastSpell, pCastProgress, pCastTotalMs, pCastTargetHash = castInfo("player")
    local tCastSpell, tCastProgress, tCastTotalMs, tCastTargetHash = 0, 0, 0, 0
    if hasTarget == 1 then
        tCastSpell, tCastProgress, tCastTotalMs, tCastTargetHash = castInfo("target")
    end

    local buffs1, _, _ = topAuras("player", true, 1, 4)
    local debuffs1, _, _ = topAuras("player", false, 1, 4)
    local buffs2, buffStacks2, buffDurs2   = topAuras("player", true, 5, 4)
    local debuffs2, debuffStacks2, debuffDurs2 = topAuras("player", false, 5, 4)

    if ns.SpellRegistry then
        if pCastSpell ~= 0 then ns.SpellRegistry:Observe(pCastSpell) end
        if tCastSpell ~= 0 then ns.SpellRegistry:Observe(tCastSpell) end
        ns.SpellRegistry:ObserveMany(buffs1)
        ns.SpellRegistry:ObserveMany(debuffs1)
        ns.SpellRegistry:ObserveMany(buffs2)
        ns.SpellRegistry:ObserveMany(debuffs2)
    end

    local cds = actionBarCooldowns()

    local combo = (GetComboPoints and GetComboPoints("player", "target")) or 0
    if combo > 7 then combo = 7 end
    local powerType = UnitPowerType and UnitPowerType("player") or 0
    if powerType > 7 then powerType = 0 end

    -- ====== throttled scans (refreshed every N ticks) ======================
    if (tickCounter % EQUIP_REFRESH_TICKS) == 0 or #cachedEquip == 0 then
        cachedEquip = scanEquipment()
    end
    if (tickCounter % TALENT_REFRESH_TICKS) == 0 or cachedTalents[1] == nil then
        cachedTalents = scanTalents()
    end
    if (tickCounter % SKILL_REFRESH_TICKS) == 0 then
        cachedSkills = scanSkills()
    end
    if (tickCounter % QUEST_REFRESH_TICKS) == 0 then
        cachedQuests = scanQuests()
    end
    if (tickCounter % BAG_REFRESH_TICKS) == 0 then
        cachedBag = scanBag()
    end
    if (tickCounter % NEARBY_REFRESH_TICKS) == 0 then
        cachedNearby = scanNearbyAmbient()
    end

    -- ambient flags (compose final byte 101)
    local ambient = cachedNearby
    -- player channeling
    if UnitChannelInfo and UnitChannelInfo("player") then
        ambient = bit.bor(ambient, 16)
    end
    if UnitChannelInfo and hasTarget == 1 and UnitChannelInfo("target") then
        ambient = bit.bor(ambient, 32)
    end
    if (HasFullControl and not HasFullControl()) or
       (UnitIsGhost and UnitIsGhost("player")) then
        ambient = bit.bor(ambient, 128)
    end

    -- threat
    local threatPct = 0
    if UnitThreatSituation and hasTarget == 1 then
        local sit = UnitThreatSituation("player", "target")
        if sit then threatPct = math.min(100, sit * 33) end
    end

    -- pet
    local petHpPct, petLevel, petHappiness = 0, 0, 0
    if UnitExists("pet") then
        local pH, pHM = UnitHealth("pet") or 0, UnitHealthMax("pet") or 1
        petHpPct = math.floor((pH / math.max(1, pHM)) * 100)
        petLevel = math.min(255, UnitLevel("pet") or 0)
        if GetPetHappiness then
            local h = GetPetHappiness()
            if h then petHappiness = math.min(3, h) end
        end
    end

    -- reputation
    local repFactionId, repBarPct, repTier = 0, 0, 0
    if GetWatchedFactionInfo then
        local name, standing, barMin, barMax, barValue, factionID =
            GetWatchedFactionInfo()
        if name and barMax and barMax > barMin then
            repBarPct = math.floor(((barValue - barMin) / (barMax - barMin)) * 100)
            if repBarPct < 0 then repBarPct = 0 elseif repBarPct > 100 then repBarPct = 100 end
            repTier = math.min(8, math.max(0, standing or 0))
            repFactionId = (factionID or hash16(name)) % 65536
        end
    end

    -- group
    local mateData = {{0,0,0},{0,0,0},{0,0,0},{0,0,0}}
    local memberCount = 0
    for i = 1, 4 do
        local unit = "party" .. i
        if UnitExists(unit) then
            memberCount = memberCount + 1
            local _, mClassToken, mClassID = UnitClass(unit)
            if not mClassID then mClassID = CLASS_ID[mClassToken or ""] or 0 end
            local _, mRaceToken = UnitRace(unit)
            local mRaceID = RACE_ID[(mRaceToken or ""):gsub("%s", "")] or 0
            local mLvl = math.min(255, UnitLevel(unit) or 0)
            local mH, mHM = UnitHealth(unit) or 0, UnitHealthMax(unit) or 1
            local mHpPct = math.floor((mH / math.max(1, mHM)) * 100)
            mateData[i] = { mClassID * 16 + mRaceID, mLvl, mHpPct }
        end
    end

    -- ====== write all bytes ================================================
    setByte(0, 0xA5)
    setByte(1, tickCounter)
    setU16(2,  hp);  setU16(4, hpMax)
    setU16(6,  mp);  setU16(8, mpMax)
    setByte(10, level * 2 + resting)
    setByte(11, classID * 16 + raceID)
    local flags12 = inCombat*128 + gender*64 + faction*32 + mounted*16 +
                    pvp*8 + grouped*4 + hasPet*2
    setByte(12, flags12)
    setByte(13, xpPct * 2 + restedXP)
    setU16(14, zoneHash)
    setByte(16, mapX); setByte(17, mapY); setByte(18, facing)
    setByte(19, dura * 2 + bagFull)
    setU24(20, goldPieces)
    setByte(23, freeSlots)
    setU16(24, tHp); setU16(26, tHpMax)
    setByte(28, tLevel * 2 + hasTarget)
    local flags29 = tHostile*128 + tIsPlayer*64 + (tClass % 8) * 8
    setByte(29, flags29)
    setU16(30, tCastSpell); setByte(32, tCastProgress)
    setU16(33, pCastSpell); setByte(35, pCastProgress)
    for i = 1, 4 do setU16(34 + i*2, buffs1[i]) end
    for i = 1, 4 do setU16(42 + i*2, debuffs1[i]) end
    for i = 1, 10 do setByte(51 + i, cds[i]) end
    setByte(62, combo * 32 + (powerType % 8) * 4)

    -- ====== v2 fields ======================================================
    setByte(63, SCHEMA_VER)

    -- Quests (3 x 10 bytes)
    for q = 1, 3 do
        local base = 64 + (q - 1) * 10
        local qd = cachedQuests[q] or { id=0, mapX=0, mapY=0,
                                        obj1=0, obj2=0, obj3=0, obj4=0, flags=0 }
        setU24(base, qd.id)
        setByte(base + 3, qd.mapX)
        setByte(base + 4, qd.mapY)
        setByte(base + 5, qd.obj1)
        setByte(base + 6, qd.obj2)
        setByte(base + 7, qd.obj3)
        setByte(base + 8, qd.obj4)
        setByte(base + 9, qd.flags)
    end

    setU16(94, subzoneHash)
    setI16(96, worldX)
    setI16(98, worldY)
    setByte(100, math.min(100, threatPct))
    setByte(101, ambient)

    setByte(102, petHpPct)
    setByte(103, petLevel)
    setByte(104, petHappiness * 64 + (UnitExists("pet") and 32 or 0))

    setU16(105, repFactionId)
    setByte(107, repBarPct)
    setByte(108, repTier * 16)

    setByte(109, cachedTalents[1] or 0)
    setByte(110, cachedTalents[2] or 0)
    setByte(111, cachedTalents[3] or 0)
    for i = 1, 5 do setByte(111 + i, cachedSkills[i] or 0) end

    setByte(117, math.min(4, memberCount))
    for m = 1, 4 do
        local base = 118 + (m - 1) * 3
        local md = mateData[m]
        setByte(base,     md[1])
        setByte(base + 1, md[2])
        setByte(base + 2, md[3])
    end

    -- Death recap
    setU16(130, lastDeath.killerHash or 0)
    setU16(132, lastDeath.spellId or 0)
    setByte(134, lastDeath.deathTick and ticksSince(lastDeath.deathTick) or 0)

    -- Loot
    setU24(135, lastLootRoll.itemId or 0)
    setByte(138, lastLootRoll.myRoll or 0)

    -- NPC chat
    setU16(139, lastNpcChat.nameHash or 0)
    setU16(141, lastNpcChat.textHash or 0)
    setByte(143, ticksSince(lastNpcChat.tick))
    setByte(144, lastNpcChat.kind or 0)

    -- Cast targets + totals
    setU16(145, pCastTargetHash)
    setU16(147, pCastTotalMs)
    setU16(149, tCastTargetHash)
    setU16(151, tCastTotalMs)

    -- Bag samples (6 entries: 2 bytes id + 1 byte count = 3 bytes each)
    for i = 1, 6 do
        local base = 153 + (i - 1) * 3
        local b = cachedBag[i] or {0, 0}
        setU16(base, b[1] or 0)
        setByte(base + 2, b[2] or 0)
    end

    -- Equipment (16 slots x u24)
    for i = 1, 16 do
        setU24(171 + (i - 1) * 3, cachedEquip[i] or 0)
    end

    -- Expanded buffs/debuffs (4 each x (id u16 + stack u8 + dur u8) = 4 bytes)
    for i = 1, 4 do
        local base = 219 + (i - 1) * 4
        setU16(base, buffs2[i] or 0)
        setByte(base + 2, buffStacks2[i] or 0)
        setByte(base + 3, buffDurs2[i] or 0)
    end
    for i = 1, 4 do
        local base = 235 + (i - 1) * 4
        setU16(base, debuffs2[i] or 0)
        setByte(base + 2, debuffStacks2[i] or 0)
        setByte(base + 3, debuffDurs2[i] or 0)
    end

    -- Reserved (251..254) zero-filled
    for i = 251, 254 do setByte(i, 0) end

    -- Checksum over bytes 0..254 (using buffer set by every setByte call).
    local sum = 0
    for byteIdx = 0, 254 do
        sum = sum + (byteBuf[byteIdx] or 0)
    end
    setByte(255, sum % 256)
end

local function tick()
    if not frame:IsShown() then return end
    encodeSnapshot()
    C_Timer.After(0, function() Screenshot() end)
end

-- ----- Public --------------------------------------------------------------
function ScreenGrid:Init()
    build()
    setupEvents()
    pcall(SetCVar, "screenshotFormat", "jpg")
    pcall(SetCVar, "screenshotQuality", "1")
    if UIErrorsFrame and UIErrorsFrame.UnregisterEvent then
        pcall(UIErrorsFrame.UnregisterEvent, UIErrorsFrame, "SCREENSHOT_SUCCEEDED")
        pcall(UIErrorsFrame.UnregisterEvent, UIErrorsFrame, "SCREENSHOT_FAILED")
    end
    if ticker then ticker:Cancel() end
    ticker = C_Timer.NewTicker(TICK_SECS, tick)
    print(string.format(
        "|cff66ccffASCIIMUD|r: screen grid v%d %dx%d (%d bytes/tick) every %.1fs.",
        SCHEMA_VER, GRID_COLS, GRID_ROWS, TOTAL_BYTES, TICK_SECS))
end

function ScreenGrid:Show()  if frame then frame:Show() end end
function ScreenGrid:Hide()  if frame then frame:Hide() end end
function ScreenGrid:Toggle()
    if not frame then return end
    if frame:IsShown() then frame:Hide() else frame:Show() end
end
