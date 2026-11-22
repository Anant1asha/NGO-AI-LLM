"""
Universal REST Adapter

This module provides the UniversalRestAdapter, which takes API definitions
parsed from .og files (`::api` blocks) and dynamically generates native Python
functions that execute the HTTP requests using `httpx`.

These dynamic functions are registered directly into the agent's ToolRegistry.
"""

import json
import os
import re

import httpx

from hachi.core.credential_vault import CredentialVault
from hachi.core.loop import ToolRegistry
from hachi.core.net_guard import ValidationResult
from hachi.core.net_guard import validate_outbound_url as _net_guard_validate
from hachi.core.secret_scanner import outbound_redaction_disabled, redact_secrets
from hachi.core.untrusted_content import guard_untrusted
from hachi.og_engine.parser import OGNode

# Safety cap so a verbose REST response can't flood the agent's context. Tools
# that need a tight result should declare `fields=` in their ::api block instead.
_MAX_REST_RESPONSE_CHARS = 6_000


def _redact_mapping_secrets(mapping: dict | None) -> tuple[dict | None, int]:
    """Redact provider-secret-pattern values (sk-ant-, AKIA, ghp_, …) from a params/json dict.

    REST auth is injected via vault-interpolated *headers*, never via these request
    kwargs, so this only strips a credential the agent accidentally placed in a query
    param or body — it never breaks a legitimate call. Returns ``(mapping, count)``.

    The opt-out (``HACHI_ALLOW_OUTBOUND_SECRETS``) is the shared outbound policy.
    """
    if mapping is None or outbound_redaction_disabled():
        return mapping, 0
    total = 0
    redacted: dict = {}
    for key, value in mapping.items():
        if isinstance(value, str):
            safe, count = redact_secrets(value)
            redacted[key] = safe
            total += count
        else:
            redacted[key] = value
    return redacted, total


def _truncate_rest_response(text: str, limit: int = _MAX_REST_RESPONSE_CHARS) -> str:
    """Cap an over-long REST response, telling the model how to get a tighter one."""
    if len(text) <= limit:
        return text
    dropped = len(text) - limit
    return (
        f"{text[:limit]}\n\n... [truncated {dropped} chars — add a `fields=` directive "
        "to this skill's ::api block to return only the keys you need]"
    )


