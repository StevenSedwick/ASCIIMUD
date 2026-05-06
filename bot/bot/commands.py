"""Chat command handlers.

Each handler returns a (kind, facts) pair so the same template + AI rewriter
used for auto-posts can produce the reply.
"""
from __future__ import annotations

from typing import Any

from .derived import Derived


def cmd_status(d: Derived) -> tuple[str, dict[str, Any]]:
    return ("status", d.snapshot_facts())


def cmd_rules(d: Derived) -> tuple[str, dict[str, Any]]:
    return ("rules", {})


def cmd_danger(d: Derived) -> tuple[str, dict[str, Any]]:
    return ("danger", d.snapshot_facts())


def cmd_objective(d: Derived) -> tuple[str, dict[str, Any]]:
    return ("objective", d.snapshot_facts())


def cmd_stats(d: Derived) -> tuple[str, dict[str, Any]]:
    return ("stats", d.snapshot_facts())


def cmd_closecalls(d: Derived) -> tuple[str, dict[str, Any]]:
    f = d.snapshot_facts()
    # latest close call from recap ring, if any
    last_cc = next((line for line in reversed(list(d.recap))
                    if line.lower().startswith("close call")), None)
    f["lastCloseCall"] = last_cc
    return ("closecalls", f)


def cmd_deathlog(d: Derived) -> tuple[str, dict[str, Any]]:
    f = d.snapshot_facts()
    last_death = next((line for line in reversed(list(d.recap))
                       if line.lower().startswith("death")), None)
    f["lastDeath"] = last_death
    return ("deathlog", f)


def cmd_help(d: Derived) -> tuple[str, dict[str, Any]]:
    return ("help", {})


def cmd_addon(d: Derived, addon_url: str) -> tuple[str, dict[str, Any]]:
    return ("addon", {"addonUrl": addon_url})


def cmd_map(d: Derived, map_url: str) -> tuple[str, dict[str, Any]]:
    return ("map", {"mapUrl": map_url})


def cmd_interface(d: Derived, interface_url: str) -> tuple[str, dict[str, Any]]:
    return ("interface", {"interfaceUrl": interface_url})


COMMANDS = {
    "status": cmd_status,
    "rules": cmd_rules,
    "danger": cmd_danger,
    "objective": cmd_objective,
    "stats": cmd_stats,
    "closecalls": cmd_closecalls,
    "deathlog": cmd_deathlog,
    "help": cmd_help,
}
