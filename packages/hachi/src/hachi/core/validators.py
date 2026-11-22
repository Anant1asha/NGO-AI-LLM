"""
Pure input validators for integration workflows.

Reusable, dependency-free validators for email, dates, times, recurrence rules,
Sheets ranges, and phone numbers. Each validator returns (ok: bool, value: str)
where value is the normalized input on success or a short error message on failure.

All validators are pure functions with no side effects.
"""

import re
from collections.abc import Iterable
from datetime import date, datetime


def validate_email(addr: str) -> tuple[bool, str]:
    """
    Validate and normalize an email address (RFC-5322-lite).

    Rules:
      - Trim surrounding whitespace
      - Exactly one @ separator
      - Non-empty local part (before @)
      - Domain has at least one dot
      - No whitespace in normalized form
      - No leading/trailing dots in domain

    Args:
        addr: Email address string.

    Returns:
        (True, normalized_email) on success;
        (False, error_message) on failure.

    Examples:
        >>> validate_email("alex@example.com")
        (True, 'alex@example.com')
        >>> validate_email("a.b+tag@sub.example.co.uk")
        (True, 'a.b+tag@sub.example.co.uk')
        >>> validate_email("alex@")
        (False, '...')
    """
    addr = addr.strip()

    if not addr or " " in addr:
        return (False, "Email must not be empty or contain whitespace")

    if addr.count("@") != 1:
        return (False, "Email must contain exactly one @ symbol")

    local, domain = addr.split("@")

    if not local:
        return (False, "Local part (before @) must not be empty")

    if not domain or "." not in domain:
        return (False, "Domain must contain at least one dot")

    if domain.startswith(".") or domain.endswith("."):
        return (False, "Domain must not start or end with a dot")

    normalized = addr.lower()
    return (True, normalized)


def validate_emails(addrs: Iterable[str]) -> tuple[bool, list[str] | str]:
    """
    Validate multiple email addresses.

    Args:
        addrs: Iterable of email address strings.

    Returns:
        (True, [normalized_emails...]) on success;
        (False, error_message_with_offending_address) on first failure.

    Examples:
        >>> validate_emails(["alex@example.com", "bob@test.org"])
        (True, ['alex@example.com', 'bob@test.org'])
        >>> validate_emails(["alex@example.com", "invalid"])
        (False, '...')
    """
    normalized_list = []
    for addr in addrs:
        ok, value = validate_email(addr)
        if not ok:
            return (False, f"Invalid email '{addr}': {value}")
        normalized_list.append(value)

    return (True, normalized_list)


def validate_iso_datetime(s: str) -> tuple[bool, str]:
    """
    Validate and normalize an ISO-8601 date or datetime string.

    Accepts:
      - Date-only: YYYY-MM-DD
      - Datetime: YYYY-MM-DDTHH:MM:SS or YYYY-MM-DDTHH:MM:SS+HH:MM
      - Trailing Z replaced with +00:00 (UTC)

    Args:
        s: ISO-8601 string.

    Returns:
        (True, normalized_iso_string) on success;
        (False, error_message) on failure.

    Examples:
        >>> validate_iso_datetime("2026-06-14")
        (True, '2026-06-14')
        >>> validate_iso_datetime("2026-06-14T10:30:00Z")
        (True, '2026-06-14T10:30:00+00:00')
        >>> validate_iso_datetime("2026-13-01")
        (False, '...')
    """
    s_clean = s.strip()

    # Replace trailing Z with +00:00 for Python's fromisoformat
    if s_clean.endswith("Z"):
        s_clean = s_clean[:-1] + "+00:00"

    try:
        dt = datetime.fromisoformat(s_clean)
        return (True, dt.isoformat())
    except (ValueError, TypeError):
        return (False, f"Invalid ISO-8601 datetime: {s}")


