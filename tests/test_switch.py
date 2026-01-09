"""Test the Alfen Wallbox switch entities."""


from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alfen_wallbox.switch import ALFEN_SWITCH_TYPES, async_setup_entry


async def test_switch_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test switch platform setup."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    entities = []

    def add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, add_entities)

    # Should create 10 switch entities
    assert len(entities) == 10
    assert entities[0].entity_description.key == "lb_enable_phase_switching"
    assert entities[1].entity_description.key == "dp_light_auto_dim"


async def test_switch_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test switch entity initialization."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.switch import AlfenSwitchSensor

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    switch = AlfenSwitchSensor(mock_config_entry, ALFEN_SWITCH_TYPES[0])

    assert switch.entity_description == ALFEN_SWITCH_TYPES[0]
    assert switch._attr_name == "Test Wallbox Load Balancing Enable Phase Switching"
    assert switch._attr_unique_id == "alfen_Test Wallbox_lb_enable_phase_switching"


async def test_switch_availability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test switch availability based on device properties."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.switch import AlfenSwitchSensor

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    switch = AlfenSwitchSensor(mock_config_entry, ALFEN_SWITCH_TYPES[0])

    # Property exists, should be available
    mock_alfen_device.properties = {"2185_0": {"value": 1, "cat": "test"}}
    assert switch.available is True

    # Property doesn't exist, should not be available
    mock_alfen_device.properties = {}
    assert switch.available is False


async def test_switch_is_on(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test switch is_on property."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.switch import AlfenSwitchSensor

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    switch = AlfenSwitchSensor(mock_config_entry, ALFEN_SWITCH_TYPES[0])

    # Value 1 = on
    mock_alfen_device.properties = {"2185_0": {"value": 1, "cat": "test"}}
    assert switch.is_on is True

    # Value 3 = on
    mock_alfen_device.properties = {"2185_0": {"value": 3, "cat": "test"}}
    assert switch.is_on is True

    # Value 0 = off
    mock_alfen_device.properties = {"2185_0": {"value": 0, "cat": "test"}}
    assert switch.is_on is False

    # Property doesn't exist = off
    mock_alfen_device.properties = {}
    assert switch.is_on is False


async def test_switch_extra_state_attributes(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test switch extra state attributes."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.switch import AlfenSwitchSensor

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    switch = AlfenSwitchSensor(mock_config_entry, ALFEN_SWITCH_TYPES[0])

    # With property
    mock_alfen_device.properties = {"2185_0": {"value": 1, "cat": "generic"}}
    attrs = switch.extra_state_attributes
    assert attrs is not None
    assert "category" in attrs
    assert attrs["category"] == "generic"

    # Without property
    mock_alfen_device.properties = {}
    attrs = switch.extra_state_attributes
    assert attrs is None


async def test_switch_turn_on_normal(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test normal switch turn on."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.switch import AlfenSwitchSensor

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    switch = AlfenSwitchSensor(mock_config_entry, ALFEN_SWITCH_TYPES[0])

    await switch.async_turn_on()

    # set_value should be called with 1 (normal switch)
    mock_alfen_device.set_value.assert_called_once_with("2185_0", 1)
    # async_update is NOT called - set_value() triggers coordinator refresh via callback


async def test_switch_turn_on_active_load_balancing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test active load balancing switch turn on (special case)."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.switch import AlfenSwitchSensor

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Create active load balancing switch (api_param "2064_0")
    active_lb_desc = next(
        desc for desc in ALFEN_SWITCH_TYPES if desc.api_param == "2064_0"
    )
    switch = AlfenSwitchSensor(mock_config_entry, active_lb_desc)

    await switch.async_turn_on()

    # set_value should be called with 3 (special case for active load balancing)
    mock_alfen_device.set_value.assert_called_once_with("2064_0", 3)
    # async_update is NOT called - set_value() triggers coordinator refresh via callback


async def test_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test switch turn off."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.switch import AlfenSwitchSensor

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    switch = AlfenSwitchSensor(mock_config_entry, ALFEN_SWITCH_TYPES[0])

    await switch.async_turn_off()

    # set_value should be called with 0
    mock_alfen_device.set_value.assert_called_once_with("2185_0", 0)
    # async_update is NOT called - set_value() triggers coordinator refresh via callback


async def test_switch_enable_phase_switching(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test enable phase switching service."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.switch import AlfenSwitchSensor

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    switch = AlfenSwitchSensor(mock_config_entry, ALFEN_SWITCH_TYPES[0])

    await switch.async_enable_phase_switching()

    # set_phase_switching should be called with True
    mock_alfen_device.set_phase_switching.assert_called_once_with(True)
    # set_value should be called (from async_turn_on)
    mock_alfen_device.set_value.assert_called_once()
    # async_update is NOT called - set_value() triggers coordinator refresh via callback


async def test_switch_disable_phase_switching(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test disable phase switching service."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator
    from custom_components.alfen_wallbox.switch import AlfenSwitchSensor

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    switch = AlfenSwitchSensor(mock_config_entry, ALFEN_SWITCH_TYPES[0])

    await switch.async_disable_phase_switching()

    # set_phase_switching should be called with False
    mock_alfen_device.set_phase_switching.assert_called_once_with(False)
    # set_value should be called (from async_turn_off)
    mock_alfen_device.set_value.assert_called_once()
    # async_update is NOT called - set_value() triggers coordinator refresh via callback
