-- ScreenGrid.lua : tick-flushed real-time data channel via screenshots.
--
-- Renders a black/white "QR-like" data grid in a corner of the WoW screen.
-- A screenshot is taken every TICK_SECS, and the companion process samples
-- the cells to recover the encoded state.
--
-- Grid is 64 cols × 8 rows = 512 bits = 64 bytes per tick. Bit-packed
-- payload schema (must match companion/screen_decoder.py):
--
--   byte 0       magic 0xA5
--   byte 1       tick % 256
--   byte 2-3     hp                (u16 BE)
--   byte 4-5     hpMax             (u16 BE)
--   byte 6-7     mp                (u16 BE)
--   byte 8-9     mpMax             (u16 BE)
--   byte 10      bits 7..1: level (1-127), bit 0: resting
--   byte 11      bits 7..4: classID (1-11), bits 3..0: raceID (1-8)
--   byte 12      flags:
--                   bit 7 = in_combat
--                   bit 6 = gender (0=male,1=female)
--                   bit 5 = faction (0=alliance,1=horde)
--                   bit 4 = mounted
--                   bit 3 = pvp_flagged
--                   bit 2 = grouped (in party/raid)
--                   bit 1 = has_pet
--                   bit 0 = (reserved)
--   byte 13      bits 7..1: xpPct (0..100), bit 0: rested-xp present
--   byte 14-15   zone hash (u16 BE, polynomial hash of GetZoneText())
--   byte 16      mapX (0-255)
--   byte 17      mapY (0-255)
--   byte 18      facing (0-255 mapped from 0..2pi)
--   byte 19      bits 7..1: durability% (0..100), bit 0: bag_full
--   byte 20-22   gold (u24 BE, gold pieces only — silver/copper truncated)
--   byte 23      bag free slots (0-255 capped)
--   byte 24-25   target hp           (u16)
--   byte 26-27   target hp max       (u16)
--   byte 28      bits 7..1: target level (0-99 ; 0 = unknown), bit 0: has_target
--   byte 29      target flags:
--                   bit 7 = hostile
--                   bit 6 = is_player_target (PvP)
--                   bits 5..3: classification (0=normal 1=elite 2=rareelite
--                              3=rare 4=worldboss 5=trivial 6=minion)
--                   bits 2..0: reserved
--   byte 30-31   target cast spell id (u16 ; 0 = not casting)
--   byte 32      target cast progress (0-100)
--   byte 33-34   player cast spell id (u16 ; 0 = not casting)
--   byte 35      player cast progress (0-100)
--   byte 36-43   player buffs:    4 × u16 BE spell ids (0 = empty slot)
--   byte 44-51   player debuffs:  4 × u16 BE spell ids
--   byte 52-61   action bar:      10 × u8 cooldown remaining seconds
--                                (0 = ready or empty ; 255 = "long")
--   byte 62      bits 7..5: combo points (0..7)
--                bits 4..2: power type id (0=mana,1=rage,2=focus,3=energy)
--                bits 1..0: reserved
--   byte 63      checksum = sum(bytes 0..62) mod 256

local _, ns = ...
local ScreenGrid = {}
ns.ScreenGrid = ScreenGrid

-- ----- Tunables ------------------------------------------------------------
local TICK_SECS    = 2.0
local CELL_PX      = 12
local GRID_COLS    = 64
local GRID_ROWS    = 8
local TOTAL_BYTES  = (GRID_COLS * GRID_ROWS) / 8       -- 64 bytes
local TOTAL_CELLS  = GRID_COLS * GRID_ROWS             -- 512 cells
local CORNER_OFF_X = 8
local CORNER_OFF_Y = 8
local QUIET_PX     = 12   -- black border (no game UI bleed-through)

local SIZE_W = CELL_PX * GRID_COLS
local SIZE_H = CELL_PX * GRID_ROWS

-- ----- Module state --------------------------------------------------------
local frame, cells, ticker
local tickCounter = 0

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
    -- MSB written first into the lower-numbered cell.
    value = math.floor(value) % 256
    for b = 0, 7 do
        local bit = math.floor(value / (2 ^ (7 - b))) % 2
        setCellBit(byteIdx * 8 + b, bit)
    end
end

local function setU16(byteIdx, value)
    value = math.floor(value) % 65536
    setByte(byteIdx,     math.floor(value / 256))
    setByte(byteIdx + 1, value % 256)