def validate_date(s: str) -> tuple[bool, str]:
    """
    Validate and normalize a date in YYYY-MM-DD format.

    Args:
        s: Date string.

    Returns:
        (True, normalized_date) on success;
        (False, error_message) on failure.

    Examples:
        >>> validate_date("2026-06-14")
        (True, '2026-06-14')
        >>> validate_date("2026-06-32")
        (False, '...')
    """
    s_clean = s.strip()

    try:
        d = date.fromisoformat(s_clean)
        return (True, d.isoformat())
    except (ValueError, TypeError):
        return (False, f"Invalid date (expected YYYY-MM-DD): {s}")


def validate_time_range(start_iso: str, end_iso: str) -> tuple[bool, str]:
    """
    Validate a time range: both must be valid ISO datetimes and start <= end.

    Args:
        start_iso: Start datetime (ISO-8601).
        end_iso: End datetime (ISO-8601).

    Returns:
        (True, "start/end") on success;
        (False, error_message) on failure.

    Examples:
        >>> validate_time_range("2026-06-14T08:00:00", "2026-06-14T17:00:00")
        (True, '2026-06-14T08:00:00/2026-06-14T17:00:00')
        >>> validate_time_range("2026-06-14T17:00:00", "2026-06-14T08:00:00")
        (False, 'End time must be after start time')
    """
    ok_start, start_norm = validate_iso_datetime(start_iso)
    if not ok_start:
        return (False, f"Invalid start datetime: {start_iso}")

    ok_end, end_norm = validate_iso_datetime(end_iso)
    if not ok_end:
        return (False, f"Invalid end datetime: {end_iso}")

    try:
        start_dt = datetime.fromisoformat(start_norm)
        end_dt = datetime.fromisoformat(end_norm)
    except (ValueError, TypeError):
        return (False, "Could not parse normalized datetimes")

    if end_dt < start_dt:
        return (False, "End time must be after start time")

    return (True, f"{start_norm}/{end_norm}")


