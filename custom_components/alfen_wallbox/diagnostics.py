"""Diagnostics support for Alfen."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from homeassistant.core import HomeAssistant

from .coordinator import AlfenConfigEntry

# Properties that may contain sensitive information (RFID tags, user data)
SENSITIVE_PROPERTY_PATTERNS = [
    r".*rfid.*",
    r".*tag.*",
    r".*card.*",
    r".*token.*",
    r".*user.*",
    r".*password.*",
    r".*secret.*",
    r".*key.*",
]

# Property IDs known to contain sensitive data
SENSITIVE_PROPERTY_IDS: set[str] = {
    "2063_0",  # RFID tag ID
}


def _hash_sensitive_value(value: Any) -> str:
    """Hash a sensitive value for diagnostics.

    Args:
        value: The value to hash

    Returns:
        A hashed representation safe for sharing
    """
    if value is None:
        return "<none>"
    value_str = str(value)
    if not value_str or value_str in ("None", "No Tag", ""):
        return value_str
    # Create a short hash for identification without exposing actual value
    hash_val = hashlib.sha256(value_str.encode()).hexdigest()[:8]
    return f"<redacted:{hash_val}>"


def _is_sensitive_property(prop_id: str) -> bool:
    """Check if a property ID might contain sensitive data.

    Args:
        prop_id: The property ID to check

    Returns:
        True if the property might be sensitive
    """
    if prop_id in SENSITIVE_PROPERTY_IDS:
        return True

    prop_lower = prop_id.lower()
    return any(re.match(pattern, prop_lower) for pattern in SENSITIVE_PROPERTY_PATTERNS)


def _sanitize_properties(properties: dict[str, Any]) -> dict[str, Any]:
    """Sanitize properties dict by redacting sensitive values.

    Args:
        properties: The properties dict to sanitize

    Returns:
        A sanitized copy of the properties
    """
    sanitized = {}
    for prop_id, prop_data in properties.items():
        if _is_sensitive_property(prop_id):
            # Redact the entire property
            sanitized[prop_id] = {"id": prop_id, "value": "<redacted>", "cat": prop_data.get("cat", "unknown")}
        else:
            # Copy the property as-is
            sanitized[prop_id] = prop_data
    return sanitized


def _sanitize_latest_tag(latest_tag: dict | None) -> dict[str, Any] | None:
    """Sanitize latest_tag data by hashing RFID tags.

    Args:
        latest_tag: The latest_tag dict to sanitize

    Returns:
        A sanitized copy of the latest_tag data
    """
    if latest_tag is None:
        return None

    sanitized = {}
    for key, value in latest_tag.items():
        # Key is a tuple like ("socket 1", "start", "tag")
        if isinstance(key, tuple) and len(key) >= 3 and key[2] == "tag":
            # Hash the RFID tag value
            sanitized[str(key)] = _hash_sensitive_value(value)
        else:
            # Keep other values (dates, kWh) as-is
            sanitized[str(key)] = value
    return sanitized


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: AlfenConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry.

    Note: Sensitive data (RFID tags, etc.) is redacted or hashed for privacy.
    """
    device = entry.runtime_data.device
    return {
        "id": device.id,
        "name": device.name,
        "info": vars(device.info) if device.info else None,
        "keep_logout": device.keep_logout,
        "max_allowed_phases": device.max_allowed_phases,
        "number_socket": device.get_number_of_sockets(),
        "licenses": device.get_licenses(),
        "category_options": device.category_options,
        # Sanitize properties to redact sensitive data
        "properties": _sanitize_properties(device.properties),
        # Sanitize RFID tag data
        "latest_tag": _sanitize_latest_tag(device.latest_tag),
    }
