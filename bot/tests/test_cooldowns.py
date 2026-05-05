from bot.cooldowns import Cooldowns


def test_per_key_gates():
    c = Cooldowns(global_min_interval=0, dedupe_window=60)
    assert c.ready("k", 10, now=0)
    c.mark("k", now=0)
    assert not c.ready("k", 10, now=5)
    assert c.ready("k", 10, now=11)


def test_global_throttle():
    c = Cooldowns(global_min_interval=5, dedupe_window=60)
    assert c.global_ready(now=0)
    c.mark_global(now=0)
    assert not c.global_ready(now=2)
    assert c.global_ready(now=6)


def test_dedupe_window():
    c = Cooldowns(global_min_interval=0, dedupe_window=10)
    msg = "[ASCIIMUD] hello"
    assert not c.is_duplicate(msg, now=0)
    c.remember(msg, now=0)
    assert c.is_duplicate(msg, now=5)
    # Outside window, not a dup anymore.
    assert not c.is_duplicate(msg, now=20)


def test_should_send_combined():
    c = Cooldowns(global_min_interval=2, dedupe_window=30)
    assert c.should_send("k", 5, "x")
    c.commit("k", "x")
    assert not c.should_send("k", 5, "x")          # dedupe + key cooldown
    assert not c.should_send("k2", 1, "x")         # dedupe still blocks
    assert not c.should_send("k2", 1, "y")         # global throttle blocks
