"""Test the Alfen Wallbox select entities."""

from unittest.mock import Mock

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alfen_wallbox.select import ALFEN_SELECT_TYPES, async_setup_entry


async def test_select_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test select platform setup with single socket."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Single socket device
    mock_alfen_device.get_number_of_sockets = Mock(return_value=1)

    entities = []

    def add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, add_entities)

    # Should create 17 select entities (only single socket types)
    assert len(entities) == 17
    assert entities[0].entity_description.key == "lb_solar_charging_mode"


async def test_select_setup_dual_socket(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test select platform setup with dual socket."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Dual socket device
    mock_alfen_device.get_number_of_sockets = Mock(return_value=2)

    entities = []

    def add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, add_entities)

    # Should create 18 select entities (17 single + 1 dual)
    assert len(entities) == 18


async def test_select_async_select_option(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test selecting an option."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.select import AlfenSelect

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    select = AlfenSelect(mock_config_entry, ALFEN_SELECT_TYPES[0])
    select.async_write_ha_state = Mock()

    # Select "Green" option (value 2)
    await select.async_select_option("Green")

    # set_value should be called with the mapped value
    mock_alfen_device.set_value.assert_called_once_with("3280_1", 2)
    select.async_write_ha_state.assert_called_once()


async def test_select_extra_state_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test select extra state attributes."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.select import AlfenSelect

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    select = AlfenSelect(mock_config_entry, ALFEN_SELECT_TYPES[0])

    # With property
    mock_alfen_device.properties = {"3280_1": {"value": 1, "cat": "generic"}}
    attrs = select.extra_state_attributes
    assert attrs is not None
    assert "category" in attrs
    assert attrs["category"] == "generic"

    # Without property
    mock_alfen_device.properties = {}
    attrs = select.extra_state_attributes
    assert attrs is None


async def test_select_get_current_option_max_allowed_phase(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test get current option for max_allowed_phase (special case)."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.select import AlfenSelect

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the max_allowed_phase select
    max_phase_desc = next(
        desc for desc in ALFEN_SELECT_TYPES if desc.key == "ps_installation_max_allowed_phase"
    )

    select = AlfenSelect(mock_config_entry, max_phase_desc)

    # Set property value
    mock_alfen_device.properties = {"2189_0": {"value": 3, "cat": "test"}}

    # Get current option should set device.max_allowed_phases
    result = select._get_current_option()

    assert result == 3
    assert mock_alfen_device.max_allowed_phases == 3


async def test_select_async_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test select async_update."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.select import AlfenSelect

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    select = AlfenSelect(mock_config_entry, ALFEN_SELECT_TYPES[0])

    # Set property
    mock_alfen_device.properties = {"3280_1": {"value": 2, "cat": "test"}}

    # Should be None initially
    select._attr_current_option = None

    await select.async_update()

    # Should be updated now
    assert select._attr_current_option == 2


async def test_select_async_set_current_phase(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test set current phase service."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.select import AlfenSelect

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the phase connection select
    phase_desc = next(
        desc for desc in ALFEN_SELECT_TYPES if desc.key == "lb_phase_connection"
    )

    select = AlfenSelect(mock_config_entry, phase_desc)
    select.async_write_ha_state = Mock()

    await select.async_set_current_phase("L1")

    # set_current_phase should be called
    mock_alfen_device.set_current_phase.assert_called_once_with("L1")
    # set_value should be called (from async_select_option)
    mock_alfen_device.set_value.assert_called_once()


async def test_select_async_enable_rfid_auth_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test enable RFID auth mode service."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.select import AlfenSelect

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the auth mode select
    auth_desc = next(desc for desc in ALFEN_SELECT_TYPES if desc.key == "auth_mode")

    select = AlfenSelect(mock_config_entry, auth_desc)
    select.async_write_ha_state = Mock()

    await select.async_enable_rfid_auth_mode()

    # set_rfid_auth_mode should be called with True
    mock_alfen_device.set_rfid_auth_mode.assert_called_once_with(True)
    # set_value should be called with 2 (RFID mode)
    mock_alfen_device.set_value.assert_called_once_with("2126_0", 2)
    select.async_write_ha_state.assert_called_once()


async def test_select_async_disable_rfid_auth_mode(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test disable RFID auth mode service."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.select import AlfenSelect

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the auth mode select
    auth_desc = next(desc for desc in ALFEN_SELECT_TYPES if desc.key == "auth_mode")

    select = AlfenSelect(mock_config_entry, auth_desc)
    select.async_write_ha_state = Mock()

    await select.async_disable_rfid_auth_mode()

    # set_rfid_auth_mode should be called with False
    mock_alfen_device.set_rfid_auth_mode.assert_called_once_with(False)
    # set_value should be called with 0 (Plug and Charge mode)
    mock_alfen_device.set_value.assert_called_once_with("2126_0", 0)
    select.async_write_ha_state.assert_called_once()
