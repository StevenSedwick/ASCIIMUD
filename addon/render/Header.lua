-- Header.lua : top bar with zone, HP/MP, chapter.
local _, ns = ...
local Header = {}
ns.Header = Header

local FONT = "Fonts\\ARIALN.TTF"

function Header:Init()
    local f = CreateFrame("Frame", "ASCIIMUDHeader", ns.Veil.frame)
    f:SetSize(900, 28)
    f:SetPoint("TOP", ns.Veil.frame, "TOP", 0, -12)

    local fs = f:CreateFontString(nil, "ARTWORK")
    fs:SetFont(FONT, 16, "")
    fs:SetPoint("CENTER")
    fs:SetTextColor(0.8, 0.95, 1)
    self.text = fs

    ns.EventBus:On("STATE_CHANGED", function(s) self:Render(s) end)
end

function Header:Render(s)
    local p = s.player
    local hp = string.format("HP %d/%d", p.hp, p.hpMax)
    local mp = string.format("MP %d/%d", p.mp, p.mpMax)
    local zone = s.zone.name
    if s.zone.subzone ~= "" and s.zone.subzone ~= zone then
        zone = zone .. " : " .. s.zone.subzone
    end
    self.text:SetText(string.format(" Ch.%d  |  %s  |  Lv%d %s  |  %s  |  %s ",
        s.chapter, zone, p.level, p.name, hp, mp))
end
