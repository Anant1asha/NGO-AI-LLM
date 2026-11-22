"""Load :class:`~hachi.core.routing.descriptor.ModelDescriptor` objects from JSON.

The bundled registry lives at ``src/hachi/data/model-registry.json``.  A user-local
override file at ``config_dir/model-registry.json`` is merged on top (last entry
for a given ``id`` wins), so operators can add or price-correct models without
touching code.

``status`` filtering:
    * ``"active"``      → included in routing candidates (default when absent).
    * ``"deprecated"``  → included (resolvable) but deprioritized (tier_rank bumped).
    * ``"disabled"``    → excluded from routing; still priced (for cost look-ups).

Adding a new model is a JSON-only edit; no Python change required.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from hachi.core.routing.capability import Capability
from hachi.core.routing.descriptor import ModelDescriptor, Pricing

logger = logging.getLogger(__name__)

_BUNDLED_JSON = Path(__file__).parent.parent.parent / "data" / "model-registry.json"

_CAPABILITY_MAP: dict[str, Capability] = {c.name: c for c in Capability}

_DEPRECATED_TIER_PENALTY = 200


def _parse_entry(entry: dict[str, Any]) -> ModelDescriptor | None:
    """Parse one JSON entry into a :class:`ModelDescriptor`, returning ``None`` on error."""
    try:
        raw_caps: list[str] = entry.get("capabilities", [])
        caps: frozenset[Capability] = frozenset(
            _CAPABILITY_MAP[c] for c in raw_caps if c in _CAPABILITY_MAP
        )
        if len(caps) != len(raw_caps):
            unknown = [c for c in raw_caps if c not in _CAPABILITY_MAP]
            logger.warning(
                "model-registry.json: unknown capabilities %s in %s", unknown, entry.get("id")
            )

        pricing: Pricing | None = None
        if "input_per_mtok" in entry and "output_per_mtok" in entry:
            pricing = Pricing(
                input_per_mtok=float(entry["input_per_mtok"]),
                output_per_mtok=float(entry["output_per_mtok"]),
                cache_read_mult=float(entry.get("cache_read_mult", 0.1)),
                cache_write_mult=float(entry.get("cache_write_mult", 1.25)),
            )

        tier_rank: int = int(entry.get("tier_rank", 50))
        status: str = str(entry.get("status", "active")).lower()
        if status == "deprecated":
            tier_rank += _DEPRECATED_TIER_PENALTY

        return ModelDescriptor(
            id=str(entry["id"]),
            provider=str(entry.get("provider", "")),
            capabilities=caps,
            context_window=int(entry.get("context_window", 128_000)),
            max_output=int(entry.get("max_output", 4_096)),
            pricing=pricing,
            supports_tools=bool(entry.get("supports_tools", True)),
            supports_streaming=bool(entry.get("supports_streaming", True)),
            tier_rank=tier_rank,
        )
    except (KeyError, TypeError, ValueError) as exc:
        logger.warning("model-registry.json: skipping malformed entry %r: %s", entry.get("id"), exc)
        return None


def load_model_registry_json(
    override_path: Path | None = None,
) -> list[ModelDescriptor]:
    """Return a list of :class:`ModelDescriptor` objects from the bundled JSON + user override.

    Args:
        override_path: Optional path to a user-local ``model-registry.json``.  When
            ``None``, ``config_dir/model-registry.json`` is NOT loaded (pure bundled).
            Pass ``get_hachi_paths().config_dir / "model-registry.json"`` at call sites
            that want the full merge.

    Returns:
        A list of descriptors, with ``status="disabled"`` entries excluded.  Within the
        list, later entries (user overrides) shadow bundled entries with the same ``id``.
    """
    by_id: dict[str, dict[str, Any]] = {}

    def _load(path: Path) -> None:
        if not path.exists():
            return
        try:
            entries = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(entries, list):
                logger.warning("model-registry.json at %s is not a JSON array; skipped", path)
                return
            for entry in entries:
                if isinstance(entry, dict) and "id" in entry:
                    by_id[str(entry["id"])] = entry
        except (json.JSONDecodeError, OSError) as exc:
            logger.warning("Failed to load model-registry.json from %s: %s", path, exc)

    _load(_BUNDLED_JSON)
    if override_path is not None:
        _load(override_path)

    result: list[ModelDescriptor] = []
    for entry in by_id.values():
        status = str(entry.get("status", "active")).lower()
        if status == "disabled":
            continue
        desc = _parse_entry(entry)
        if desc is not None:
            result.append(desc)

    return result
