"""Spell metadata store.

The addon resolves spell IDs to {name, rank, icon, school} via GetSpellInfo
in-game and emits ``spell_meta`` events on the chat-log NDJSON channel.
We persist them to ``data/spells.json`` so a /reload doesn't lose them and
so cold-start overlays get a bulk dump on connect.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Iterable

LOG = logging.getLogger("asciimud.spell_db")


class SpellDB:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.spells: dict[int, dict[str, Any]] = {}
        self.action_bar: list[dict[str, Any]] = []
        self._dirty = False
        self._load()

    # ---------- persistence ----------
    def _load(self) -> None:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return
        except (json.JSONDecodeError, OSError) as e:
            LOG.warning("spell DB load failed: %s", e)
            return
        for k, v in (raw.get("spells") or {}).items():
            try:
                self.spells[int(k)] = v
            except (TypeError, ValueError):
                continue
        LOG.info("Loaded %d spell metadata entries from %s",
                 len(self.spells), self.path)

    def flush(self) -> None:
        if not self._dirty:
            return
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            tmp.write_text(json.dumps(
                {"spells": {str(k): v for k, v in self.spells.items()}},
                indent=0, sort_keys=True), encoding="utf-8")
            tmp.replace(self.path)
            self._dirty = False
        except OSError as e:
            LOG.warning("spell DB flush failed: %s", e)

    # ---------- ingest ----------
    def add_meta(self, evt: dict[str, Any]) -> bool:
        """Returns True if this is a new spell (worth broadcasting)."""
        try:
            sid = int(evt["id"])
        except (KeyError, TypeError, ValueError):
            return False
        existing = self.spells.get(sid)
        if existing == {k: v for k, v in evt.items() if k != "t"}:
            return False
        self.spells[sid] = {k: v for k, v in evt.items() if k != "t"}
        self._dirty = True
        return True

    def set_action_bar(self, slots: list[dict[str, Any]]) -> None:
        self.action_bar = slots or []

    # ---------- queries ----------
    def get(self, sid: int) -> dict[str, Any] | None:
        return self.spells.get(int(sid))

    def bulk_payload(self) -> dict[str, Any]:
        return {"t": "spell_meta_bulk",
                "spells": [{**v, "id": k} for k, v in self.spells.items()]}

    def action_bar_payload(self) -> dict[str, Any]:
        return {"t": "action_bar", "slots": self.action_bar}
