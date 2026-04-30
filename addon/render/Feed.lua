-- Feed.lua : scrolling text column on the right.
local _, ns = ...
local Feed = { max = 24 }
ns.Feed = Feed

local FONT = "Fonts\\ARIALN.TTF"

function Feed:Init()
    local f = CreateFrame("ScrollingMessageFrame", "ASCIIMUDFeed", ns.Veil.frame)
    f:SetSize(420, 480)
    f:SetPoint("RIGHT", ns.Veil.frame, "RIGHT", -40, 0)
    f:SetFont(FONT, 13, "")
    f:SetJustifyH("LEFT")
    f:SetFading(false)
    f:SetMaxLines(self.max)
    f:SetInsertMode("BOTTOM")
    f:SetTextColor(0.85, 0.85, 0.7)
    self.frame = f

    ns.EventBus:On("CHAT_MSG_MONSTER_SAY", function(p) self:Push("[mob] " .. (p[1] or "")) end)
    ns.EventBus:On("CHAT_MSG_SAY",         function(p) self:Push("[say] " .. (p[2] or "") .. ": " .. (p[1] or "")) end)
    ns.EventBus:On("PLAYER_REGEN_DISABLED",function() self:Push("|cffff5555>> combat begins <<|r") end)
    ns.EventBus:On("PLAYER_REGEN_ENABLED", function() self:Push("|cff55ff55>> combat ends   <<|r") end)
    ns.EventBus:On("PLAYER_DEAD",          function() self:Push("|cffff0000*** you have died ***|r") end)
end

function Feed:Push(line)
    if self.frame then self.frame:AddMessage(line) end
end
