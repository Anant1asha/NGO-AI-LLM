"""
Google HTTP Client

A dedicated, scalable HTTP client for Google APIs.
It abstracts away the OAuth token lifecycle and provides clean HTTP verbs
so that individual services (Gmail, Drive) can focus purely on business logic.
"""

import json
import time
from typing import TYPE_CHECKING, Any

import httpx

from hachi.core.idempotency import IdempotencyGuard
from hachi.core.oauth import OAuthManager

if TYPE_CHECKING:
    from hachi.core.approvals import ActionApprover


class GoogleHTTPClient:
    """
    Manages authenticated HTTP connections to Google Workspace APIs.
    Features lazy authentication to prevent blocking agent boot.
    """

    BASE_URL = "https://www.googleapis.com"
    _RETRYABLE_STATUS_CODES = (429, 503)
    _MAX_RETRIES = 3
    _MAX_WAIT_SECONDS = 30

    def __init__(self, scopes: list[str]):
        """
        Initialize the client with required Google OAuth scopes.

        Args:
            scopes: A list of URL scopes required by the loaded services.
        """
        self.oauth = OAuthManager()
        self.scopes = scopes
        # Optional approver wired by the hub at session boot.  When set, destructive
        # actions call require_approval() before proceeding.
        self.approver: ActionApprover | None = None
        # Per-client (= per-session) dedup of opt-in side-effecting writes, so an LLM retry
        # or tool-pool re-dispatch within a turn cannot double-send an email / double-create
        # an event. Only POSTs that pass an idempotency_key are guarded (AUDIT Theme A).
        self._idem_guard = IdempotencyGuard()

    def _get_headers(self) -> dict[str, str]:
        """
        Retrieves the OAuth token and constructs the Authorization header.
        Triggers the browser flow only if the token is missing/expired.
        """
        token = self.oauth.get_google_credentials(self.scopes)
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }

    def _request_with_retry(
        self,
        client: httpx.Client,
        method: str,
        url: str,
        **kwargs: Any,
    ) -> httpx.Response:
        """
        Execute an HTTP request, retrying on 429/503 responses.

        Respects the ``Retry-After`` response header when present, capped at
        ``_MAX_WAIT_SECONDS``.  Raises ``httpx.HTTPStatusError`` on the final
        failure or on any non-retryable error status.

        Args:
            client: An already-open ``httpx.Client`` to use for the request.
            method: HTTP method string (``"GET"``, ``"POST"``, …).
            url: The URL or path to request.
            **kwargs: Extra keyword arguments forwarded to ``client.request``.

        Returns:
            The successful ``httpx.Response``.
        """
        response: httpx.Response
        for attempt in range(self._MAX_RETRIES + 1):
            response = client.request(method, url, **kwargs)
            if response.status_code in self._RETRYABLE_STATUS_CODES and attempt < self._MAX_RETRIES:
                wait = int(response.headers.get("Retry-After", "5"))
                time.sleep(min(wait, self._MAX_WAIT_SECONDS))
                continue
            if response.status_code == 403:
                self._raise_forbidden(url, response)
            if not response.is_success:
                self._raise_api_error(url, response)
            return response
        # Reached only when all retries were exhausted on a retryable status.
        self._raise_api_error(url, response)
        return response  # unreachable; satisfies type checker

    @staticmethod
    def _raise_api_error(url: str, response: httpx.Response) -> None:
        """Raise a human-readable error for any non-success response.

        Extracts the Google API ``error.message`` from the JSON body so the agent
        sees the actionable reason (e.g. "Missing time zone definition…") rather
        than the generic httpx "Client error 'NNN'… see MDN" message.
        """
        detail = ""
        try:
            body = response.json()
            err = body.get("error", {})
            detail = err.get("message", "") if isinstance(err, dict) else str(err)
        except Exception:
            detail = response.text.strip()
        raise RuntimeError(
            f"Google API error {response.status_code} for {url}" + (f": {detail}" if detail else "")
        )

    @staticmethod
    def _raise_forbidden(url: str, response: httpx.Response) -> None:
        """Raise a human-readable error for 403 responses.

        A 403 from the Google API almost always means the API is not enabled
        in the Cloud project, not an OAuth scope problem.
        """
        detail = ""
        try:
            body = response.json()
            err = body.get("error", {})
            detail = err.get("message", "") if isinstance(err, dict) else str(err)
        except Exception:
            detail = response.text.strip()

        # Detect "API not enabled" specifically — it has a consistent message pattern
        from urllib.parse import urlparse as _urlparse

        _parsed = _urlparse(url)
        if _parsed.scheme:  # absolute URL (e.g. https://people.googleapis.com/...)
            _host = _parsed.hostname or ""
            api_name = _host.split(".")[0].title() if "." in _host else _host
        else:  # relative URL (e.g. /drive/v3/files)
            _parts = url.lstrip("/").split("/")
            api_name = _parts[0] if _parts else url
        if "has not been used" in detail or "disabled" in detail or "enable" in detail.lower():
            hint = (
                f" — the {api_name} API is not enabled for your Google Cloud project. "
                "Go to https://console.cloud.google.com/apis/library, search for the API, "
                "and click Enable."
            )
        else:
            hint = (
                " — check that the API is enabled at https://console.cloud.google.com/apis/library "
                "and that your OAuth scopes are correct."
            )

        raise PermissionError(
            f"Google API returned 403 Forbidden for {url}"
            + (f": {detail}" if detail else "")
            + hint
        )

    def get(self, endpoint: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """Executes an authenticated GET request."""
        with httpx.Client(base_url=self.BASE_URL, headers=self._get_headers()) as client:
            response = self._request_with_retry(client, "GET", endpoint, params=params)
            return response.json()

    def post(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
        *,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        """Executes an authenticated POST request.

        When ``idempotency_key`` is supplied — by side-effecting create/send leaf tools —
        a duplicate POST with the same key inside the short dedup window replays the prior
        response instead of re-sending, so an LLM retry or tool-pool re-dispatch within a
        turn cannot double-send an email or double-create an event. Read/batch POSTs omit
        the key and are never deduped (they must always return fresh data).
        """
        if idempotency_key is None:
            return self._post_raw(endpoint, json_data, params)
        is_dup, prior = self._idem_guard.begin(idempotency_key)
        if is_dup:
            # Replay the prior success; an in-flight concurrent duplicate has no result yet.
            return json.loads(prior) if prior else {}
        try:
            result = self._post_raw(endpoint, json_data, params)
        except Exception:
            self._idem_guard.abort(idempotency_key)  # failed → leave it retryable
            raise
        self._idem_guard.finish(idempotency_key, json.dumps(result))
        return result

    def _post_raw(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None,
        params: dict[str, Any] | None,
    ) -> dict[str, Any]:
        with httpx.Client(base_url=self.BASE_URL, headers=self._get_headers()) as client:
            response = self._request_with_retry(
                client, "POST", endpoint, json=json_data, params=params
            )
            if not response.content:
                return {}
            result: dict[str, Any] = response.json()
            return result

    def patch(
        self,
        endpoint: str,
        json_data: dict[str, Any] | None = None,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Executes an authenticated PATCH request."""
        with httpx.Client(base_url=self.BASE_URL, headers=self._get_headers()) as client:
            response = self._request_with_retry(
                client, "PATCH", endpoint, json=json_data, params=params
            )
            if not response.content:
                return {}
            return response.json()

    def upload_multipart(
        self,
        endpoint: str,
        metadata: dict[str, Any],
        file_path: str,
        mime_type: str,
        params: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Executes an authenticated POST request with multipart/related data (metadata + file)."""
        import json
        from pathlib import Path

        path = Path(file_path)
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        token = self.oauth.get_google_credentials(self.scopes)
        # Do not use _get_headers() — httpx sets Content-Type with the correct multipart boundary.
        headers = {"Authorization": f"Bearer {token}"}

        metadata_json = json.dumps(metadata).encode("utf-8")

        with open(path, "rb") as f:
            file_data = f.read()

        files = {
            "metadata": ("metadata.json", metadata_json, "application/json"),
            "file": (path.name, file_data, mime_type),
        }

        with httpx.Client(base_url=self.BASE_URL, headers=headers) as client:
            response = self._request_with_retry(
                client, "POST", endpoint, files=files, params=params
            )
            if not response.content:
                return {}
            return response.json()

    def delete(self, endpoint: str, params: dict[str, Any] | None = None) -> None:
        """Executes an authenticated DELETE request."""
        with httpx.Client(base_url=self.BASE_URL, headers=self._get_headers()) as client:
            self._request_with_retry(client, "DELETE", endpoint, params=params)

    def require_approval(self, action: str, summary: str, detail: str = "") -> tuple[bool, str]:
        """Gate a destructive/outbound action behind the session approver.

        When an :class:`~hachi.core.approvals.ActionApprover` is wired (by the
        :class:`~hachi.integrations.google.GoogleIntegrationHub`), delegates to it.
        Without an approver the call fails safe — the action is blocked — because the
        tier policy is applied upstream when an approver exists and a bare client with
        no approver should never silently allow destructive operations.

        Args:
            action:  Canonical action name (e.g. ``"send_email"``, ``"trash_file"``).
            summary: Short human-readable description of what would happen.
            detail:  Optional extended context for the approval UI.

        Returns:
            ``(True, reason)`` if approved; ``(False, reason)`` if denied.
        """
        if self.approver is not None:
            return self.approver.require(action, summary, detail)
        # No approver wired → fail safe (deny). Tier policy is applied upstream when an
        # approver exists; a bare client with no approver denies destructive actions.
        return (False, "No approver connected for this session; destructive action blocked.")
