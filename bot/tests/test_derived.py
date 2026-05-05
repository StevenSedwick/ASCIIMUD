from bot.derived import Derived


def _snap(**player):
    return {
        "t": "snapshot",
        "data": {
            "player": {"hpPct": player.get("hpPct", 100),
                       "level": player.get("level", 5),
                       "class": "WARLOCK"},
            "zone": {"hash": player.get("zoneHash", 0x3ED4)},  # Elwynn
            "target": {"name": player.get("targetName"),
                       "level": player.get("targetLevel")},
            "combat": player.get("combat", False),
        },
    }


def kinds(events):
    return [k for k, _ in events]


def test_first_snapshot_emits_only_state_update():
    d = Derived("Steven")
    events = d.feed(_snap())
    assert "state_update" in kinds(events)
    assert "level_up" not in kinds(events)


def test_level_up_detection():
    d = Derived("Steven")
    d.feed(_snap(level=5))
    events = d.feed(_snap(level=6))
    assert "level_up" in kinds(events)


def test_combat_enter_leave():
    d = Derived("Steven")
    d.feed(_snap(combat=False))
    e1 = d.feed(_snap(combat=True))
    assert "entered_combat" in kinds(e1)
    e2 = d.feed(_snap(combat=False))
    assert "left_combat" in kinds(e2)


def test_close_call_arms_and_fires():
    d = Derived("Steven")
    d.feed(_snap(hpPct=100))
    d.feed(_snap(hpPct=22))            # arm
    d.feed(_snap(hpPct=18))            # update lowest
    e = d.feed(_snap(hpPct=70))        # recover -> fires
    assert "close_call" in kinds(e)
    assert d.counters.close_call_count == 1


def test_zone_change():
    d = Derived("Steven")
    d.feed(_snap(zoneHash=0x3ED4))
    e = d.feed(_snap(zoneHash=0x6DCA))   # Westfall
    assert "zone_changed" in kinds(e)


def test_kill_count_via_combat_event():
    d = Derived("Steven")
    d.feed({"t": "combat", "event": "UNIT_DIED", "dst": "Defias Thug"})
    assert d.counters.kill_count == 1


def test_death_event_records():
    d = Derived("Steven")
    d.feed({"t": "death", "player": "Steven"})
    assert d.counters.death_count == 1
