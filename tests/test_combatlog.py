"""Tests for the combat-log parser."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "companion"))

from combatlog import parse  # noqa: E402


pytestmark = pytest.mark.unit


def test_swing_damage_outgoing():
    line = (
        '4/30 17:35:43.456  SWING_DAMAGE,Player-1-ABC,"Testwick",0x511,0x0,'
        'Creature-0-1-1-1-100-X,"Defias Thug",0x10a48,0x0,123,0,1,0,0,0,nil,nil,nil'
    )
    evt = parse(line)
    assert evt is not None
    assert evt["t"] == "combat"
    assert evt["event"] == "SWING_DAMAGE"
    assert evt["src"] == "Testwick"
    assert evt["dst"] == "Defias Thug"
    assert evt["amount"] == 123
    assert evt["spell"] == "Melee"


def test_spell_damage():
    line = (
        '4/30 17:35:43.456  SPELL_DAMAGE,Player-1-ABC,"Testwick",0x511,0x0,'
        'Creature-0-1,"Boar",0x10a48,0x0,348,"Immolate",0x4,412,0,4,0,0,0,nil,nil,nil'
    )
    evt = parse(line)
    assert evt is not None
    assert evt["spell"] == "Immolate"
    assert evt["amount"] == 412


def test_spell_heal():
    line = (
        '4/30 17:35:43.456  SPELL_HEAL,Player-1-ABC,"Healer",0x511,0x0,'
        'Player-1-DEF,"Tank",0x511,0x0,2050,"Healing Touch",0x8,500,0,0,nil'
    )
    evt = parse(line)
    assert evt is not None
    assert evt["spell"] == "Healing Touch"
    assert evt["amount"] == 500
    assert evt.get("heal") is True


def test_unit_died():
    line = (
        '4/30 17:36:00.000  UNIT_DIED,0000000000000000,nil,0x0,0x0,'
        'Creature-0-1,"Defias Thug",0x10a48,0x0'
    )
    evt = parse(line)
    assert evt is not None
    assert evt["event"] == "UNIT_DIED"
    assert evt["dst"] == "Defias Thug"


def test_uninteresting_event_returns_none():
    line = '4/30 17:35:43.456  SPELL_AURA_APPLIED,Player-1,"X",0,0,Player-1,"X",0,0,1,"Buff",0x1,BUFF'
    assert parse(line) is None


def test_garbage_returns_none():
    assert parse("hello world") is None
    assert parse("") is None
    assert parse("4/30 not really a combat line") is None


def test_combat_log_version_header_ignored():
    line = "4/30 17:35:42.123  COMBAT_LOG_VERSION,11,ADVANCED_LOG_ENABLED,1"
    assert parse(line) is None


def test_environmental_damage():
    line = (
        '4/30 17:35:43.456  ENVIRONMENTAL_DAMAGE,0000000000000000,nil,0x0,0x0,'
        'Player-1,"Testwick",0x511,0x0,"FALLING",450,0,1,0,0,0,nil,nil,nil'
    )
    evt = parse(line)
    assert evt is not None
    assert evt["spell"] == "FALLING"
    assert evt["amount"] == 450
