"""Hachi Cockpit — dark terminal cockpit for the hachi autonomous agent engine.

Public exports
--------------
CockpitApp    — self-contained Textual host; run standalone or embed in the main app.
CockpitScreen — the single surface (TrustBar + ContentSwitcher + CockpitFooter).
CockpitData   — data facade (wraps GatewayClient with offline fallback).
"""

from __future__ import annotations

from hachi.tui.cockpit.app import CockpitApp
from hachi.tui.cockpit.data import CockpitData
from hachi.tui.cockpit.screen import CockpitScreen

__all__ = ["CockpitApp", "CockpitScreen", "CockpitData"]
