"""Test security features of the Alfen Wallbox integration."""

import time
from unittest.mock import MagicMock

import pytest

from custom_components.alfen_wallbox.alfen import (
    API_PARAM_PATTERN,
    LOGIN_RATE_LIMIT_MAX_ATTEMPTS,
    LOGIN_RATE_LIMIT_WINDOW,
    AlfenDevice,
)
from custom_components.alfen_wallbox.const import ID, PROPERTIES, TOTAL, VALUE
from custom_components.alfen_wallbox.diagnostics import (
    _hash_sensitive_value,
    _is_sensitive_property,
    _sanitize_latest_tag,
    _sanitize_properties,
)


@pytest.fixture(name="mock_session")
def mock_session_fixture():
    """Mock aiohttp ClientSession."""
    session = MagicMock()
    session.verify = False
    session.closed = False
    return session


@pytest.fixture(name="mock_ssl_context")
def mock_ssl_context_fixture():
    """Mock SSL context."""
    return MagicMock()


@pytest.fixture(name="alfen_device")
def alfen_device_fixture(mock_session, mock_ssl_context):
    """Create an AlfenDevice instance."""
    device = AlfenDevice(
        session=mock_session,
        host="192.168.1.100",
        name="Test Wallbox",
        username="admin",
        password="secret",
        category_options=["generic", "states"],
        ssl=mock_ssl_context,
    )
    device.category_fetch_delay = 0
    return device


# =============================================================================
# Login Rate Limiting Tests
# =============================================================================


class TestLoginRateLimiting:
    """Tests for login rate limiting functionality."""

    def test_rate_limit_constants(self):
        """Test rate limit constants are defined correctly."""
        assert LOGIN_RATE_LIMIT_WINDOW == 60
        assert LOGIN_RATE_LIMIT_MAX_ATTEMPTS == 5

    def test_check_login_rate_limit_allows_first_attempt(self, alfen_device):
        """Test that first login attempt is allowed."""
        assert alfen_device._check_login_rate_limit() is True

    def test_check_login_rate_limit_allows_under_limit(self, alfen_device):
        """Test that attempts under the limit are allowed."""
        # Record 4 attempts (under limit of 5)
        for _ in range(4):
            alfen_device._record_login_attempt()

        assert alfen_device._check_login_rate_limit() is True

    def test_check_login_rate_limit_blocks_at_limit(self, alfen_device):
        """Test that attempts at the limit are blocked."""
        # Record 5 attempts (at limit)
        for _ in range(5):
            alfen_device._record_login_attempt()

        assert alfen_device._check_login_rate_limit() is False

    def test_check_login_rate_limit_blocks_over_limit(self, alfen_device):
        """Test that attempts over the limit are blocked."""
        # Record 10 attempts (over limit)
        for _ in range(10):
            alfen_device._record_login_attempt()

        assert alfen_device._check_login_rate_limit() is False

    def test_rate_limit_clears_old_attempts(self, alfen_device):
        """Test that old attempts outside the window are cleared."""
        # Record attempts with old timestamps
        old_time = time.time() - LOGIN_RATE_LIMIT_WINDOW - 10
        alfen_device._login_attempts = [old_time] * 10

        # Should allow new attempts since old ones are outside window
        assert alfen_device._check_login_rate_limit() is True
        # Old attempts should be cleared
        assert len(alfen_device._login_attempts) == 0

    def test_record_login_attempt_adds_timestamp(self, alfen_device):
        """Test that recording an attempt adds a timestamp."""
        initial_count = len(alfen_device._login_attempts)
        alfen_device._record_login_attempt()

        assert len(alfen_device._login_attempts) == initial_count + 1
        # Timestamp should be recent
        assert time.time() - alfen_device._login_attempts[-1] < 1


# =============================================================================
# API Parameter Validation Tests
# =============================================================================


