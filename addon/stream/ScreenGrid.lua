-- ScreenGrid.lua : tick-flushed real-time data channel via screenshots.
--
-- WoW writes screenshots to disk synchronously, so they're not subject to
-- the in-process buffering that holds back chat/combat logs. We render a
-- tiny 8x8 grid of black/white squares in a corner of the screen, encode
-- the current state into 64 bits, then call Screenshot() on a timer.
-- The companion process watches Screenshots/, samples the grid pixels,
-- and broadcasts the decoded snapshot to the OBS overlay.
--
-- This file is the in-game half: the grid + the tick. Decoding is in
-- companion/screenshot_decoder.py.
--
-- Schema currently encoded (16x8 grid = 128 cells = 16 bytes):
--   byte0   = magic (0xA5)
--   byte1   = tick % 256
--   byte2   bits 7..1: HP%, bit 0: in_combat
--   byte3   bits 7..1: MP%, bit 0: target_hostile
--   byte4..5 zone hash (16 bits big-endian, FNV-1a of GetZoneText())
--   byte6   bits 7..1: target HP%, bit 0: has_target
--   byte7   bits 7..1: level (1-60), bit 0: is_resting
--   byte8   map X position (0-255, normalised from C_Map 0..1)
--   byte9   map Y position (0-255, normalised from C_Map 0..1)
--   byte10..13 reserved (zero)
--   byte14  checksum = sum(bytes 0..13) % 256
--   byte15  reserved (zero)

local _, ns = ...
local ScreenGrid = {}
ns.ScreenGrid = ScreenGrid

-- Tunable.
local TICK_SECS    = 2.0    -- how often to snap
local CELL_PX      = 12     -- size of each cell on screen, must be >= 4 to decode reliably
local GRID_COLS    = 16     -- 16 columns × 8 rows = 128 bits = 16 bytes
local GRID_ROWS    = 8
local CORNER_OFF_X = 8      -- pixels from screen edge
local CORNER_OFF_Y = 8

local SIZE_W = CELL_PX * GRID_COLS
local SIZE_H = CELL_PX * GRID_ROWS

local frame, cells, ticker
local tickCounter = 0

-- ----- bit helpers ---------------------------------------------------------

local function setCellBit(idx, bit)
    -- idx 0..63, bit 0 or 1
    local cell = cells[idx + 1]
    if bit == 1 then
        cell:SetColorTexture(1, 1, 1, 1)  -- white = 1
    else
        cell:SetColorTexture(0, 0, 0, 1)  -- black = 0
    end
end

local function setByte(byteIdx, value)
    -- byteIdx 0..15. MSB written into the lower-numbered cell (left-to-right reading).
    value = value % 256
    for b = 0, 7 do
        local bit = math.floor(value / (2 ^ (7 - b))) % 2
        setCellBit(byteIdx * 8 + b, bit)
    end
end

local function setBits(startCell, nBits, value)
    -- pack `value` (already in range 0..2^nBits-1) into `nBits` consecutive cells.
    value = value % (2 ^ nBits)
    for b = 0, nBits - 1 do
        local bit = math.floor(value / (2 ^ (nBits - 1 - b))) % 2
        setCellBit(startCell + b, bit)
    end
end

local function fnv1a8(s)
    -- 16-bit FNV-1a; cheap zone-name hash so we can map names client-side.
    local h = 2166136261
    for i = 1, #s do
        h = bit.bxor(h, s:byte(i))
        h = (h * 16777619) % 4294967296
    end
    return h % 65536
end

-- ----- frame setup ---------------------------------------------------------

local function build()
    if frame then return end
    frame = CreateFrame("Frame", "ASCIIMUDGrid", UIParent)
    -- Force 1:1 logical-units-to-pixels so the decoder knows exact coords.
    frame:SetScale(1 / UIParent:GetEffectiveScale())
    frame:SetSize(SIZE_W, SIZE_H)
    frame:SetPoint("BOTTOMRIGHT", UIParent, "BOTTOMRIGHT", -CORNER_OFF_X, CORNER_OFF_Y)
    frame:SetFrameStrata("TOOLTIP")
    cells = {}
    for row = 0, GRID_ROWS - 1 do
        for col = 0, GRID_COLS - 1 do
            local idx = row * GRID_COLS + col
            local t = frame:CreateTexture(nil, "OVERLAY")
            t:SetSize(CELL_PX, CELL_PX)
            -- Row 0 = top of grid.
            t:SetPoint("TOPLEFT", frame, "TOPLEFT",
                       col * CELL_PX, -row * CELL_PX)
            t:SetColorTexture(0, 0, 0, 1)
            cells[idx + 1] = t
        end
    end
end

-- ----- snapshot encode + screenshot ---------------------------------------

