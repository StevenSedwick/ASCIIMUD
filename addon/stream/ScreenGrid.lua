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
-- Schema currently encoded (in cell index order, MSB first per byte):
--   cells 00..07  byte0  = magic        (0xA5  marker so we can sync)
--   cells 08..15  byte1  = tick % 256   (heartbeat)
--   cells 16..22  bits   = HP%/100 * 100 (0..100, 7 bits)
--   cell  23      bit    = combat       (1 = in combat)
--   cells 24..30  bits   = MP%/100 * 100 (0..100, 7 bits)
--   cell  31      bit    = target hostile
--   cells 32..47  byte4..5 zone id hash (16 bits)
--   cells 48..55  byte6  reserved
--   cells 56..63  byte7  = checksum (sum of bytes 0..6 mod 256)

local _, ns = ...
local ScreenGrid = {}
ns.ScreenGrid = ScreenGrid

-- Tunable.
local TICK_SECS    = 2.0   -- how often to snap
local CELL_PX      = 8     -- size of each cell on screen, must be >= 4 to decode reliably
local GRID_CELLS   = 8     -- 8x8 = 64 bits = 8 bytes per shot
local CORNER_OFF_X = 4     -- pixels from screen edge
local CORNER_OFF_Y = 4

local SIZE_PX = CELL_PX * GRID_CELLS

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
    -- byteIdx 0..7. MSB written into the lower-numbered cell (left-to-right reading).
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
    frame:SetSize(SIZE_PX, SIZE_PX)
    frame:SetPoint("BOTTOMRIGHT", UIParent, "BOTTOMRIGHT", -CORNER_OFF_X, CORNER_OFF_Y)
    frame:SetFrameStrata("TOOLTIP")
    cells = {}
    for row = 0, GRID_CELLS - 1 do
        for col = 0, GRID_CELLS - 1 do
            local idx = row * GRID_CELLS + col
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
    local targetHostile = (UnitExists("target") and UnitCanAttack("player", "target")) and 1 or 0

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

    local zoneName = GetZoneText() or ""
    local zoneHash = fnv1a8(zoneName)

    setByte(0, 0xA5)          -- magic marker
    setByte(1, tickCounter)
    setBits(16, 7, hpPct)     -- cells 16..22
    setCellBit(23, inCombat)  -- cell 23
    setBits(24, 7, mpPct)     -- cells 24..30
    setCellBit(31, targetHostile)  -- cell 31
    setByte(4, math.floor(zoneHash / 256))  -- high byte
    setByte(5, zoneHash % 256)              -- low byte
    setByte(6, 0)                           -- reserved
    -- checksum: sum of bytes 0..6 mod 256
    local sum = 0xA5 + tickCounter
                + math.floor(hpPct * 2 + inCombat)        -- byte2 reconstructed
                + math.floor(mpPct * 2 + targetHostile)   -- byte3 reconstructed
                + math.floor(zoneHash / 256)
                + (zoneHash % 256)
                + 0
    setByte(7, sum % 256)
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
    if ticker then ticker:Cancel() end
    ticker = C_Timer.NewTicker(TICK_SECS, tick)
    print(string.format(
        "|cff66ccffASCIIMUD|r: screen grid %dx%d (%dpx cells) snapping every %.1fs.",
        GRID_CELLS, GRID_CELLS, CELL_PX, TICK_SECS))
end

function ScreenGrid:Show() if frame then frame:Show() end end
function ScreenGrid:Hide() if frame then frame:Hide() end end
function ScreenGrid:Toggle()
    if not frame then return end
    if frame:IsShown() then frame:Hide() else frame:Show() end
end