class UniversalRestAdapter:
    """
    Dynamically generates native Python tools from .og ::api blocks and registers
    them with the ToolRegistry for LLM consumption.
    """

    def __init__(
        self,
        registry: ToolRegistry,
        vault: CredentialVault | None = None,
        allowed_hosts: list[str] | None = None,
    ):
        self.registry = registry
        self.vault = vault
        self.allowed_hosts = allowed_hosts or self._load_allowed_hosts_from_env()
        self._allow_private_egress = (
            os.environ.get("HACHI_REST_ALLOW_PRIVATE", "false").lower() == "true"
        )

    @staticmethod
    def _load_allowed_hosts_from_env() -> list[str]:
        raw = os.environ.get("HACHI_REST_ALLOWLIST", "")
        return [entry.strip().lower() for entry in raw.split(",") if entry.strip()]

    @staticmethod
    def _host_in_allowlist(host: str, allowlist: list[str]) -> bool:
        host = host.lower()
        for item in allowlist:
            if item.startswith("*."):
                suffix = item[1:].lower()  # includes leading dot
                if host.endswith(suffix) and host != suffix[1:]:
                    return True
            elif host == item.lower():
                return True
        return False

    def _validate_outbound_url(
        self, raw_url: str, includes_secret: bool
    ) -> tuple[str, ValidationResult] | tuple[None, None]:
        """Validate ``raw_url`` before sending a request.

        Delegates host/IP safety to :func:`~hachi.core.net_guard.validate_outbound_url`
        (the single source of truth for SSRF mitigations). Additional REST-layer checks
        (allowlist, secret-interpolation guard) are applied on top.

        Args:
            raw_url: The fully-interpolated URL about to be requested.
            includes_secret: Whether a vault-sourced credential was injected into headers.

        Returns:
            ``(None, None)`` if the URL is safe to request, or
            ``(error_string, None)`` that should be returned to the caller without making
            the request.  When safe, the second element is the :class:`ValidationResult`
            which carries the pre-resolved IP set — callers SHOULD use it to build a
            pinned connection and avoid a second DNS lookup (DNS-rebinding TOCTOU).
        """
        from urllib.parse import urlparse

        try:
            parsed = urlparse(raw_url)
        except Exception:
            return "Invalid URL format", None

        host = parsed.hostname
        if not host:
            return "URL hostname is required", None

        host_lc = host.lower()
        # BB-53: fail CLOSED when no allowlist is configured. An empty/unset
        # HACHI_REST_ALLOWLIST means NO outbound REST host is permitted — it must
        # never be treated as "no restriction" (that was the fail-open bug).
        if not self.allowed_hosts:
            return (
                f"Host '{host_lc}' is not allowed: HACHI_REST_ALLOWLIST is not configured "
                "(fails closed — configure it to permit any outbound REST host)",
                None,
            )
        if not self._host_in_allowlist(host_lc, self.allowed_hosts):
            return f"Host '{host_lc}' is not allowed by HACHI_REST_ALLOWLIST", None

        result = _net_guard_validate(raw_url, allow_private=self._allow_private_egress)
        if not result.ok:
            return str(result.reason), None

        return None, result

    def register_node_apis(self, node: OGNode):
        """Parses all API definitions in an OGNode and registers them as tools."""
        for tool_name, api_def in node.api_defs.items():
            self._register_single_api(tool_name, api_def, node.name)

    def _register_single_api(self, tool_name: str, api_def: dict[str, str], node_name: str):
        method = api_def.get("method", "GET").upper()
        endpoint = api_def.get("endpoint", "")
        base_desc = api_def.get("description", f"Execute {method} request to {endpoint}")

        # Force the LLM to read the .og behavioral instructions
        # before blindly calling the raw REST endpoint.
        description = (
            f"{base_desc}\n\nIMPORTANT: You MUST call `load_skill('{node_name}')` BEFORE using "
            "this tool to understand its required context and safety assertions!"
        )

        # Parse schema into proper LLM properties
        raw_schema = {}
        if "schema" in api_def:
            # We already validated it's valid JSON in Phase 1
            raw_schema = json.loads(api_def["schema"])

        properties = {}
        required_fields = []
        for k, v in raw_schema.items():
            if isinstance(v, str):
                properties[k] = {"type": v, "description": f"Parameter: {k}"}
                required_fields.append(k)
            elif isinstance(v, dict):
                properties[k] = v  # Assume it's already a proper JSON Schema dict
                required_fields.append(k)

        llm_schema = {
            "name": tool_name,
            "description": description,
            "input_schema": {
                "type": "object",
                "properties": properties,
                "required": required_fields,
            },
        }

        raw_headers_str = api_def.get("headers", "{}")

        # The dynamic function that will be executed
        def dynamic_api_tool(**kwargs) -> str:
            # 1. Prepare Endpoint (replace path params if any exist in endpoint string)
            url = endpoint
            for k, v in kwargs.items():
                if f"{{{k}}}" in url:
                    url = url.replace(f"{{{k}}}", str(v))

            # 2. Prepare Headers (inject vault tokens & default headers)
            try:
                headers = json.loads(raw_headers_str)
                secret_interpolated = False

                # Inject standard bot headers to prevent 403 blocks
                # from public APIs (like Wikipedia, CoinGecko, ipapi) that reject default
                # python-httpx agents.
                header_keys = {k.lower() for k in headers.keys()}
                if "user-agent" not in header_keys:
                    headers["User-Agent"] = (
                        "Hachi-Omni-Orchestrator/1.0 (https://github.com/OpenGigantic/hachi)"
                    )
                if "accept" not in header_keys:
                    headers["Accept"] = "application/json, text/plain, */*"

                # Dynamic interception of vault variables like {whatsapp_api_token}
                for k, v in headers.items():
                    if isinstance(v, str):
                        matches = re.findall(r"\{([a-zA-Z0-9_]+)\}", v)
                        for vault_key in matches:
                            normalized_header = k.lower().strip()
                            if normalized_header in {"host", "x-forwarded-host", "forwarded"}:
                                return (
                                    f"Error: Header '{k}' is not allowed. "
                                    "Host-routing headers are blocked by outbound policy."
                                )
                            if normalized_header not in {
                                "authorization",
                                "x-api-key",
                                "api-key",
                                "x-auth-token",
                            }:
                                return (
                                    f"Error: Secret interpolation in header '{k}' is not allowed. "
                                    "Use Authorization/x-api-key style headers only."
                                )
                            if self.vault:
                                vault_val = self.vault.get_token(vault_key)
                                if vault_val:
                                    v = v.replace(f"{{{vault_key}}}", vault_val)
                                    secret_interpolated = True
                                else:
                                    return (
                                        f"Error: Missing secret '{vault_key}' in credential vault."
                                    )
                            else:
                                return (
                                    "Error: No credential vault configured for secret "
                                    "interpolation."
                                )
                        headers[k] = v
            except Exception as e:
                return f"Error parsing headers: {e}"

            # 3. Prepare Payload/Query
            params = {}
            json_payload = {}

            # Separate body payload vs query params based on HTTP method
            # Path params were already injected into the URL
            for k, v in kwargs.items():
                if f"{{{k}}}" not in endpoint:
                    if method in ("GET", "DELETE"):
                        params[k] = v
                    else:
                        json_payload[k] = v

            # Clean up empty payloads
            params = params if params else None
            json_payload = json_payload if json_payload else None

            # Scrub accidental provider secrets from the outbound request so a key the
            # agent happened to read can't be exfiltrated to a third-party API. Vault
            # auth uses headers (above), not these kwargs, so this never strips a real
            # credential. Opt out with HACHI_ALLOW_OUTBOUND_SECRETS=true.
            params, _redacted_params = _redact_mapping_secrets(params)
            json_payload, _redacted_body = _redact_mapping_secrets(json_payload)

            # 4. Execute HTTP Request
            validation_error, net_result = self._validate_outbound_url(
                url, includes_secret=secret_interpolated
            )
            if validation_error:
                return f"Blocked by outbound policy: {validation_error}"

            try:
                from urllib.parse import urlparse as _urlparse

                # DNS-pinning: connect to the IP we resolved during validation rather
                # than letting httpx re-resolve the hostname (DNS-rebinding TOCTOU fix).
                # When net_result has resolved IPs, pick one and substitute it into the
                # URL; set the Host header so TLS SNI and virtual-hosting still work.
                connect_url = url
                if net_result is not None and net_result.resolved_ips:
                    _parsed = _urlparse(url)
                    _pinned_ip = next(iter(net_result.resolved_ips))
                    # Format IPv6 addresses with brackets as required by RFC 2732.
                    _ip_host = f"[{_pinned_ip}]" if ":" in _pinned_ip else _pinned_ip
                    # Preserve the original Host header if the caller set one (blocked
                    # by the header policy above, so in practice we set it ourselves).
                    if "host" not in {k.lower() for k in headers}:
                        headers["Host"] = _parsed.hostname or ""
                    _port = _parsed.port
                    _netloc = f"{_ip_host}:{_port}" if _port else _ip_host
                    connect_url = _parsed._replace(netloc=_netloc).geturl()

                # follow_redirects=False is explicit: a 3xx to an internal host is a
                # classic SSRF bypass of the public-host check above. DNS-rebinding
                # TOCTOU is closed by connecting to the pinned IP above.
                with httpx.Client(timeout=15.0, follow_redirects=False) as client:
                    response = client.request(
                        method=method,
                        url=connect_url,
                        headers=headers,
                        params=params,
                        json=json_payload,
                    )
                    response.raise_for_status()

                    try:
                        data = response.json()
                    except json.JSONDecodeError:
                        text = _truncate_rest_response(response.text)
                        guarded, _flagged = guard_untrusted(text, source=url)
                        return guarded

                    # Optional .og field projection: an ::api block may declare
                    # `fields=a, b` to return only those top-level keys, keeping
                    # tool output (and token cost) tight. Falls back to the full
                    # response, then a generic size cap as a last resort.
                    fields = api_def.get("fields")
                    if fields and isinstance(data, dict):
                        wanted = [f.strip() for f in fields.split(",") if f.strip()]
                        projected = {k: data[k] for k in wanted if k in data}
                        if projected:
                            data = projected

                    result = _truncate_rest_response(json.dumps(data, indent=2))
                    # Spotlight third-party API responses: if the payload carries a
                    # prompt-injection, wrap it so the model treats it as data only.
                    guarded, _flagged = guard_untrusted(result, source=url)
                    return guarded

            except httpx.HTTPStatusError as exc:
                return f"HTTP Error {exc.response.status_code}: {exc.response.text}"
            except httpx.RequestError as exc:
                return f"Request Error: {str(exc)}"
            except Exception as exc:
                return f"Unexpected Error: {str(exc)}"

        # Set the name of the function to the tool name (helps with debugging stack traces)
        dynamic_api_tool.__name__ = tool_name

        # Register the dynamic function with the ToolRegistry under the skill's group,
        # so load_skill(node_name) lazily unlocks exactly this skill's REST tools.
        self.registry.register(llm_schema, dynamic_api_tool, group=node_name)
