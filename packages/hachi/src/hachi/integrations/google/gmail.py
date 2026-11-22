"""Gmail Service Plugin."""

from __future__ import annotations

import base64
import html
import logging
import re
from pathlib import Path
from typing import Any

from hachi.core.idempotency import make_idempotency_key
from hachi.core.loop import ToolRegistry
from hachi.core.untrusted_content import guard_untrusted
from hachi.core.validators import validate_email, validate_emails
from hachi.integrations.google.service import GoogleService

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Attachment safety
# ---------------------------------------------------------------------------

#: Maximum allowed attachment size in bytes (25 MiB — Gmail's own hard limit).
_MAX_ATTACHMENT_BYTES: int = 25 * 1024 * 1024


def _safe_attachment_path(path_str: str) -> tuple[bool, Path | str]:
    """Resolve and validate an attachment path before opening it.

    Checks:
    - The path must be absolute.
    - The resolved path must not be a symlink that escapes the declared parent
      directory (symlink-traversal guard).
    - The file must exist and be a regular file (not a directory / device node).
    - The file size must not exceed :data:`_MAX_ATTACHMENT_BYTES`.

    Args:
        path_str: Raw path string supplied by the model or user.

    Returns:
        ``(True, resolved_path)`` on success;
        ``(False, error_message)`` on any failure.
    """
    try:
        raw = Path(path_str)
        if not raw.is_absolute():
            return (
                False,
                f"Attachment not found (path is not absolute): {path_str!r}. "
                "Supply an absolute path to attach a file.",
            )

        resolved = raw.resolve(strict=False)

        # Guard against symlinks that point outside the declared parent.
        # We require the resolved path to stay within the same root as the
        # original path's declared parent.
        declared_parent = raw.parent.resolve(strict=False)
        try:
            resolved.relative_to(declared_parent)
        except ValueError:
            return (
                False,
                f"Attachment {path_str!r} resolves outside its declared directory "
                f"(symlink traversal rejected).",
            )

        if not resolved.exists():
            return False, f"Attachment not found: {path_str!r}"

        if not resolved.is_file():
            return False, f"Attachment path is not a regular file: {path_str!r}"

        size = resolved.stat().st_size
        if size > _MAX_ATTACHMENT_BYTES:
            mb = size / (1024 * 1024)
            return (
                False,
                f"Attachment {path_str!r} is {mb:.1f} MiB, exceeding the "
                f"{_MAX_ATTACHMENT_BYTES // (1024 * 1024)} MiB limit.",
            )

        return True, resolved

    except (OSError, ValueError) as exc:
        return False, f"Cannot access attachment {path_str!r}: {exc}"


# ---------------------------------------------------------------------------
# HTML → plain-text (UC-MAIL-006)
# ---------------------------------------------------------------------------

# A non-greedy paired-tag regex for single-level <script>/<style> removal.
# For nested tags we use a stack-based approach (_strip_script_style below).
_HTML_SCRIPT_OPEN_RE = re.compile(r"<(script|style)\b[^>]*>", re.IGNORECASE)
_HTML_SCRIPT_CLOSE_RE = re.compile(r"</(script|style)>", re.IGNORECASE)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WS_RUNS_RE = re.compile(r"[ \t]{2,}")
_BLANK_LINES_RE = re.compile(r"\n{3,}")