end

local function setU24(byteIdx, value)
    value = math.floor(value) % 16777216
    setByte(byteIdx,     math.floor(value / 65536))
    setByte(byteIdx + 1, math.floor(value / 256) % 256)
    setByte(byteIdx + 2, value % 256)
end

-- Polynomial hash that's safe in WoW's Lua (stays well under 2^31 each step)
-- so doubles never lose precision. Mirrors companion's hash16().
local function hash16(s)
    local h = 0
    for i = 1, #s do
        h = (h * 31 + s:byte(i)) % 65536
    end
    return h
end

-- ----- Frame setup ---------------------------------------------------------
local function build()
    if frame then return end
    frame = CreateFrame("Frame", "ASCIIMUDGrid", UIParent)
    -- Force 1:1 logical-units-to-pixels so the decoder knows exact coords.
    frame:SetScale(1 / UIParent:GetEffectiveScale())
    frame:SetSize(SIZE_W, SIZE_H)
    -- Bottom-right anchor; viewer's OBS source can crop this off-screen.
    frame:SetPoint("BOTTOMRIGHT", UIParent, "BOTTOMRIGHT", -CORNER_OFF_X, CORNER_OFF_Y)
    frame:SetFrameStrata("TOOLTIP")

    -- Quiet zone: a black backdrop that extends QUIET_PX past the grid on
    -- all sides. This gives the decoder a clean "no white pixels" border
    -- so its bbox finder can locate the data cells unambiguously.
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
-- Class token -> id. UnitClass returns (localized, token, classID) — we use
-- classID directly when present, but include this as fallback.
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
local POWER_TYPE_ID = {
    [0] = 0,  -- mana
    [1] = 1,  -- rage
    [2] = 2,  -- focus
    [3] = 3,  -- energy
}

-- ----- Snapshot encode -----------------------------------------------------
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

local function topAuras(unit, helpful)
    -- Returns up to 4 spell ids (u16) from UnitBuff/UnitDebuff.
    local ids = {0, 0, 0, 0}
    local fn = helpful and UnitBuff or UnitDebuff
    if not fn then return ids end
    for i = 1, 4 do
        local _, _, _, _, _, _, _, _, _, spellId = fn(unit, i)
        if spellId then
            -- u16 fits Classic spell ids; truncate just in case.
            ids[i] = spellId % 65536
        end
    end
    return ids
end

local function actionBarCooldowns()
    -- 10 slots; cooldown remaining in seconds, clamped to [0,255]
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

local function targetCastInfo(unit)
    local spellId, progressPct = 0, 0
    if not UnitCastingInfo then return spellId, progressPct end
    local _, _, _, startMs, endMs, _, _, _, sId = UnitCastingInfo(unit)
    if not sId then
        if not UnitChannelInfo then return spellId, progressPct end
        local _, _, _, sMs, eMs, _, _, _, csId = UnitChannelInfo(unit)
        if csId then
            spellId = csId % 65536
            local now = GetTime() * 1000
            local total = (eMs or now) - (sMs or now)
            if total > 0 then
                progressPct = math.floor(((eMs - now) / total) * 100)
                if progressPct < 0 then progressPct = 0
                elseif progressPct > 100 then progressPct = 100 end
            end
        end
        return spellId, progressPct
    end
    spellId = sId % 65536
    local now = GetTime() * 1000
    local total = (endMs or now) - (startMs or now)
    if total > 0 then
        progressPct = math.floor(((now - startMs) / total) * 100)
        if progressPct < 0 then progressPct = 0
        elseif progressPct > 100 then progressPct = 100 end
    end
    return spellId, progressPct
end