class TestApiParameterValidation:
    """Tests for API parameter validation."""

    def test_api_param_pattern_valid_simple(self):
        """Test valid simple parameter IDs."""
        assert API_PARAM_PATTERN.match("2129_0") is not None
        assert API_PARAM_PATTERN.match("205E_0") is not None
        assert API_PARAM_PATTERN.match("21A2_0") is not None

    def test_api_param_pattern_valid_alphanumeric(self):
        """Test valid alphanumeric parameter IDs."""
        assert API_PARAM_PATTERN.match("abc123") is not None
        assert API_PARAM_PATTERN.match("ABC123") is not None
        assert API_PARAM_PATTERN.match("a1b2c3") is not None

    def test_api_param_pattern_valid_with_hyphen(self):
        """Test valid parameter IDs with hyphens."""
        assert API_PARAM_PATTERN.match("param-id") is not None
        assert API_PARAM_PATTERN.match("a-b-c") is not None

    def test_api_param_pattern_invalid_special_chars(self):
        """Test invalid parameter IDs with special characters."""
        assert API_PARAM_PATTERN.match("param;injection") is None
        assert API_PARAM_PATTERN.match("param&other") is None
        assert API_PARAM_PATTERN.match("param=value") is None
        assert API_PARAM_PATTERN.match("param<script>") is None

    def test_api_param_pattern_invalid_spaces(self):
        """Test invalid parameter IDs with spaces."""
        assert API_PARAM_PATTERN.match("param id") is None
        assert API_PARAM_PATTERN.match(" param") is None
        assert API_PARAM_PATTERN.match("param ") is None

    def test_validate_api_param_valid(self, alfen_device):
        """Test validation of valid API parameters."""
        assert alfen_device._validate_api_param("2129_0") is True
        assert alfen_device._validate_api_param("205E_0") is True
        assert alfen_device._validate_api_param("abc-123") is True

    def test_validate_api_param_invalid(self, alfen_device):
        """Test validation of invalid API parameters."""
        assert alfen_device._validate_api_param("") is False
        assert alfen_device._validate_api_param(None) is False
        assert alfen_device._validate_api_param("param;drop") is False
        assert alfen_device._validate_api_param("../../../etc/passwd") is False

    def test_validate_api_param_non_string(self, alfen_device):
        """Test validation rejects non-string inputs."""
        assert alfen_device._validate_api_param(123) is False
        assert alfen_device._validate_api_param(["list"]) is False
        assert alfen_device._validate_api_param({"dict": "value"}) is False


# =============================================================================
# JSON Response Validation Tests
# =============================================================================


class TestJsonResponseValidation:
    """Tests for JSON response validation."""

    def test_validate_properties_response_valid(self, alfen_device):
        """Test validation of valid response structure."""
        valid_response = {
            PROPERTIES: [
                {ID: "2129_0", VALUE: "16"},
                {ID: "205E_0", VALUE: "1"},
            ],
            TOTAL: 2,
        }
        assert alfen_device._validate_properties_response(valid_response) is True

    def test_validate_properties_response_empty_properties(self, alfen_device):
        """Test validation with empty properties list."""
        response = {PROPERTIES: [], TOTAL: 0}
        assert alfen_device._validate_properties_response(response) is True

    def test_validate_properties_response_missing_properties(self, alfen_device):
        """Test validation fails when properties key is missing."""
        response = {TOTAL: 2}
        assert alfen_device._validate_properties_response(response) is False

    def test_validate_properties_response_missing_total(self, alfen_device):
        """Test validation fails when total key is missing."""
        response = {PROPERTIES: [{ID: "2129_0"}]}
        assert alfen_device._validate_properties_response(response) is False

    def test_validate_properties_response_not_dict(self, alfen_device):
        """Test validation fails for non-dict response."""
        assert alfen_device._validate_properties_response("string") is False
        assert alfen_device._validate_properties_response([]) is False
        assert alfen_device._validate_properties_response(None) is False

    def test_validate_properties_response_properties_not_list(self, alfen_device):
        """Test validation fails when properties is not a list."""
        response = {PROPERTIES: "not a list", TOTAL: 1}
        assert alfen_device._validate_properties_response(response) is False

    def test_validate_properties_response_total_not_int(self, alfen_device):
        """Test validation fails when total is not an integer."""
        response = {PROPERTIES: [], TOTAL: "10"}
        assert alfen_device._validate_properties_response(response) is False

    def test_validate_properties_response_property_missing_id(self, alfen_device):
        """Test validation fails when property is missing id."""
        response = {PROPERTIES: [{VALUE: "16"}], TOTAL: 1}
        assert alfen_device._validate_properties_response(response) is False

    def test_validate_properties_response_property_not_dict(self, alfen_device):
        """Test validation fails when property is not a dict."""
        response = {PROPERTIES: ["not a dict"], TOTAL: 1}
        assert alfen_device._validate_properties_response(response) is False


# =============================================================================
# Exception Sanitization Tests
# =============================================================================


