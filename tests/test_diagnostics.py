"""Test the Alfen Wallbox diagnostics."""

from unittest.mock import MagicMock

from custom_components.alfen_wallbox.diagnostics import async_get_config_entry_diagnostics


async def test_diagnostics(hass):
    """Test diagnostics data."""
    # Mock device info
    mock_device_info = MagicMock()
    mock_device_info.identity = "ALFENEVE001"
    mock_device_info.firmware_version = "5.9.0"
    mock_device_info.model = "NG910"

    # Mock device
    mock_device = MagicMock()
    mock_device.id = "alfen_test"
    mock_device.name = "Test Wallbox"
    mock_device.info = mock_device_info
    mock_device.keep_logout = False
    mock_device.max_allowed_phases = 3
    mock_device.category_options = ["generic", "states"]
    mock_device.properties = {"2129_0": {"id": "2129_0", "value": "16"}}
    mock_device.get_number_of_sockets = MagicMock(return_value=1)
    mock_device.get_licenses = MagicMock(return_value=["Active_Load_Balancing"])

    # Mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.device = mock_device

    # Mock config entry
    mock_entry = MagicMock()
    mock_entry.runtime_data = mock_coordinator

    # Get diagnostics
    diagnostics = await async_get_config_entry_diagnostics(hass, mock_entry)

    # Verify diagnostics data
    assert diagnostics["id"] == "alfen_test"
    assert diagnostics["name"] == "Test Wallbox"
    assert diagnostics["keep_logout"] is False
    assert diagnostics["max_allowed_phases"] == 3
    assert diagnostics["number_socket"] == 1
    assert "Active_Load_Balancing" in diagnostics["licenses"]
    assert diagnostics["category_options"] == ["generic", "states"]
    assert "2129_0" in diagnostics["properties"]
    assert "info" in diagnostics