local function encodeSnapshot()
    tickCounter = (tickCounter + 1) % 256

    -- Player vitals (raw values for the new schema).
    local hp     = UnitHealth("player")    or 0
    local hpMax  = UnitHealthMax("player") or 0
    local mp     = UnitPower("player")     or 0
    local mpMax  = UnitPowerMax("player")  or 0
    if hp > 65535 then hp = 65535 end
    if hpMax > 65535 then hpMax = 65535 end
    if mp > 65535 then mp = 65535 end
    if mpMax > 65535 then mpMax = 65535 end

    -- Player meta.
    local level = UnitLevel("player") or 1
    if level < 1 then level = 1 end
    if level > 127 then level = 127 end

    local _, classToken, classID = UnitClass("player")
    if not classID then classID = CLASS_ID[classToken or ""] or 0 end
    local _, raceToken = UnitRace("player")
    local raceID = RACE_ID[(raceToken or ""):gsub("%s", "")] or 0

    local genderIdx = (UnitSex and UnitSex("player")) or 1   -- 1=neutral 2=male 3=female
    local gender = (genderIdx == 3) and 1 or 0
    local factionGroup = UnitFactionGroup("player")
    local faction = (factionGroup == "Horde") and 1 or 0
    local mounted = (IsMounted and IsMounted()) and 1 or 0
    local pvp = (UnitIsPVP and UnitIsPVP("player")) and 1 or 0
    local grouped = (IsInGroup and IsInGroup()) and 1 or 0
    local hasPet  = (UnitExists and UnitExists("pet")) and 1 or 0
    local inCombat = UnitAffectingCombat("player") and 1 or 0
    local resting  = (IsResting and IsResting()) and 1 or 0

    -- XP.
    local xp     = UnitXP and UnitXP("player") or 0
    local xpMax  = UnitXPMax and UnitXPMax("player") or 0
    local xpPct  = (xpMax > 0) and math.floor((xp / xpMax) * 100) or 0
    if xpPct > 100 then xpPct = 100 end
    local restedXP = (GetXPExhaustion and (GetXPExhaustion() or 0) > 0) and 1 or 0

    -- Zone + position.
    local zoneName = GetZoneText() or ""
    local zoneHash = hash16(zoneName)
    local mapX, mapY = getMapPos()
    local facing = 0
    if GetPlayerFacing then
        local f = GetPlayerFacing() or 0   -- radians 0..2pi
        facing = math.floor((f / (2 * math.pi)) * 256) % 256
    end

    -- Money + bags + durability.
    local money = GetMoney and GetMoney() or 0   -- copper
    local goldPieces = math.floor(money / 10000)
    if goldPieces > 16777215 then goldPieces = 16777215 end

    local freeSlots = 0
    if GetContainerNumFreeSlots then
        for bag = 0, 4 do
            freeSlots = freeSlots + (GetContainerNumFreeSlots(bag) or 0)
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

    -- Target.
    local hasTarget = UnitExists("target") and 1 or 0
    local tHp, tHpMax, tLevel = 0, 0, 0
    local tHostile, tIsPlayer, tClass = 0, 0, 0
    local tCastSpell, tCastProgress = 0, 0
    if hasTarget == 1 then
        tHp    = UnitHealth("target") or 0
        tHpMax = UnitHealthMax("target") or 0
        if tHp > 65535 then tHp = 65535 end
        if tHpMax > 65535 then tHpMax = 65535 end
        local lvl = UnitLevel("target") or 0
        if lvl < 0 then lvl = 0 end           -- ?? bosses come back as -1
        if lvl > 99 then lvl = 99 end
        tLevel = lvl
        tHostile  = UnitCanAttack("player", "target") and 1 or 0
        tIsPlayer = UnitIsPlayer("target") and 1 or 0
        local cls = (UnitClassification and UnitClassification("target")) or "normal"
        tClass = CLASSIFICATION_ID[cls] or 0
        tCastSpell, tCastProgress = targetCastInfo("target")
    end

    -- Player casting.
    local pCastSpell, pCastProgress = targetCastInfo("player")

    -- Buffs / debuffs.
    local buffs   = topAuras("player", true)
    local debuffs = topAuras("player", false)

    -- Notify SpellRegistry so it can side-channel name+icon for any new IDs.
    if ns.SpellRegistry then
        if pCastSpell ~= 0 then ns.SpellRegistry:Observe(pCastSpell) end
        if tCastSpell ~= 0 then ns.SpellRegistry:Observe(tCastSpell) end
        ns.SpellRegistry:ObserveMany(buffs)
        ns.SpellRegistry:ObserveMany(debuffs)
    end

    -- Action bar.
    local cds = actionBarCooldowns()

    -- Combo points + power type.
    local combo = (GetComboPoints and GetComboPoints("player", "target")) or 0
    if combo > 7 then combo = 7 end
    local powerType = UnitPowerType and UnitPowerType("player") or 0
    if powerType > 7 then powerType = 0 end

    -- ---- write all bytes ----
    setByte(0, 0xA5)
    setByte(1, tickCounter)
    setU16(2,  hp)
    setU16(4,  hpMax)
    setU16(6,  mp)
    setU16(8,  mpMax)
    setByte(10, level * 2 + resting)
    setByte(11, classID * 16 + raceID)

    local flags12 =
        inCombat   * 128 +
        gender     * 64  +
        faction    * 32  +
        mounted    * 16  +
        pvp        * 8   +
        grouped    * 4   +
        hasPet     * 2
    setByte(12, flags12)
    setByte(13, xpPct * 2 + restedXP)
    setU16(14, zoneHash)
    setByte(16, mapX)
    setByte(17, mapY)
    setByte(18, facing)
    setByte(19, dura * 2 + bagFull)
    setU24(20, goldPieces)
    setByte(23, freeSlots)
    setU16(24, tHp)
    setU16(26, tHpMax)
    setByte(28, tLevel * 2 + hasTarget)

    local flags29 =
        tHostile  * 128 +
        tIsPlayer * 64  +
        (tClass % 8) * 8
    setByte(29, flags29)
    setU16(30, tCastSpell)
    setByte(32, tCastProgress)
    setU16(33, pCastSpell)
    setByte(35, pCastProgress)
    -- buffs 36..43 (4 × u16)
    for i = 1, 4 do setU16(34 + i * 2, buffs[i]) end
    -- debuffs 44..51
    for i = 1, 4 do setU16(42 + i * 2, debuffs[i]) end
    -- action bar 52..61 (10 bytes)
    for i = 1, 10 do setByte(51 + i, cds[i]) end
    setByte(62, combo * 32 + (powerType % 8) * 4)

    -- Checksum over bytes 0..62. Easiest: read back from the cells we just
    -- wrote — but we already have all values. Sum them in the same order.
    local sum = 0xA5 + tickCounter
    -- u16 values contribute as their two-byte sums:
    local function s16(v) return math.floor(v / 256) + (v % 256) end
    local function s24(v) return math.floor(v / 65536)
                              + math.floor(v / 256) % 256
                              + (v % 256) end
    sum = sum
        + s16(hp) + s16(hpMax) + s16(mp) + s16(mpMax)
        + (level * 2 + resting)
        + (classID * 16 + raceID)
        + flags12
        + (xpPct * 2 + restedXP)
        + s16(zoneHash)
        + mapX + mapY + facing
        + (dura * 2 + bagFull)
        + s24(goldPieces)
        + freeSlots
        + s16(tHp) + s16(tHpMax)
        + (tLevel * 2 + hasTarget)
        + flags29
        + s16(tCastSpell) + tCastProgress
        + s16(pCastSpell) + pCastProgress
    for i = 1, 4 do sum = sum + s16(buffs[i]) end
    for i = 1, 4 do sum = sum + s16(debuffs[i]) end
    for i = 1, 10 do sum = sum + cds[i] end
    sum = sum + (combo * 32 + (powerType % 8) * 4)
    setByte(63, sum % 256)