local function encodeSnapshot()
    tickCounter = (tickCounter + 1) % 256

    local hpPct = 0
    local mpPct = 0
    local inCombat = UnitAffectingCombat("player") and 1 or 0
    local hasTarget = UnitExists("target") and 1 or 0
    local targetHostile = (hasTarget == 1 and UnitCanAttack("player", "target")) and 1 or 0
    local targetHpPct = 0
    if hasTarget == 1 then
        local thMax = UnitHealthMax("target") or 0
        if thMax > 0 then
            targetHpPct = math.floor((UnitHealth("target") / thMax) * 100)
        end
        if targetHpPct > 100 then targetHpPct = 100 end
        if targetHpPct < 0 then targetHpPct = 0 end
    end

    local hpMax = UnitHealthMax("player") or 0
    if hpMax > 0 then
        hpPct = math.floor((UnitHealth("player") / hpMax) * 100)
    end
    local mpMax = UnitPowerMax("player") or 0
    if mpMax > 0 then
        mpPct = math.floor((UnitPower("player") / mpMax) * 100)
    end
    if hpPct > 100 then hpPct = 100 end
    if mpPct > 100 then mpPct = 100 end

    local level = UnitLevel("player") or 1
    if level < 1 then level = 1 end
    if level > 127 then level = 127 end
    local isResting = IsResting() and 1 or 0

    local zoneName = GetZoneText() or ""
    local zoneHash = fnv1a8(zoneName)

    -- Map position: C_Map returns 0..1 floats; encode as 0..255.
    local mapX, mapY = 127, 127
    if C_Map and C_Map.GetBestMapForUnit then
        local ok, result = pcall(function()
            local mapID = C_Map.GetBestMapForUnit("player")
            if mapID then
                return C_Map.GetPlayerMapPosition(mapID, "player")
            end
        end)
        if ok and result then
            local px, py = result:GetXY()
            mapX = math.floor(math.max(0, math.min(1, px)) * 255)
            mapY = math.floor(math.max(0, math.min(1, py)) * 255)
        end
    end

    -- byte6: bits 7..1 = targetHpPct, bit 0 = hasTarget
    local byte6 = targetHpPct * 2 + hasTarget
    -- byte7: bits 7..1 = level, bit 0 = isResting
    local byte7 = level * 2 + isResting

    setByte(0, 0xA5)
    setByte(1, tickCounter)
    setBits(16, 7, hpPct)
    setCellBit(23, inCombat)
    setBits(24, 7, mpPct)
    setCellBit(31, targetHostile)
    setByte(4, math.floor(zoneHash / 256))
    setByte(5, zoneHash % 256)
    setByte(6, byte6)
    setByte(7, byte7)
    setByte(8, mapX)
    setByte(9, mapY)
    setByte(10, 0)  -- reserved
    setByte(11, 0)
    setByte(12, 0)
    setByte(13, 0)
    -- checksum over bytes 0..13
    local sum = 0xA5 + tickCounter
                + (hpPct * 2 + inCombat)
                + (mpPct * 2 + targetHostile)
                + math.floor(zoneHash / 256)
                + (zoneHash % 256)
                + byte6
                + byte7
                + mapX
                + mapY
                -- bytes 10-13 are zero, contribute 0
    setByte(14, sum % 256)
    setByte(15, 0)  -- reserved
end

local function tick()
    if not frame:IsShown() then return end
    encodeSnapshot()
    -- Take the screenshot one frame *after* encode so the textures are committed.
    C_Timer.After(0, function()
        Screenshot()
    end)
end

-- ----- public --------------------------------------------------------------

function ScreenGrid:Init()
    build()
    -- Force JPEG at lowest quality so each shot is small & fast.
    -- screenshotQuality 0..10 ; format "jpg" or "tga".
    pcall(SetCVar, "screenshotFormat", "jpg")
    pcall(SetCVar, "screenshotQuality", "1")
    -- Suppress yellow "Screenshot captured" toast that would otherwise spam
    -- every 2 seconds. The default UI listens for these on UIErrorsFrame.
    if UIErrorsFrame and UIErrorsFrame.UnregisterEvent then
        pcall(UIErrorsFrame.UnregisterEvent, UIErrorsFrame, "SCREENSHOT_SUCCEEDED")
        pcall(UIErrorsFrame.UnregisterEvent, UIErrorsFrame, "SCREENSHOT_FAILED")
    end
    if ticker then ticker:Cancel() end
    ticker = C_Timer.NewTicker(TICK_SECS, tick)
    print(string.format(
        "|cff66ccffASCIIMUD|r: screen grid %dx%d (%dpx cells) snapping every %.1fs.",
        GRID_COLS, GRID_ROWS, CELL_PX, TICK_SECS))
end

function ScreenGrid:Show() if frame then frame:Show() end end
function ScreenGrid:Hide() if frame then frame:Hide() end end
function ScreenGrid:Toggle()
    if not frame then return end
    if frame:IsShown() then frame:Hide() else frame:Show() end
end
