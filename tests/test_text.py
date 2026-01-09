"""Test the Alfen Wallbox text entities."""

from unittest.mock import Mock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alfen_wallbox.text import ALFEN_TEXT_TYPES, async_setup_entry


async def test_text_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test text platform setup."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    entities = []

    def add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, add_entities)

    # Should create 5 text entities
    assert len(entities) == 5
    assert entities[0].entity_description.key == "auth_plug_and_charge_id"
    assert entities[1].entity_description.key == "proxy_address_port"


async def test_text_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test text entity initialization."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.text import AlfenText

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Setup property for initial value
    mock_alfen_device.properties = {"2063_0": {"value": "test-id-123", "cat": "test"}}

    text = AlfenText(mock_config_entry, ALFEN_TEXT_TYPES[0])

    assert text.entity_description == ALFEN_TEXT_TYPES[0]
    assert text._attr_name == "Test Wallbox Auth. Plug & Charge ID"
    assert text._attr_unique_id == "alfen_Test Wallbox_auth_plug_and_charge_id"
    assert text._attr_native_value == "test-id-123"


async def test_text_get_current_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test text entity get current value."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.text import AlfenText

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    text = AlfenText(mock_config_entry, ALFEN_TEXT_TYPES[0])

    # With value
    mock_alfen_device.properties = {"2063_0": {"value": "test-value", "cat": "test"}}
    assert text._get_current_value() == "test-value"

    # Without value
    mock_alfen_device.properties = {}
    assert text._get_current_value() is None


async def test_text_async_set_value(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test text entity set value."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.text import AlfenText

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    mock_alfen_device.properties = {"2063_0": {"value": "old-value", "cat": "test"}}

    text = AlfenText(mock_config_entry, ALFEN_TEXT_TYPES[0])

    # Mock the async_write_ha_state method
    text.async_write_ha_state = Mock()

    await text.async_set_value("new-test-value")

    # set_value should be called with new value
    mock_alfen_device.set_value.assert_called_once_with("2063_0", "new-test-value")

    # Internal state should be updated
    assert text._attr_native_value == "new-test-value"

    # async_write_ha_state should be called
    text.async_write_ha_state.assert_called_once()


async def test_text_extra_state_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test text entity extra state attributes."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.text import AlfenText

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    text = AlfenText(mock_config_entry, ALFEN_TEXT_TYPES[0])

    # With property
    mock_alfen_device.properties = {"2063_0": {"value": "test", "cat": "generic"}}
    attrs = text.extra_state_attributes
    assert attrs is not None
    assert "category" in attrs
    assert attrs["category"] == "generic"

    # Without property
    mock_alfen_device.properties = {}
    attrs = text.extra_state_attributes
    assert attrs is None


async def test_text_password_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test text entity with password mode."""
    mock_config_entry.add_to_hass(hass)

    from homeassistant.components.text import TextMode

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.text import AlfenText

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the password text description
    password_desc = next(desc for desc in ALFEN_TEXT_TYPES if desc.mode == TextMode.PASSWORD)

    text = AlfenText(mock_config_entry, password_desc)

    # Mode should be PASSWORD
    assert text._attr_mode == TextMode.PASSWORD
    assert text.entity_description.key == "proxy_password"
