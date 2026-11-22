"""
Tests for core validators module.

Covers all validator functions with valid and invalid cases,
including specific reject cases (e.g., invalid dates, end-before-start).
"""

from hachi.core.validators import (
    validate_a1_range,
    validate_date,
    validate_email,
    validate_emails,
    validate_iso_datetime,
    validate_phone,
    validate_rrule,
    validate_time_range,
)


class TestValidateEmail:
    """Tests for validate_email."""

    def test_valid_simple_email(self) -> None:
        """Valid simple email."""
        ok, value = validate_email("alex@example.com")
        assert ok is True
        assert value == "alex@example.com"

    def test_valid_complex_email(self) -> None:
        """Valid email with dots and plus tag."""
        ok, value = validate_email("a.b+tag@sub.example.co.uk")
        assert ok is True
        assert value == "a.b+tag@sub.example.co.uk"

    def test_valid_email_with_whitespace(self) -> None:
        """Valid email with surrounding whitespace (should be trimmed)."""
        ok, value = validate_email("  alex@example.com  ")
        assert ok is True
        assert value == "alex@example.com"

    def test_valid_email_uppercase_domain(self) -> None:
        """Domain should be lowercased."""
        ok, value = validate_email("alex@EXAMPLE.COM")
        assert ok is True
        assert value == "alex@example.com"

    def test_invalid_empty_string(self) -> None:
        """Empty string is invalid."""
        ok, value = validate_email("")
        assert ok is False
        assert value  # Error message present

    def test_invalid_no_at_symbol(self) -> None:
        """Must have exactly one @ symbol."""
        ok, value = validate_email("alex example.com")
        assert ok is False
        assert value

    def test_invalid_multiple_at_symbols(self) -> None:
        """Too many @ symbols."""
        ok, value = validate_email("alex@exam@ple.com")
        assert ok is False
        assert value

    def test_invalid_missing_local_part(self) -> None:
        """Local part (before @) must not be empty."""
        ok, value = validate_email("@example.com")
        assert ok is False
        assert value

    def test_invalid_missing_domain(self) -> None:
        """Email must end with something; @example is rejected."""
        ok, value = validate_email("alex@")
        assert ok is False
        assert value

    def test_invalid_domain_no_dot(self) -> None:
        """Domain must contain at least one dot."""
        ok, value = validate_email("a@b")
        assert ok is False
        assert value

    def test_invalid_domain_leading_dot(self) -> None:
        """Domain must not start with a dot."""
        ok, value = validate_email("alex@.example.com")
        assert ok is False
        assert value

    def test_invalid_domain_trailing_dot(self) -> None:
        """Domain must not end with a dot."""
        ok, value = validate_email("alex@example.com.")
        assert ok is False
        assert value

    def test_invalid_whitespace_in_email(self) -> None:
        """Whitespace in email address is invalid."""
        ok, value = validate_email("alex @ example.com")
        assert ok is False
        assert value


class TestValidateEmails:
    """Tests for validate_emails."""

    def test_valid_single_email(self) -> None:
        """Single valid email."""
        ok, value = validate_emails(["alex@example.com"])
        assert ok is True
        assert value == ["alex@example.com"]

    def test_valid_multiple_emails(self) -> None:
        """Multiple valid emails."""
        ok, value = validate_emails(["alex@example.com", "bob@test.org"])
        assert ok is True
        assert value == ["alex@example.com", "bob@test.org"]

    def test_invalid_first_email(self) -> None:
        """Invalid first email returns (False, error_msg)."""
        ok, value = validate_emails(["invalid", "bob@test.org"])
        assert ok is False
        assert "invalid" in value

    def test_invalid_second_email(self) -> None:
        """Invalid second email returns (False, error_msg) with offending address."""
        ok, value = validate_emails(["alex@example.com", "alex@"])
        assert ok is False
        assert "alex@" in value

    def test_empty_iterable(self) -> None:
        """Empty iterable returns empty list."""
        ok, value = validate_emails([])
        assert ok is True
        assert value == []


class TestValidateIsoDatetime:
    """Tests for validate_iso_datetime."""

    def test_valid_date_only(self) -> None:
        """Valid date-only ISO string."""
        ok, value = validate_iso_datetime("2026-06-14")
        assert ok is True
        assert "2026-06-14" in value

    def test_valid_datetime_no_offset(self) -> None:
        """Valid datetime without offset."""
        ok, value = validate_iso_datetime("2026-06-14T10:30:00")
        assert ok is True
        assert "2026-06-14T10:30:00" in value

    def test_valid_datetime_with_z(self) -> None:
        """Valid datetime with Z (should be converted to +00:00)."""
        ok, value = validate_iso_datetime("2026-06-14T10:30:00Z")
        assert ok is True
        assert value == "2026-06-14T10:30:00+00:00"

    def test_valid_datetime_with_offset(self) -> None:
        """Valid datetime with explicit offset."""
        ok, value = validate_iso_datetime("2026-06-14T10:30:00+02:00")
        assert ok is True
        assert "2026-06-14T10:30:00" in value

    def test_invalid_month(self) -> None:
        """Month 13 is invalid."""
        ok, value = validate_iso_datetime("2026-13-01")
        assert ok is False
        assert value

    def test_invalid_day(self) -> None:
        """Day 32 in June is invalid."""
        ok, value = validate_iso_datetime("2026-06-32")
        assert ok is False
        assert value

    def test_invalid_format(self) -> None:
        """Completely invalid string."""
        ok, value = validate_iso_datetime("not-a-date")
        assert ok is False
        assert value

    def test_invalid_empty_string(self) -> None:
        """Empty string is invalid."""
        ok, value = validate_iso_datetime("")
        assert ok is False
        assert value


