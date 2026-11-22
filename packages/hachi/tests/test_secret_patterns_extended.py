"""Tests for the additional secret-scanner patterns (Stripe, GitHub fine-grained
PAT, Google OAuth, SendGrid, npm, JWT)."""

from __future__ import annotations

import pytest

from hachi.core.secret_scanner import (
    REDACTION_PLACEHOLDER,
    contains_secret,
    find_secret_kinds,
    redact_secrets,
)

_GH_PAT = "github_pat_" + "a" * 40
_GOOGLE_OAUTH = "GOCSPX-" + "a" * 24
_STRIPE = "sk_live_" + "a" * 24
_SENDGRID = "SG." + "a" * 22 + "." + "b" * 22
_NPM = "npm_" + "a" * 36
_JWT = "eyJ" + "abcdefghijklmno" + "." + "abcdefghijklmno" + "." + "abcdefghijklmno"


@pytest.mark.parametrize(
    "secret,kind",
    [
        (_GH_PAT, "github_fine_grained_pat"),
        (_GOOGLE_OAUTH, "google_oauth_secret"),
        (_STRIPE, "stripe_key"),
        (_SENDGRID, "sendgrid_key"),
        (_NPM, "npm_token"),
        (_JWT, "jwt"),
    ],
)
def test_detects_and_redacts_new_kinds(secret: str, kind: str) -> None:
    assert contains_secret(secret)
    assert kind in find_secret_kinds(secret)
    redacted, count = redact_secrets(secret)
    assert count >= 1
    assert REDACTION_PLACEHOLDER in redacted
    assert secret not in redacted


def test_redacted_inside_surrounding_text() -> None:
    redacted, count = redact_secrets(f"my stripe key is {_STRIPE} keep it safe")
    assert count == 1
    assert _STRIPE not in redacted
    assert "keep it safe" in redacted


@pytest.mark.parametrize(
    "benign",
    [
        "Run npm install to add the dependency.",
        "The GitHub repo is at github.com/OpenGigantic/hachi.",
        "Decode the base64 string before parsing.",
        "Use sk_test mode only after configuring the webhook.",  # 'sk_test' w/o full key
    ],
)
def test_no_false_positive_on_benign_text(benign: str) -> None:
    assert not contains_secret(benign)
    assert find_secret_kinds(benign) == []
