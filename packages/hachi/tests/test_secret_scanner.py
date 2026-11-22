"""Tests for the outbound secret-leak guard (core/secret_scanner)."""

from __future__ import annotations

import pytest

from hachi.core.secret_scanner import (
    REDACTION_PLACEHOLDER,
    contains_secret,
    find_secret_kinds,
    redact_secrets,
)

_ANTHROPIC = "sk-ant-" + "a" * 40
_OPENAI = "sk-" + "A" * 40
_AWS = "AKIA" + "ABCDEFGHIJKLMNOP"
_GITHUB = "ghp_" + "a" * 36
_SLACK = "xoxb-1234567890-abcdefABCDEF"
_GOOGLE = "AIza" + "a" * 35
_PRIVATE_KEY = "-----BEGIN RSA PRIVATE KEY-----\nMIIabc123\nDEF456\n-----END RSA PRIVATE KEY-----"


@pytest.mark.parametrize(
    "secret,kind",
    [
        (_ANTHROPIC, "anthropic_key"),
        (_OPENAI, "openai_key"),
        (_AWS, "aws_access_key"),
        (_GITHUB, "github_token"),
        (_SLACK, "slack_token"),
        (_GOOGLE, "google_api_key"),
        (_PRIVATE_KEY, "private_key"),
    ],
)
def test_detects_each_secret_kind(secret: str, kind: str) -> None:
    assert contains_secret(secret)
    assert kind in find_secret_kinds(secret)
    redacted, count = redact_secrets(secret)
    assert count >= 1
    assert REDACTION_PLACEHOLDER in redacted
    # The raw secret material must be gone.
    assert secret not in redacted


def test_redacts_secret_inside_surrounding_text() -> None:
    text = f"Here is my key: {_ANTHROPIC} please keep it safe"
    redacted, count = redact_secrets(text)
    assert count == 1
    assert "sk-ant-" not in redacted
    assert "please keep it safe" in redacted  # surrounding text preserved


def test_counts_multiple_secrets() -> None:
    text = f"{_AWS} and {_GITHUB} and {_GOOGLE}"
    _redacted, count = redact_secrets(text)
    assert count == 3


def test_clean_text_is_untouched() -> None:
    text = "Deploy the app to production and notify the team in #ops."
    assert not contains_secret(text)
    assert find_secret_kinds(text) == []
    redacted, count = redact_secrets(text)
    assert count == 0
    assert redacted == text


def test_private_key_block_redacted_as_unit() -> None:
    redacted, count = redact_secrets(_PRIVATE_KEY)
    assert count == 1
    assert "MIIabc123" not in redacted  # body gone, not just the header