class TestExceptionSanitization:
    """Tests for exception message sanitization."""

    def test_sanitize_exception_basic(self, alfen_device):
        """Test basic exception sanitization."""
        exc = ValueError("Simple error message")
        result = alfen_device._sanitize_exception(exc)

        assert "ValueError" in result
        assert "Simple error message" in result

    def test_sanitize_exception_removes_unix_paths(self, alfen_device):
        """Test that Unix file paths are redacted."""
        exc = FileNotFoundError("File not found: /home/user/secret/file.txt")
        result = alfen_device._sanitize_exception(exc)

        assert "/home/user/secret/file.txt" not in result
        assert "<path>" in result

    def test_sanitize_exception_removes_windows_paths(self, alfen_device):
        """Test that Windows file paths are redacted."""
        exc = FileNotFoundError("File not found: C:\\Users\\admin\\secret.txt")
        result = alfen_device._sanitize_exception(exc)

        assert "C:\\Users\\admin\\secret.txt" not in result
        assert "<path>" in result

    def test_sanitize_exception_removes_ip_addresses(self, alfen_device):
        """Test that IP addresses are redacted."""
        exc = ConnectionError("Cannot connect to 192.168.1.100:8080")
        result = alfen_device._sanitize_exception(exc)

        assert "192.168.1.100" not in result
        assert "<ip>" in result

    def test_sanitize_exception_removes_long_tokens(self, alfen_device):
        """Test that long alphanumeric strings (potential tokens) are redacted."""
        token = "a" * 40  # 40 character string
        exc = ValueError(f"Invalid token: {token}")
        result = alfen_device._sanitize_exception(exc)

        assert token not in result
        assert "<redacted>" in result

    def test_sanitize_exception_preserves_short_strings(self, alfen_device):
        """Test that short strings are preserved."""
        exc = ValueError("Error code: ABC123")
        result = alfen_device._sanitize_exception(exc)

        assert "ABC123" in result

    def test_sanitize_exception_truncates_long_messages(self, alfen_device):
        """Test that long messages are truncated."""
        # Use a message that won't be replaced by other sanitization patterns
        long_message = "Error occurred: " + "error details here " * 50
        exc = ValueError(long_message)
        result = alfen_device._sanitize_exception(exc)

        # Message should be truncated (type + ": " + 200 chars + "...")
        assert len(result) <= 220
        assert "..." in result

    def test_sanitize_exception_type_included(self, alfen_device):
        """Test that exception type is included."""
        exc = TimeoutError("Connection timed out")
        result = alfen_device._sanitize_exception(exc)

        assert "TimeoutError" in result


# =============================================================================
# Diagnostics Sanitization Tests
# =============================================================================


class TestDiagnosticsSanitization:
    """Tests for diagnostics data sanitization."""

    def test_hash_sensitive_value_none(self):
        """Test hashing of None value."""
        assert _hash_sensitive_value(None) == "<none>"

    def test_hash_sensitive_value_empty_string(self):
        """Test hashing of empty string."""
        assert _hash_sensitive_value("") == ""

    def test_hash_sensitive_value_no_tag(self):
        """Test hashing of 'No Tag' value."""
        assert _hash_sensitive_value("No Tag") == "No Tag"

    def test_hash_sensitive_value_creates_hash(self):
        """Test that actual values are hashed."""
        result = _hash_sensitive_value("ABC123456")

        assert result.startswith("<redacted:")
        assert result.endswith(">")
        # Hash should be 8 characters
        hash_part = result[len("<redacted:"):-1]
        assert len(hash_part) == 8

    def test_hash_sensitive_value_consistent(self):
        """Test that same value produces same hash."""
        value = "RFID12345"
        result1 = _hash_sensitive_value(value)
        result2 = _hash_sensitive_value(value)

        assert result1 == result2

    def test_hash_sensitive_value_different_for_different_values(self):
        """Test that different values produce different hashes."""
        result1 = _hash_sensitive_value("RFID12345")
        result2 = _hash_sensitive_value("RFID67890")

        assert result1 != result2

    def test_is_sensitive_property_rfid(self):
        """Test detection of RFID-related properties."""
        assert _is_sensitive_property("rfid_tag") is True
        assert _is_sensitive_property("RFID_Card") is True
        assert _is_sensitive_property("user_rfid") is True

    def test_is_sensitive_property_tag(self):
        """Test detection of tag-related properties."""
        assert _is_sensitive_property("tag_id") is True
        assert _is_sensitive_property("latest_tag") is True

    def test_is_sensitive_property_password(self):
        """Test detection of password-related properties."""
        assert _is_sensitive_property("password") is True
        assert _is_sensitive_property("user_password") is True

    def test_is_sensitive_property_card(self):
        """Test detection of card-related properties."""
        assert _is_sensitive_property("card_number") is True
        assert _is_sensitive_property("user_card") is True

    def test_is_sensitive_property_specific_ids(self):
        """Test detection of specific sensitive property IDs."""
        assert _is_sensitive_property("2063_0") is True  # RFID tag ID

    def test_is_sensitive_property_non_sensitive(self):
        """Test that non-sensitive properties are not flagged."""
        assert _is_sensitive_property("2129_0") is False
        assert _is_sensitive_property("current_limit") is False
        assert _is_sensitive_property("power_kwh") is False
        assert _is_sensitive_property("phase_switching") is False

    def test_sanitize_properties_redacts_sensitive(self):
        """Test that sensitive properties are redacted."""
        properties = {
            "rfid_tag": {"id": "rfid_tag", "value": "ABC123", "cat": "generic"},
            "2129_0": {"id": "2129_0", "value": "16", "cat": "generic"},
        }

        result = _sanitize_properties(properties)

        assert result["rfid_tag"]["value"] == "<redacted>"
        assert result["2129_0"]["value"] == "16"

    def test_sanitize_properties_preserves_structure(self):
        """Test that property structure is preserved."""
        properties = {
            "2129_0": {"id": "2129_0", "value": "16", "cat": "generic"},
        }

        result = _sanitize_properties(properties)

        assert result["2129_0"]["id"] == "2129_0"
        assert result["2129_0"]["value"] == "16"
        assert result["2129_0"]["cat"] == "generic"

    def test_sanitize_latest_tag_none(self):
        """Test sanitization of None latest_tag."""
        assert _sanitize_latest_tag(None) is None

    def test_sanitize_latest_tag_hashes_tag_values(self):
        """Test that tag values are hashed."""
        latest_tag = {
            ("socket 1", "start", "tag"): "RFID123456",
            ("socket 1", "start", "date"): "2024-01-15 10:30:00",
            ("socket 1", "start", "kWh"): "10.5",
        }

        result = _sanitize_latest_tag(latest_tag)

        # Tag should be hashed
        tag_key = str(("socket 1", "start", "tag"))
        assert result[tag_key].startswith("<redacted:")

        # Date and kWh should be preserved
        date_key = str(("socket 1", "start", "date"))
        kwh_key = str(("socket 1", "start", "kWh"))
        assert result[date_key] == "2024-01-15 10:30:00"
        assert result[kwh_key] == "10.5"

    def test_sanitize_latest_tag_preserves_no_tag(self):
        """Test that 'No Tag' values are preserved."""
        latest_tag = {
            ("socket 1", "start", "tag"): "No Tag",
        }

        result = _sanitize_latest_tag(latest_tag)

        tag_key = str(("socket 1", "start", "tag"))
        assert result[tag_key] == "No Tag"