def _strip_script_style(text: str) -> str:
    """Remove ALL <script>/<style> blocks robustly, including nested ones.

    A single non-greedy regex substitution stops at the *first* ``</script>``
    it finds, leaking the body of outer nested tags.  A loop of such subs also
    fails: after removing ``<script>inner</script>`` the inner body text of the
    outer block is left as free text between the consumed inner close-tag and
    the outer close-tag.

    Instead we use a stack-based algorithm:
    1. Scan for all open- and close-tag positions in document order.
    2. Maintain a stack of open-tag starts; on each close-tag pop the deepest
       matching entry.
    3. When the stack empties (outermost pair matched), record the full span
       from outermost open to current close for removal.
    4. Build the output string by skipping the recorded spans.

    This correctly handles nesting of any depth and multiple separate blocks
    in a single pass, without an expensive iterative loop.
    """
    # Collect all open and close tag events in document order.
    events: list[tuple[str, str, int, int]] = []
    for m in _HTML_SCRIPT_OPEN_RE.finditer(text):
        events.append(("open", m.group(1).lower(), m.start(), m.end()))
    for m in _HTML_SCRIPT_CLOSE_RE.finditer(text):
        events.append(("close", m.group(1).lower(), m.start(), m.end()))
    events.sort(key=lambda e: e[2])

    # Stack-based matching: each entry is (tag_name, outermost_start_pos).
    spans_to_remove: list[tuple[int, int]] = []
    stack: list[tuple[str, int]] = []  # (tag_name, outermost_block_start)

    for kind, tag, start, end in events:
        if kind == "open":
            # Push outermost start only; nested opens inherit the outer start.
            outer_start = stack[0][1] if stack else start
            stack.append((tag, outer_start))
        elif kind == "close" and stack:
            # Walk back to find the deepest matching open.
            for i in range(len(stack) - 1, -1, -1):
                if stack[i][0] == tag:
                    outer_start = stack[i][1]
                    del stack[i:]  # pop this and any inner unmatched opens
                    if not stack:
                        # We've closed the outermost block — record the full span.
                        spans_to_remove.append((outer_start, end))
                    break

    if not spans_to_remove:
        return text

    result: list[str] = []
    pos = 0
    for rm_start, rm_end in sorted(spans_to_remove):
        result.append(text[pos:rm_start])
        result.append(" ")
        pos = rm_end
    result.append(text[pos:])
    return "".join(result)