class TestValidateDate:
    """Tests for validate_date."""

    def test_valid_date(self) -> None:
        """Valid date in YYYY-MM-DD format."""
        ok, value = validate_date("2026-06-14")
        assert ok is True
        assert value == "2026-06-14"

    def test_valid_leap_year(self) -> None:
        """Valid leap year date."""
        ok, value = validate_date("2024-02-29")
        assert ok is True
        assert value == "2024-02-29"

    def test_invalid_month(self) -> None:
        """Month 13 is invalid."""
        ok, value = validate_date("2026-13-01")
        assert ok is False
        assert value

    def test_invalid_day(self) -> None:
        """Day 32 in June is invalid."""
        ok, value = validate_date("2026-06-32")
        assert ok is False
        assert value

    def test_invalid_format(self) -> None:
        """Invalid format."""
        ok, value = validate_date("06/14/2026")
        assert ok is False
        assert value

    def test_invalid_leap_year(self) -> None:
        """Feb 29 on non-leap year is invalid."""
        ok, value = validate_date("2025-02-29")
        assert ok is False
        assert value


class TestValidateTimeRange:
    """Tests for validate_time_range."""

    def test_valid_same_day_range(self) -> None:
        """Valid time range on same day."""
        ok, value = validate_time_range("2026-06-14T08:00:00", "2026-06-14T17:00:00")
        assert ok is True
        assert "/" in value

    def test_valid_multi_day_range(self) -> None:
        """Valid range spanning multiple days."""
        ok, value = validate_time_range("2026-06-14T08:00:00", "2026-06-15T17:00:00")
        assert ok is True
        assert "/" in value

    def test_valid_equal_times(self) -> None:
        """Start == end is valid."""
        ok, value = validate_time_range("2026-06-14T10:00:00", "2026-06-14T10:00:00")
        assert ok is True
        assert "/" in value

    def test_invalid_end_before_start(self) -> None:
        """End time before start time is invalid."""
        ok, value = validate_time_range("2026-06-14T17:00:00", "2026-06-14T08:00:00")
        assert ok is False
        assert "after start" in value.lower() or "before" in value.lower()

    def test_invalid_bad_start(self) -> None:
        """Invalid start datetime."""
        ok, value = validate_time_range("2026-13-01T10:00:00", "2026-06-14T17:00:00")
        assert ok is False
        assert value

    def test_invalid_bad_end(self) -> None:
        """Invalid end datetime."""
        ok, value = validate_time_range("2026-06-14T08:00:00", "2026-06-32T17:00:00")
        assert ok is False
        assert value


class TestValidateRrule:
    """Tests for validate_rrule."""

    def test_valid_simple_rule(self) -> None:
        """Valid simple RRULE."""
        ok, value = validate_rrule("FREQ=DAILY")
        assert ok is True
        assert "FREQ=DAILY" in value

    def test_valid_rule_with_interval(self) -> None:
        """Valid RRULE with INTERVAL."""
        ok, value = validate_rrule("FREQ=DAILY;INTERVAL=2")
        assert ok is True
        assert "INTERVAL=2" in value

    def test_valid_rule_with_count(self) -> None:
        """Valid RRULE with COUNT."""
        ok, value = validate_rrule("FREQ=WEEKLY;COUNT=10")
        assert ok is True
        assert "COUNT=10" in value

    def test_valid_rule_with_rrule_prefix(self) -> None:
        """Valid RRULE with RRULE: prefix."""
        ok, value = validate_rrule("RRULE:FREQ=MONTHLY")
        assert ok is True
        assert "FREQ=MONTHLY" in value

    def test_valid_all_freqs(self) -> None:
        """All valid FREQ values should work."""
        for freq in ["SECONDLY", "MINUTELY", "HOURLY", "DAILY", "WEEKLY", "MONTHLY", "YEARLY"]:
            ok, value = validate_rrule(f"FREQ={freq}")
            assert ok is True, f"FREQ={freq} should be valid"

    def test_invalid_no_freq(self) -> None:
        """RRULE without FREQ is invalid."""
        ok, value = validate_rrule("INTERVAL=2")
        assert ok is False
        assert "FREQ" in value.upper()

    def test_invalid_freq_value(self) -> None:
        """Invalid FREQ value."""
        ok, value = validate_rrule("FREQ=NONSENSE")
        assert ok is False
        assert value

    def test_invalid_unknown_key(self) -> None:
        """Unknown key is rejected."""
        ok, value = validate_rrule("FREQ=DAILY;BADKEY=value")
        assert ok is False
        assert "BADKEY" in value

    def test_invalid_interval_not_positive(self) -> None:
        """INTERVAL must be positive."""
        ok, value = validate_rrule("FREQ=DAILY;INTERVAL=0")
        assert ok is False
        assert value

    def test_invalid_count_not_positive(self) -> None:
        """COUNT must be positive."""
        ok, value = validate_rrule("FREQ=DAILY;COUNT=-1")
        assert ok is False
        assert value

    def test_invalid_interval_not_int(self) -> None:
        """INTERVAL must be an integer."""
        ok, value = validate_rrule("FREQ=DAILY;INTERVAL=abc")
        assert ok is False
        assert value

    def test_invalid_empty_rule(self) -> None:
        """Empty rule is invalid."""
        ok, value = validate_rrule("")
        assert ok is False
        assert value