# =============================================================================
# RFID Tag Logging Sanitization Tests
# =============================================================================


class TestRfidTagLoggingSanitization:
    """Tests for RFID tag logging sanitization."""

    def test_sanitize_tag_for_logging_none(self, alfen_device):
        """Test sanitization when latest_tag is None."""
        alfen_device.latest_tag = None
        result = alfen_device._sanitize_tag_for_logging()

        assert result == {}

    def test_sanitize_tag_for_logging_empty(self, alfen_device):
        """Test sanitization when latest_tag is empty."""
        alfen_device.latest_tag = {}
        result = alfen_device._sanitize_tag_for_logging()

        assert result == {}

    def test_sanitize_tag_for_logging_hashes_tag(self, alfen_device):
        """Test that tag values are hashed."""
        alfen_device.latest_tag = {
            ("socket 1", "start", "tag"): "RFID123456",
        }

        result = alfen_device._sanitize_tag_for_logging()

        key = str(("socket 1", "start", "tag"))
        assert result[key].startswith("<tag:")
        assert result[key].endswith(">")
        assert "RFID123456" not in result[key]

    def test_sanitize_tag_for_logging_preserves_non_tag(self, alfen_device):
        """Test that non-tag values are preserved."""
        alfen_device.latest_tag = {
            ("socket 1", "start", "date"): "2024-01-15 10:30:00",
            ("socket 1", "start", "kWh"): "10.5",
            ("socket 1", "start", "taglog"): 12345,
        }

        result = alfen_device._sanitize_tag_for_logging()

        assert result[str(("socket 1", "start", "date"))] == "2024-01-15 10:30:00"
        assert result[str(("socket 1", "start", "kWh"))] == "10.5"
        assert result[str(("socket 1", "start", "taglog"))] == 12345

    def test_sanitize_tag_for_logging_preserves_no_tag(self, alfen_device):
        """Test that 'No Tag' values are preserved."""
        alfen_device.latest_tag = {
            ("socket 1", "start", "tag"): "No Tag",
        }

        result = alfen_device._sanitize_tag_for_logging()

        key = str(("socket 1", "start", "tag"))
        assert result[key] == "No Tag"

    def test_sanitize_tag_for_logging_preserves_none_value(self, alfen_device):
        """Test that None tag values are preserved."""
        alfen_device.latest_tag = {
            ("socket 1", "start", "tag"): None,
        }

        result = alfen_device._sanitize_tag_for_logging()

        key = str(("socket 1", "start", "tag"))
        assert result[key] is None

    def test_sanitize_tag_for_logging_consistent_hash(self, alfen_device):
        """Test that same tag produces same hash."""
        alfen_device.latest_tag = {
            ("socket 1", "start", "tag"): "RFID123456",
        }

        result1 = alfen_device._sanitize_tag_for_logging()
        result2 = alfen_device._sanitize_tag_for_logging()

        key = str(("socket 1", "start", "tag"))
        assert result1[key] == result2[key]