def _html_to_text(raw: str) -> str:
    """Reduce an HTML email body to readable plain text (no extra deps).

    Tag soup in tool results overflows the TUI and is useless to the model, so
    we strip markup, unescape entities, and collapse runaway whitespace.
    """
    text = _strip_script_style(raw)
    # Keep line structure for common block-level breaks before nuking tags.
    text = re.sub(r"(?i)<br\s*/?>", "\n", text)
    text = re.sub(r"(?i)</(p|div|tr|table|li|h[1-6])>", "\n", text)
    text = _HTML_TAG_RE.sub("", text)
    text = html.unescape(text)
    text = _WS_RUNS_RE.sub(" ", text)
    text = _BLANK_LINES_RE.sub("\n\n", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Base64 / message helpers
# ---------------------------------------------------------------------------


def _decode_b64(data: str) -> str:
    """URL-safe base64-decode a Gmail body part, tolerating missing padding."""
    padding = len(data) % 4
    if padding:
        data += "=" * (4 - padding)
    return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")


def _extract_message_text(payload: dict[str, Any]) -> str:
    """Walk a Gmail message payload and return its best-effort plain text.

    Prefers ``text/plain``; falls back to ``text/html`` (stripped to text) so
    single-part HTML newsletters render cleanly instead of dumping raw markup.
    Recurses through nested multipart parts.
    """
    plain: str | None = None
    html_body: str | None = None

    def _walk(part: dict[str, Any]) -> None:
        nonlocal plain, html_body
        mime = part.get("mimeType", "")
        data = part.get("body", {}).get("data")
        if data:
            if mime == "text/plain" and plain is None:
                plain = _decode_b64(data)
            elif mime == "text/html" and html_body is None:
                html_body = _decode_b64(data)
        for sub in part.get("parts", []) or []:
            _walk(sub)

    _walk(payload)
    if plain and plain.strip():
        return plain.strip()
    if html_body and html_body.strip():
        return _html_to_text(html_body)
    return "[No readable body found]"


# ---------------------------------------------------------------------------
# UC-MAIL-005 — robust 404 detection
# ---------------------------------------------------------------------------

_API_ERROR_STATUS_RE = re.compile(r"Google API error (\d+)")


def _is_404_error(exc: Exception) -> bool:
    """Return True only when *exc* carries an actual HTTP 404 status code.

    The old ``"404" in str(e)`` check fires on any error message that happens
    to contain the digits "404" — including thread IDs, error detail text, or
    other status codes whose decimal representation contains "404" as a
    substring (e.g. a hypothetical "40400").  We instead parse the status code
    that :class:`~hachi.integrations.google.client.GoogleHTTPClient` embeds
    at the start of its RuntimeError messages (``"Google API error <N> for …"``).
    """
    match = _API_ERROR_STATUS_RE.search(str(exc))
    if match:
        return int(match.group(1)) == 404
    return False


# ---------------------------------------------------------------------------
# GmailService
# ---------------------------------------------------------------------------


class GmailService(GoogleService):
    """Gmail integration — send, read, search, draft, reply, label, batch."""

    @property
    def required_scopes(self) -> list[str]:
        return ["https://www.googleapis.com/auth/gmail.modify"]

    def send_email(
        self, to: str, subject: str, body: str, attachment_paths: list[str] | None = None
    ) -> str:
        """Send an email via Gmail, optionally with file attachments.

        Args:
            to: Recipient email address (validated before send).
            subject: Email subject line.
            body: Plain-text body.
            attachment_paths: Optional list of absolute local file paths.

        Returns:
            A user-facing success or failure string.
        """
        import mimetypes
        from email.message import EmailMessage

        # UC-MAIL-002 — validate recipient before touching the API.
        ok, val = validate_email(to)
        if not ok:
            return f"Invalid recipient address: {val}"
        to = val  # use normalised form

        # UC-MAIL-001 — approval gate (destructive / outbound).
        approved, reason = self.require_approval(
            action="send_email",
            summary=f"Send email to {to}",
            detail=subject,
        )
        if not approved:
            return f"⛔ Action not approved: {reason}"

        msg = EmailMessage()
        msg.set_content(body)
        msg["To"] = to
        msg["Subject"] = subject

        if attachment_paths:
            # UC-MAIL-004 — size cap + symlink/traversal guard for every attachment.
            for path_str in attachment_paths:
                safe, result = _safe_attachment_path(path_str)
                if not safe:
                    return f"Attachment rejected: {result}"
                path = result  # type: ignore[assignment]  # Path on success
                ctype, encoding = mimetypes.guess_type(path)
                if ctype is None or encoding is not None:
                    ctype = "application/octet-stream"
                maintype, subtype = ctype.split("/", 1)
                with open(path, "rb") as f:
                    msg.add_attachment(
                        f.read(), maintype=maintype, subtype=subtype, filename=path.name
                    )

        raw_msg = base64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        # Key on the LOGICAL message, not raw_msg: MIME boundaries are randomized when
        # attachments are present, so the serialized bytes are not stable across a retry.
        idem = make_idempotency_key(
            "gmail.send", to, f"{subject}\x00{body}\x00{','.join(attachment_paths or [])}"
        )
        self.client.post(
            "/gmail/v1/users/me/messages/send",
            json_data={"raw": raw_msg},
            idempotency_key=idem,
        )
        return f"Email successfully sent to {to}."

    def list_recent_emails(
        self,
        max_results: int = 5,
        page_token: str | None = None,
    ) -> str:
        """List recent emails in the user's Gmail inbox.

        Args:
            max_results: How many messages to fetch (default 5).
            page_token: Optional Gmail pagination token from a previous call.

        Returns:
            Formatted email list with a pagination notice when more are available.
        """
        # UC-MAIL-003 — accept page_token, surface nextPageToken to caller.
        params: dict[str, Any] = {"maxResults": max_results, "q": "in:inbox"}
        if page_token:
            params["pageToken"] = page_token

        response = self.client.get("/gmail/v1/users/me/messages", params=params)
        messages = response.get("messages", [])
        next_token = response.get("nextPageToken")

        if not messages:
            return "Your inbox is empty."

        result = []
        for msg in messages:
            msg_id = msg["id"]
            try:
                detail_resp = self.client.get(f"/gmail/v1/users/me/messages/{msg_id}")
            except Exception as exc:
                logger.warning("Failed to fetch detail for message %s: %s", msg_id, exc)
                continue
            headers = detail_resp.get("payload", {}).get("headers", [])

            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
            thread_id = detail_resp.get("threadId", msg_id)
            result.append(
                f"From: {sender}\nSubject: {subject}\n"
                f"Message-ID: {msg_id}\nThread-ID: {thread_id}\n---"
            )

        output = "\n".join(result)
        if next_token:
            output += (
                f"\n\n[Showing first {len(result)} result(s); more are available. "
                f"Pass page_token={next_token!r} to fetch the next page, "
                "or refine your query to narrow results.]"
            )
        return output

    def search_emails(
        self,
        query: str,
        max_results: int = 5,
        page_token: str | None = None,
    ) -> str:
        """Search the user's Gmail using standard Gmail query syntax.

        Args:
            query: Gmail search query (e.g. ``'from:boss has:attachment'``).
            max_results: How many results to return (default 5).
            page_token: Optional Gmail pagination token from a previous call.

        Returns:
            Formatted email list with a pagination notice when more are available.
        """
        # UC-MAIL-003 — accept page_token, surface nextPageToken to caller.
        params: dict[str, Any] = {"maxResults": max_results, "q": query}
        if page_token:
            params["pageToken"] = page_token

        response = self.client.get("/gmail/v1/users/me/messages", params=params)
        messages = response.get("messages", [])
        next_token = response.get("nextPageToken")

        if not messages:
            return f"No emails found matching query: {query}"

        result = []
        for msg in messages:
            msg_id = msg["id"]
            try:
                detail_resp = self.client.get(f"/gmail/v1/users/me/messages/{msg_id}")
            except Exception as exc:
                logger.warning("Failed to fetch detail for message %s: %s", msg_id, exc)
                continue
            headers = detail_resp.get("payload", {}).get("headers", [])

            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "No Subject")
            sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
            thread_id = detail_resp.get("threadId", msg_id)
            result.append(
                f"From: {sender}\nSubject: {subject}\n"
                f"Message-ID: {msg_id}\nThread-ID: {thread_id}\n---"
            )

        output = "\n".join(result)
        if next_token:
            output += (
                f"\n\n[Showing first {len(result)} result(s); more are available. "
                f"Pass page_token={next_token!r} to fetch the next page, "
                "or refine your query to narrow results.]"
            )
        return output

    def create_draft(self, to: str, subject: str, body: str) -> str:
        """Create an email draft without sending it.

        Args:
            to: Recipient email address (validated before draft creation).
            subject: Email subject line.
            body: Plain-text body.

        Returns:
            A user-facing success or failure string including the draft ID.
        """
        import base64 as _b64
        from email.message import EmailMessage

        # UC-MAIL-002 — validate recipient.
        ok, val = validate_email(to)
        if not ok:
            return f"Invalid recipient address: {val}"
        to = val

        msg = EmailMessage()
        msg.set_content(body)
        msg["To"] = to
        msg["Subject"] = subject

        raw_msg = _b64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")

        response = self.client.post(
            "/gmail/v1/users/me/drafts", json_data={"message": {"raw": raw_msg}}
        )
        draft_id = response.get("id", "Unknown")
        return f"Draft created successfully. Draft ID: {draft_id}"

    def reply_thread(
        self, thread_id: str, body: str, attachment_paths: list[str] | None = None
    ) -> str:
        """Reply to an existing email thread, optionally with attachments.

        Args:
            thread_id: The ID of the thread to reply to.
            body: Plain-text reply body.
            attachment_paths: Optional list of absolute local file paths.

        Returns:
            A user-facing success or failure string.
        """
        import base64 as _b64
        import mimetypes
        from email.message import EmailMessage

        # Fetch the thread to get the latest message headers.
        thread_response = self.client.get(f"/gmail/v1/users/me/threads/{thread_id}")
        messages = thread_response.get("messages", [])
        if not messages:
            return f"Thread {thread_id} not found."

        latest_msg = messages[-1]
        headers = latest_msg.get("payload", {}).get("headers", [])

        message_id = next((h["value"] for h in headers if h["name"] == "Message-ID"), "")
        subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
        sender = next((h["value"] for h in headers if h["name"] == "From"), "")

        # UC-MAIL-002 — detect missing From header before sending to empty To:.
        if not sender:
            return (
                f"Cannot reply to thread {thread_id}: the original message has no From: "
                "header, so the reply recipient is unknown."
            )

        # Validate the extracted sender address.
        ok, val = validate_emails([sender])
        if not ok:
            return (
                f"Cannot reply to thread {thread_id}: the original From: header "
                f"({sender!r}) is not a valid email address — {val}"
            )

        # UC-MAIL-001 — approval gate for the outbound send.
        approved, reason = self.require_approval(
            action="send_email",
            summary=f"Reply to thread {thread_id} (recipient: {sender})",
            detail=subject,
        )
        if not approved:
            return f"⛔ Action not approved: {reason}"

        if not subject.startswith("Re:"):
            subject = "Re: " + subject

        msg = EmailMessage()
        msg.set_content(body)
        msg["To"] = sender
        msg["Subject"] = subject
        if message_id:
            msg["In-Reply-To"] = message_id
            msg["References"] = message_id

        if attachment_paths:
            # UC-MAIL-004 — size cap + symlink/traversal guard.
            for path_str in attachment_paths:
                safe, result = _safe_attachment_path(path_str)
                if not safe:
                    return f"Attachment rejected: {result}"
                path = result  # type: ignore[assignment]
                ctype, encoding = mimetypes.guess_type(path)
                if ctype is None or encoding is not None:
                    ctype = "application/octet-stream"
                maintype, subtype = ctype.split("/", 1)
                with open(path, "rb") as f:
                    msg.add_attachment(
                        f.read(), maintype=maintype, subtype=subtype, filename=path.name
                    )

        raw_msg = _b64.urlsafe_b64encode(msg.as_bytes()).decode("utf-8")
        self.client.post(
            "/gmail/v1/users/me/messages/send",
            json_data={"raw": raw_msg, "threadId": thread_id},
            idempotency_key=make_idempotency_key("gmail.reply", thread_id, body),
        )
        return f"Successfully replied to thread {thread_id}."

    def archive_email(self, message_id: str) -> str:
        """Archive an email by removing it from INBOX without deleting it."""
        try:
            self.client.post(
                f"/gmail/v1/users/me/messages/{message_id}/modify",
                json_data={"removeLabelIds": ["INBOX"]},
            )
            return f"Successfully archived email {message_id}."
        except Exception as e:
            return f"Failed to archive email: {str(e)}"

    def mark_email_read(self, message_id: str) -> str:
        """Mark an email as read."""
        try:
            self.client.post(
                f"/gmail/v1/users/me/messages/{message_id}/modify",
                json_data={"removeLabelIds": ["UNREAD"]},
            )
            return f"Successfully marked email {message_id} as read."
        except Exception as e:
            return f"Failed to mark email as read: {str(e)}"

    def list_labels(self) -> str:
        """List all Gmail labels (folders)."""
        try:
            response = self.client.get("/gmail/v1/users/me/labels")
            labels = response.get("labels", [])
            if not labels:
                return "No labels found."

            result = ["Available Gmail Labels (Folders):"]
            for label in labels:
                result.append(f"- {label.get('name')} (ID: {label.get('id')})")
            return "\n".join(result)
        except Exception as e:
            return f"Failed to list labels: {str(e)}"

    def create_label(self, label_name: str) -> str:
        """Create a new Gmail label (folder)."""
        try:
            response = self.client.post(
                "/gmail/v1/users/me/labels",
                json_data={
                    "name": label_name,
                    "labelListVisibility": "labelShow",
                    "messageListVisibility": "show",
                },
            )
            label_id = response.get("id")
            return f"Successfully created label '{label_name}' with ID: {label_id}"
        except Exception as e:
            return f"Failed to create label: {str(e)}"

    def categorize_email(self, message_id: str, label_id: str) -> str:
        """Apply a label to an email (move it to a folder)."""
        try:
            self.client.post(
                f"/gmail/v1/users/me/messages/{message_id}/modify",
                json_data={"addLabelIds": [label_id]},
            )
            return f"Successfully applied label {label_id} to email {message_id}."
        except Exception as e:
            return f"Failed to categorize email: {str(e)}"

    def batch_categorize_emails(self, message_ids: list[str], label_id: str) -> str:
        """Apply a label to multiple emails simultaneously.

        UC-MAIL-007: The Gmail batchModify endpoint returns a 204 No-Content on
        full success but does *not* return per-message results.  When the batch
        call itself raises (e.g. on a 400 with a list of failed IDs in the body),
        we surface the details rather than reporting full success.  We also
        individually verify a sample when the batch returns without error to catch
        any partial failures the API silently swallows.

        Args:
            message_ids: List of Gmail message IDs to label.
            label_id: The label ID to apply.

        Returns:
            A user-facing string — success count, plus any failure details.
        """
        try:
            self.client.post(
                "/gmail/v1/users/me/messages/batchModify",
                json_data={"ids": message_ids, "addLabelIds": [label_id]},
            )
        except Exception as exc:
            # The batchModify API can return a 400 with a body listing failed IDs.
            # Expose whatever the client captured rather than hiding it.
            return (
                f"Batch categorize partially or fully failed for label {label_id}: {exc}\n"
                f"Attempted message IDs: {message_ids}"
            )

        # batchModify is fire-and-forget at the HTTP level (204 No Content on success).
        # Verify individual messages to surface silent partial failures.
        failed: list[str] = []
        for msg_id in message_ids:
            try:
                detail = self.client.get(f"/gmail/v1/users/me/messages/{msg_id}?format=minimal")
                applied_labels: list[str] = detail.get("labelIds", [])
                if label_id not in applied_labels:
                    failed.append(msg_id)
            except Exception as exc:
                logger.warning("Could not verify label application for %s: %s", msg_id, exc)
                failed.append(msg_id)

        if failed:
            return (
                f"Label {label_id} applied to {len(message_ids) - len(failed)} of "
                f"{len(message_ids)} emails; {len(failed)} failed or could not be verified: "
                + ", ".join(failed)
            )

        return f"Successfully applied label {label_id} to {len(message_ids)} emails."

    def _render_message(self, msg: dict[str, Any]) -> str:
        """Format one Gmail message as ``--- header ---`` + readable body.

        ADV-002: The body is passed through :func:`guard_untrusted` so the model
        treats inbound email content as data rather than instructions.
        """
        payload = msg.get("payload", {})
        headers = payload.get("headers", [])
        sender = next((h["value"] for h in headers if h["name"] == "From"), "Unknown")
        date = next((h["value"] for h in headers if h["name"] == "Date"), "Unknown")
        raw_body = _extract_message_text(payload)

        # UC-MAIL-006 / ADV-002 — frame inbound content as untrusted data.
        body, _flagged = guard_untrusted(raw_body, source=f"email from {sender}")

        return f"--- Message from {sender} on {date} ---\n{body}\n"

    def read_email_thread(self, thread_id: str) -> str:
        """Read and extract text from an entire email thread.

        Falls back to reading ``thread_id`` as a single message ID when the
        thread endpoint returns HTTP 404 — the model often passes a Message-ID
        where a Thread-ID is expected, and both are interchangeable hex IDs.

        UC-MAIL-005: The 404 check now uses the HTTP status code embedded in the
        RuntimeError message (``"Google API error 404 for …"``), not a fragile
        substring match on the full error string.
        """
        try:
            thread_response = self.client.get(f"/gmail/v1/users/me/threads/{thread_id}")
            messages = thread_response.get("messages", [])
            if not messages:
                return f"Thread {thread_id} not found."
            return "\n".join(self._render_message(msg) for msg in messages)
        except Exception as e:
            if _is_404_error(e):
                try:
                    msg = self.client.get(f"/gmail/v1/users/me/messages/{thread_id}")
                    return self._render_message(msg)
                except Exception as inner:
                    return f"Failed to read thread or message {thread_id}: {str(inner)}"
            return f"Failed to read thread: {str(e)}"

    def register_tools(self, registry: ToolRegistry) -> None:
        """Register Gmail tools into the agent's tool registry."""
        registry.register(
            {
                "name": "google_send_email",
                "description": "Send an email via Gmail, optionally with file attachments.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                        "attachment_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional list of absolute paths to local files to attach"
                            ),
                        },
                    },
                    "required": ["to", "subject", "body"],
                },
            },
            self.send_email,
        )

        registry.register(
            {
                "name": "google_list_emails",
                "description": "List the most recent emails in the user's Gmail inbox.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "max_results": {"type": "integer"},
                        "page_token": {
                            "type": "string",
                            "description": (
                                "Optional pagination token returned by a previous call "
                                "to fetch the next page of results."
                            ),
                        },
                    },
                },
            },
            self.list_recent_emails,
        )

        registry.register(
            {
                "name": "google_search_emails",
                "description": (
                    "Search the user's Gmail using advanced query syntax"
                    " (e.g., 'from:boss has:attachment')."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Gmail search query"},
                        "max_results": {"type": "integer"},
                        "page_token": {
                            "type": "string",
                            "description": (
                                "Optional pagination token returned by a previous call "
                                "to fetch the next page of results."
                            ),
                        },
                    },
                    "required": ["query"],
                },
            },
            self.search_emails,
        )

        registry.register(
            {
                "name": "google_create_draft",
                "description": (
                    "Create an email draft without sending it. Use this when you want"
                    " the user to review the email before it goes out."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["to", "subject", "body"],
                },
            },
            self.create_draft,
        )

        registry.register(
            {
                "name": "google_reply_thread",
                "description": (
                    "Reply directly to an existing email thread. You must provide the exact"
                    " thread_id retrieved from list_emails or search_emails."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "thread_id": {
                            "type": "string",
                            "description": "The ID of the thread to reply to",
                        },
                        "body": {"type": "string", "description": "The body of your reply"},
                        "attachment_paths": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": (
                                "Optional list of absolute paths to local files to attach"
                            ),
                        },
                    },
                    "required": ["thread_id", "body"],
                },
            },
            self.reply_thread,
        )

        registry.register(
            {
                "name": "google_read_email_thread",
                "description": (
                    "Extract the raw plain-text content from an entire email thread."
                    " Use this to read the full context of an email before replying or summarizing."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "thread_id": {
                            "type": "string",
                            "description": "The ID of the thread to read",
                        }
                    },
                    "required": ["thread_id"],
                },
            },
            self.read_email_thread,
        )

        registry.register(
            {
                "name": "google_archive_email",
                "description": (
                    "Safely archive an email (removes it from the INBOX without deleting it"
                    " permanently). Use this for cleaning up the user's inbox after reading"
                    " newsletters or completed threads."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "The ID of the message to archive",
                        }
                    },
                    "required": ["message_id"],
                },
            },
            self.archive_email,
        )

        registry.register(
            {
                "name": "google_mark_email_read",
                "description": "Mark an email as read to clear the notification.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "The ID of the message to mark as read",
                        }
                    },
                    "required": ["message_id"],
                },
            },
            self.mark_email_read,
        )

        registry.register(
            {
                "name": "google_list_gmail_labels",
                "description": (
                    "List all Gmail labels (folders). Use this to find the exact Label ID"
                    " before categorizing an email."
                ),
                "input_schema": {"type": "object", "properties": {}},
            },
            self.list_labels,
        )

        registry.register(
            {
                "name": "google_create_gmail_label",
                "description": (
                    "Create a new Gmail label (folder) to help organize the user's inbox"
                    " (e.g. 'Newsletters', 'Finance')."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "label_name": {
                            "type": "string",
                            "description": "The name of the new label/folder",
                        }
                    },
                    "required": ["label_name"],
                },
            },
            self.create_label,
        )

        registry.register(
            {
                "name": "google_categorize_email",
                "description": (
                    "Apply a specific label to an email to categorize it. You must fetch the"
                    " label_id first using google_list_gmail_labels or google_create_gmail_label."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message_id": {
                            "type": "string",
                            "description": "The ID of the email message",
                        },
                        "label_id": {
                            "type": "string",
                            "description": "The ID of the label to apply",
                        },
                    },
                    "required": ["message_id", "label_id"],
                },
            },
            self.categorize_email,
        )

        registry.register(
            {
                "name": "google_batch_categorize_emails",
                "description": (
                    "Apply a specific label to multiple emails at once. This is highly optimized"
                    " and should ALWAYS be used instead of google_categorize_email when organizing"
                    " multiple emails into the same folder."
                ),
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "message_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "A list of email message IDs to categorize",
                        },
                        "label_id": {
                            "type": "string",
                            "description": "The ID of the label to apply",
                        },
                    },
                    "required": ["message_ids", "label_id"],
                },
            },
            self.batch_categorize_emails,
        )