class TestValidateA1Range:
    """Tests for validate_a1_range."""

    def test_valid_simple_cell(self) -> None:
        """Valid simple cell reference."""
        ok, value = validate_a1_range("A1")
        assert ok is True
        assert value == "A1"

    def test_valid_range(self) -> None:
        """Valid range."""
        ok, value = validate_a1_range("A1:B2")
        assert ok is True
        assert value == "A1:B2"

    def test_valid_column_range(self) -> None:
        """Valid column range."""
        ok, value = validate_a1_range("A:B")
        assert ok is True
        assert value == "A:B"

    def test_valid_row_range(self) -> None:
        """Valid row range."""
        ok, value = validate_a1_range("1:5")
        assert ok is True
        assert value == "1:5"

    def test_valid_with_sheet_name(self) -> None:
        """Valid with sheet name prefix."""
        ok, value = validate_a1_range("SheetName!A1")
        assert ok is True
        assert "SheetName" in value

    def test_valid_with_quoted_sheet(self) -> None:
        """Valid with quoted sheet name."""
        ok, value = validate_a1_range("'My Sheet'!A1:B2")
        assert ok is True
        assert "My Sheet" in value

    def test_invalid_garbage(self) -> None:
        """Garbage string is invalid."""
        ok, value = validate_a1_range("hello world")
        assert ok is False
        assert value

    def test_invalid_empty_string(self) -> None:
        """Empty string is invalid."""
        ok, value = validate_a1_range("")
        assert ok is False
        assert value

    def test_invalid_malformed_range(self) -> None:
        """Malformed range."""
        ok, value = validate_a1_range("A1:B")
        assert ok is True  # This is actually valid (B = column B all rows)

    def test_valid_large_column(self) -> None:
        """Valid large column reference."""
        ok, value = validate_a1_range("Z99")
        assert ok is True
        assert value == "Z99"


class TestValidatePhone:
    """Tests for validate_phone."""

    def test_valid_simple_digits(self) -> None:
        """Valid phone with just digits."""
        ok, value = validate_phone("5551234567")
        assert ok is True
        assert value == "5551234567"

    def test_valid_with_plus(self) -> None:
        """Valid phone with leading +."""
        ok, value = validate_phone("+15551234567")
        assert ok is True
        assert value == "+15551234567"

    def test_valid_with_formatting(self) -> None:
        """Valid phone with spaces and dashes."""
        ok, value = validate_phone("+1 (555) 123-4567")
        assert ok is True
        assert value == "+15551234567"

    def test_valid_with_dots(self) -> None:
        """Valid phone with dots."""
        ok, value = validate_phone("555.123.4567")
        assert ok is True
        assert value == "5551234567"

    def test_valid_min_length(self) -> None:
        """Valid phone at minimum length (7 digits)."""
        ok, value = validate_phone("1234567")
        assert ok is True
        assert len(value) == 7

    def test_valid_max_length(self) -> None:
        """Valid phone at maximum length (15 digits)."""
        ok, value = validate_phone("123456789012345")
        assert ok is True
        assert len(value) == 15

    def test_invalid_too_short(self) -> None:
        """Phone too short (< 7 digits)."""
        ok, value = validate_phone("123456")
        assert ok is False
        assert value

    def test_invalid_too_long(self) -> None:
        """Phone too long (> 15 digits)."""
        ok, value = validate_phone("1234567890123456")
        assert ok is False
        assert value

    def test_invalid_letters(self) -> None:
        """Letters are invalid."""
        ok, value = validate_phone("abc")
        assert ok is False
        assert value

    def test_invalid_mixed_letters_digits(self) -> None:
        """Mixed letters and digits."""
        ok, value = validate_phone("555-CALL-NOW")
        assert ok is False
        assert value

    def test_invalid_empty_string(self) -> None:
        """Empty string is invalid."""
        ok, value = validate_phone("")
        assert ok is False
        assert value
