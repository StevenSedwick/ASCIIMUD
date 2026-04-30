"""Per-viewer WS relay primitives. Currently a placeholder — the actual
broadcast logic lives on ``Hub`` in server.py. This module exists so future
features (per-viewer subscriptions, server-side filtering, recording) have a
clear home without bloating server.py.
"""

from __future__ import annotations
