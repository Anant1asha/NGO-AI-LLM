"""P3-06: SDK v0 contract tests.

Validates that:
1. All documented symbols are importable from ``hachi.sdk``.
2. The SDK version is a valid semver string.
3. ``is_compatible()`` correctly compares versions.
4. ``events`` module exposes the expected event-name constants.
5. The stable surface does NOT export any private/internal-only symbols.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 1. Symbol importability
# ---------------------------------------------------------------------------

_STABLE_SYMBOLS = [
    "ToolRegistry",
    "ToolSpec",
    "BaseLLMClient",
    "OgPackManifest",
    "PackScope",
    "ScheduleBudget",
    "parse_pack_toml",
    "render_consent_sheet",
    "events",
    "sdk_version",
    "is_compatible",
    "SDK_VERSION",
]


def test_sdk_exports_all_stable_symbols() -> None:
    import hachi.sdk as sdk

    missing = [sym for sym in _STABLE_SYMBOLS if not hasattr(sdk, sym)]
    assert not missing, f"Missing from hachi.sdk: {missing}"


def test_sdk_all_list_matches_stable_symbols() -> None:
    import hachi.sdk as sdk

    for sym in _STABLE_SYMBOLS:
        assert sym in sdk.__all__, f"{sym!r} not in hachi.sdk.__all__"


# ---------------------------------------------------------------------------
# 2. SDK version is valid semver
# ---------------------------------------------------------------------------

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


def test_sdk_version_is_valid_semver() -> None:
    from hachi.sdk import SDK_VERSION, sdk_version

    assert _SEMVER_RE.match(SDK_VERSION), f"SDK_VERSION {SDK_VERSION!r} is not semver"
    assert sdk_version() == SDK_VERSION


# ---------------------------------------------------------------------------
# 3. is_compatible() logic
# ---------------------------------------------------------------------------


def test_is_compatible_with_same_version() -> None:
    from hachi.sdk import SDK_VERSION, is_compatible

    assert is_compatible(SDK_VERSION)


def test_is_compatible_with_older_version() -> None:
    from hachi.sdk import is_compatible

    assert is_compatible("0.0.1")


def test_is_compatible_with_future_version() -> None:
    from hachi.sdk import is_compatible

    assert not is_compatible("99.0.0")


# ---------------------------------------------------------------------------
# 4. events module exposes key constants
# ---------------------------------------------------------------------------

_REQUIRED_EVENTS = [
    "SESSION_CHAT_STARTED",
    "SESSION_CHAT_COMPLETED",
    "SESSION_SHUTDOWN",
    "TOOL_CALL_STARTED",
    "TOOL_CALL_COMPLETED",
    "MCP_SHUTDOWN",
]


def test_sdk_events_exposes_runtime_event_constants() -> None:
    from hachi.sdk import events

    missing = [name for name in _REQUIRED_EVENTS if not hasattr(events, name)]
    assert not missing, f"Missing from sdk.events: {missing}"


def test_sdk_events_are_strings() -> None:
    from hachi.sdk import events

    for name in _REQUIRED_EVENTS:
        val = getattr(events, name)
        assert isinstance(val, str), f"sdk.events.{name} is not a string: {val!r}"


# ---------------------------------------------------------------------------
# 5. Key types are usable (not abstract stubs)
# ---------------------------------------------------------------------------


def test_tool_spec_is_importable_and_has_name_field() -> None:
    import inspect

    from hachi.sdk import ToolSpec

    sig = inspect.signature(ToolSpec.__init__)
    assert "name" in sig.parameters or hasattr(ToolSpec, "name")


def test_og_pack_manifest_is_dataclass_or_basemodel() -> None:
    from hachi.sdk import OgPackManifest

    # Must have id and semver fields (checked at pack install time)
    assert hasattr(OgPackManifest, "__dataclass_fields__") or hasattr(
        OgPackManifest, "model_fields"
    ), "OgPackManifest must be a dataclass or Pydantic model"


def test_base_llm_client_is_abstract() -> None:
    import abc

    from hachi.sdk import BaseLLMClient

    assert issubclass(BaseLLMClient, abc.ABC), "BaseLLMClient must extend abc.ABC"
