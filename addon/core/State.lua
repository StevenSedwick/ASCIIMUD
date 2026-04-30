-- State.lua : canonical world snapshot. Single source of truth for renderers.
local _, ns = ...
local State = {}
ns.State = State

function State:Init()
    self.player = { name = UnitName("player"), class = select(2, UnitClass("player")),
                    hp = 1, hpMax = 1, mp = 1, mpMax = 1, level = UnitLevel("player") }
    self.zone   = { name = "", subzone = "", x = 0, y = 0 }
    self.target = nil
    self.combat = false
    self.chapter = 1
    self.tick   = 0
end

function State:UpdatePlayer()
    self.player.hp     = UnitHealth("player")
    self.player.hpMax  = UnitHealthMax("player")
    self.player.mp     = UnitPower("player")
    self.player.mpMax  = UnitPowerMax("player")
    self.player.level  = UnitLevel("player")
end

function State:UpdateZone()
    self.zone.name    = GetRealZoneText() or ""
    self.zone.subzone = GetSubZoneText() or ""
end

function State:UpdateTarget()
    if UnitExists("target") then
        self.target = {
            name  = UnitName("target"),
            hp    = UnitHealth("target"),
            hpMax = UnitHealthMax("target"),
            level = UnitLevel("target"),
            hostile = UnitCanAttack("player", "target") and true or false,
        }
    else
        self.target = nil
    end
end

function State:Snapshot()
    return {
        v       = 1,
        tick    = self.tick,
        player  = self.player,
        zone    = self.zone,
        target  = self.target,
        combat  = self.combat,
        chapter = self.chapter,
    }
end
