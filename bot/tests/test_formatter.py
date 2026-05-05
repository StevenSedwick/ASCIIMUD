from bot.formatter import _hallucinates, template


def test_status_template_includes_required_facts():
    msg = template("status", {
        "level": 12, "class": "WARLOCK", "hpPct": 80,
        "zoneHash": 0x3ED4, "inCombat": True,
        "dangerLevel": "medium", "lastEvent": "Engaged combat",
    })
    assert "[ASCIIMUD]" in msg
    assert "Level 12" in msg
    assert "Elwynn" in msg
    assert "WARLOCK" in msg


def test_rules_template_is_canonical():
    assert "Hardcore" in template("rules", {})


def test_help_lists_commands():
    msg = template("help", {})
    for c in ("!status", "!danger", "!objective", "!recap", "!help"):
        assert c in msg


def test_close_call_template_shows_lowest_hp():
    msg = template("close_call", {"lowestHpPct": 18})
    assert "18%" in msg


def test_hallucination_guard_blocks_unknown_numbers():
    facts = {"hpPct": 80, "level": 12}
    # 80 and 12 are allowed; 9999 is not.
    assert _hallucinates("[ASCIIMUD] HP 80% level 12 dealt 9999 damage", facts)
    assert not _hallucinates("[ASCIIMUD] HP 80% level 12 holding the line", facts)
