-- Grid.lua : ASCII grid rendered as a FontString matrix.
-- The player sees this in-game; chat sees a richer overlay version.
local _, ns = ...
local Grid = { cols = 60, rows = 20 }
ns.Grid = Grid

local FONT = "Fonts\\ARIALN.TTF"
local CELL_W, CELL_H = 10, 14

function Grid:Init()
    local f = CreateFrame("Frame", "ASCIIMUDGrid", ns.Veil.frame)
    f:SetSize(self.cols * CELL_W, self.rows * CELL_H)
    f:SetPoint("CENTER", ns.Veil.frame, "CENTER", -120, 0)
    self.frame = f

    self.cells = {}
    for r = 1, self.rows do
        self.cells[r] = {}
        for c = 1, self.cols do
            local fs = f:CreateFontString(nil, "ARTWORK")
            fs:SetFont(FONT, 12, "MONOCHROME")
            fs:SetTextColor(0.6, 0.9, 0.6, 1)
            fs:SetPoint("TOPLEFT", f, "TOPLEFT", (c - 1) * CELL_W, -((r - 1) * CELL_H))
            fs:SetText(".")
            self.cells[r][c] = fs
        end
    end

    ns.EventBus:On("STATE_CHANGED", function(s) self:Render(s) end)
    self:Render(ns.State:Snapshot())
end

function Grid:Set(r, c, ch, rC, gC, bC)
    local cell = self.cells[r] and self.cells[r][c]
    if not cell then return end
    cell:SetText(ch)
    if rC then cell:SetTextColor(rC, gC, bC, 1) end
end

function Grid:Clear()
    for r = 1, self.rows do
        for c = 1, self.cols do
            self:Set(r, c, ".", 0.15, 0.25, 0.15)
        end
    end
end

function Grid:Render(snap)
    self:Clear()
    local pr, pc = math.floor(self.rows / 2), math.floor(self.cols / 2)
    self:Set(pr, pc, "@", 0.9, 0.9, 0.2)
    if snap.target then
        self:Set(pr, pc + 4, snap.target.hostile and "X" or "N", 0.9, 0.3, 0.3)
    end
end