end

local function tick()
    if not frame:IsShown() then return end
    encodeSnapshot()
    -- Take the screenshot one frame *after* encode so textures are committed.
    C_Timer.After(0, function() Screenshot() end)
end

-- ----- Public --------------------------------------------------------------
function ScreenGrid:Init()
    build()
    pcall(SetCVar, "screenshotFormat", "jpg")
    pcall(SetCVar, "screenshotQuality", "1")
    -- Suppress yellow "Screenshot captured" toast.
    if UIErrorsFrame and UIErrorsFrame.UnregisterEvent then
        pcall(UIErrorsFrame.UnregisterEvent, UIErrorsFrame, "SCREENSHOT_SUCCEEDED")
        pcall(UIErrorsFrame.UnregisterEvent, UIErrorsFrame, "SCREENSHOT_FAILED")
    end
    if ticker then ticker:Cancel() end
    ticker = C_Timer.NewTicker(TICK_SECS, tick)
    print(string.format(
        "|cff66ccffASCIIMUD|r: screen grid %dx%d (%d bytes/tick) every %.1fs.",
        GRID_COLS, GRID_ROWS, TOTAL_BYTES, TICK_SECS))
end

function ScreenGrid:Show()  if frame then frame:Show() end end
function ScreenGrid:Hide()  if frame then frame:Hide() end end
function ScreenGrid:Toggle()
    if not frame then return end
    if frame:IsShown() then frame:Hide() else frame:Show() end
end
