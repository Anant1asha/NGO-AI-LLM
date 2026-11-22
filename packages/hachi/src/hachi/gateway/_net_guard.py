"""Gateway-layer SSRF guard for user-supplied outbound URLs.

Exposes :func:`is_safe_outbound_url` as the canonical check for any gateway code
that needs to validate a user-supplied URL before making an outbound request
(provider test-connection, voice STT/TTS ``base_url`` config, etc.).

The "is this address public?" decision is **delegated** to
:func:`hachi.core.net_guard.ip_is_public`. This module used to describe itself as
a "thin wrapper" while importing nothing and duplicating the predicate — and the
duplicate kept the pre-CGNAT behaviour when the core guard was hardened, which is
precisely how a documented guarantee rots. Only loopback policy is local.

``allow_loopback=True`` is used for local providers such as Ollama, where
connecting to ``http://localhost:11434`` is the expected case.

``allow_private`` mirrors the core guard's opt-in and defaults to the
``HACHI_REST_ALLOW_PRIVATE`` environment variable, so a self-hoster reaching a
tailnet (CGNAT / 100.64.0.0/10) Ollama endpoint or voice base URL keeps the same
escape hatch the channels already honour. Without it, prompting the guard for
CGNAT would silently lock out the self-hosted deployments this project targets.
"""

from __future__ import annotations

import os
import socket
from urllib.parse import urlparse

from hachi.core.net_guard import ip_is_public

_ALLOWED_SCHEMES = {"http", "https"}


def _env_allow_private() -> bool:
    """Read the documented opt-in, matching the channel senders' parsing."""
    return os.environ.get("HACHI_REST_ALLOW_PRIVATE", "").strip().lower() in {"1", "true", "yes"}


def is_safe_outbound_url(
    url: str,
    *,
    allow_loopback: bool = False,
    allow_private: bool | None = None,
) -> bool:
    """Return *True* when *url* is safe to send an outbound request to.

    Checks performed:
    - Scheme must be ``http`` or ``https``.
    - Host must be present.
    - Host resolves via DNS and every resolved address passes
      :func:`hachi.core.net_guard.ip_is_public`, except that loopback is
      permitted when *allow_loopback* is set and every IP check is skipped when
      *allow_private* is set.

    Args:
        url: The URL to validate.
        allow_loopback: When ``True``, loopback addresses (127.x.x.x, ``::1``,
            ``localhost``) are permitted. Use for local providers (Ollama).
        allow_private: When ``True``, skip the public-address requirement
            entirely — the same escape hatch core exposes, for overrides that
            deliberately target a private or overlay-network host. Defaults to
            the ``HACHI_REST_ALLOW_PRIVATE`` environment variable.

    Returns:
        ``True`` when the URL is safe; ``False`` otherwise.
    """
    if allow_private is None:
        allow_private = _env_allow_private()

    try:
        parsed = urlparse(url)
    except Exception:
        return False

    if parsed.scheme.lower() not in _ALLOWED_SCHEMES:
        return False

    host = parsed.hostname
    if not host:
        return False

    # Resolve the hostname to its IP(s).
    try:
        infos = socket.getaddrinfo(host, parsed.port, proto=socket.IPPROTO_TCP)
    except (socket.gaierror, OSError):
        return False

    addresses: set[str] = {str(info[4][0]) for info in infos}
    if not addresses:
        return False

    for raw_ip in addresses:
        # Explicit operator opt-in: skip every address check, exactly as the
        # core guard's allow_private does.
        if allow_private:
            continue

        # Loopback is exempted before the public-address test because 127/8 is
        # not public — the exemption must come first, and only when asked for.
        try:
            import ipaddress

            addr = ipaddress.ip_address(raw_ip)
        except ValueError:
            return False

        if addr.is_loopback:
            if not allow_loopback:
                return False
            continue  # allowed — skip remaining checks for this address

        if not ip_is_public(raw_ip):
            return False

    return True