def validate_rrule(rrule: str) -> tuple[bool, str]:
    """
    Validate an RFC-5545 recurrence rule (lightweight sanity check).

    Rules:
      - Optional RRULE: prefix (removed before validation)
      - Must contain FREQ= with FREQ in {SECONDLY, MINUTELY, HOURLY, DAILY,
        WEEKLY, MONTHLY, YEARLY}
      - Other keys limited to: INTERVAL, COUNT, UNTIL, BYDAY, BYMONTH,
        BYMONTHDAY, BYSETPOS, BYHOUR, BYMINUTE, WKST, BYYEARDAY, BYWEEKNO
      - INTERVAL and COUNT must be positive integers if present

    Args:
        rrule: RFC-5545 RRULE string.

    Returns:
        (True, normalized_rule) on success;
        (False, error_message) on failure.

    Examples:
        >>> validate_rrule("FREQ=DAILY;INTERVAL=2")
        (True, 'FREQ=DAILY;INTERVAL=2')
        >>> validate_rrule("FREQ=NONSENSE")
        (False, '...')
    """
    rule_str = rrule.strip()

    # Remove optional RRULE: prefix
    if rule_str.startswith("RRULE:"):
        rule_str = rule_str[6:]

    if not rule_str:
        return (False, "RRULE must not be empty")

    # Parse key=value pairs
    parts = rule_str.split(";")
    parsed = {}
    for part in parts:
        if "=" not in part:
            return (False, f"Invalid RRULE format: '{part}' (missing =)")
        key, value = part.split("=", 1)
        key = key.strip().upper()
        value = value.strip()
        parsed[key] = value

    # Must have FREQ
    if "FREQ" not in parsed:
        return (False, "RRULE must contain FREQ=")

    freq = parsed["FREQ"]
    valid_freqs = {"SECONDLY", "MINUTELY", "HOURLY", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"}
    if freq not in valid_freqs:
        return (False, f"Invalid FREQ: {freq}")

    # Check allowed keys
    allowed_keys = {
        "FREQ",
        "INTERVAL",
        "COUNT",
        "UNTIL",
        "BYDAY",
        "BYMONTH",
        "BYMONTHDAY",
        "BYSETPOS",
        "BYHOUR",
        "BYMINUTE",
        "WKST",
        "BYYEARDAY",
        "BYWEEKNO",
    }
    for key in parsed:
        if key not in allowed_keys:
            return (False, f"Unknown RRULE key: {key}")

    # Validate INTERVAL and COUNT (must be positive integers)
    if "INTERVAL" in parsed:
        try:
            interval = int(parsed["INTERVAL"])
            if interval <= 0:
                return (False, "INTERVAL must be a positive integer")
        except ValueError:
            return (False, f"Invalid INTERVAL: {parsed['INTERVAL']}")

    if "COUNT" in parsed:
        try:
            count = int(parsed["COUNT"])
            if count <= 0:
                return (False, "COUNT must be a positive integer")
        except ValueError:
            return (False, f"Invalid COUNT: {parsed['COUNT']}")

    return (True, rule_str)


def validate_a1_range(rng: str) -> tuple[bool, str]:
    """
    Validate a Google Sheets A1 notation range.

    Accepts:
      - Simple cell: A1, Z99
      - Range: A1:B2, A:B (column range), 1:5 (row range)
      - Optional sheet prefix: SheetName!A1 or 'Quoted Sheet'!A1

    Args:
        rng: A1 notation string.

    Returns:
        (True, normalized_range) on success;
        (False, error_message) on failure.

    Examples:
        >>> validate_a1_range("A1")
        (True, 'A1')
        >>> validate_a1_range("SheetName!A1:B2")
        (True, 'SheetName!A1:B2')
        >>> validate_a1_range("hello world")
        (False, '...')
    """
    rng_str = rng.strip()

    if not rng_str:
        return (False, "A1 range must not be empty")

    # Pattern: optional sheet name, then cell/range notation
    # Sheet name: unquoted word or quoted string ending with !
    sheet_pattern = r"(?:(?:'[^']*'|[a-zA-Z_]\w*)!)?"
    # Cell: letter(s) + optional digit(s), or just digit(s)
    cell_pattern = r"(?:[a-zA-Z]+\d*|\d+)"
    # Range: cell or cell:cell
    range_pattern = f"(?:{cell_pattern}(?::{cell_pattern})?)"
    full_pattern = f"^{sheet_pattern}{range_pattern}$"

    if not re.match(full_pattern, rng_str):
        return (False, f"Invalid A1 notation: {rng}")

    return (True, rng_str)


def validate_phone(s: str) -> tuple[bool, str]:
    """
    Validate a phone number (E.164-lite format).

    Rules:
      - Strip spaces, dashes, parentheses, dots
      - Allow optional leading +
      - Remaining must be 7–15 digits
      - Reject letters and other characters

    Args:
        s: Phone number string.

    Returns:
        (True, normalized_phone) on success;
        (False, error_message) on failure.

    Examples:
        >>> validate_phone("+1 (555) 123-4567")
        (True, '+15551234567')
        >>> validate_phone("555.123.4567")
        (True, '5551234567')
        >>> validate_phone("abc")
        (False, '...')
    """
    s_clean = s.strip()

    # Remove common formatting characters
    s_clean = s_clean.replace(" ", "").replace("-", "")
    s_clean = s_clean.replace("(", "").replace(")", "").replace(".", "")

    # Check for leading +
    has_plus = s_clean.startswith("+")
    if has_plus:
        s_clean = s_clean[1:]

    # Remaining must be 7-15 digits
    if not s_clean.isdigit():
        return (False, "Phone must contain only digits (after stripping formatting)")

    if len(s_clean) < 7 or len(s_clean) > 15:
        return (False, f"Phone must have 7–15 digits (got {len(s_clean)})")

    normalized = ("+" if has_plus else "") + s_clean
    return (True, normalized)
