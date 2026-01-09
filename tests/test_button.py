"""Test the Alfen Wallbox button entities."""


from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.alfen_wallbox.button import ALFEN_BUTTON_TYPES, async_setup_entry


async def test_button_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test button platform setup."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    entities = []

    def add_entities(new_entities):
        entities.extend(new_entities)

    await async_setup_entry(hass, mock_config_entry, add_entities)

    # Should create 5 button entities
    assert len(entities) == 5
    assert entities[0].entity_description.key == "reboot_wallbox"
    assert entities[1].entity_description.key == "auth_logout"
    assert entities[2].entity_description.key == "auth_login"
    assert entities[3].entity_description.key == "wallbox_force_update"
    assert entities[4].entity_description.key == "clear_transaction"


async def test_button_initialization(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test button entity initialization."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.button import AlfenButton
    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    button = AlfenButton(mock_config_entry, ALFEN_BUTTON_TYPES[0])

    assert button.entity_description == ALFEN_BUTTON_TYPES[0]
    assert button._attr_name == "Test Wallbox Reboot Wallbox"
    assert button._attr_unique_id == "alfen_Test Wallbox-reboot_wallbox"


async def test_force_update_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test force update button press."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.button import AlfenButton
    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the force update button description
    force_update_desc = next(
        desc for desc in ALFEN_BUTTON_TYPES if desc.key == "wallbox_force_update"
    )

    button = AlfenButton(mock_config_entry, force_update_desc)

    # Initially get_static_properties should be False
    mock_alfen_device.get_static_properties = False

    await button.async_press()

    # After pressing, get_static_properties should be True
    assert mock_alfen_device.get_static_properties is True
    # async_update should have been called
    mock_alfen_device.async_update.assert_called_once()


async def test_login_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test login button press."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.button import AlfenButton
    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the login button description
    login_desc = next(desc for desc in ALFEN_BUTTON_TYPES if desc.key == "auth_login")

    button = AlfenButton(mock_config_entry, login_desc)

    await button.async_press()

    # login should have been called
    mock_alfen_device.login.assert_called_once()


async def test_logout_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test logout button press."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.button import AlfenButton
    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the logout button description
    logout_desc = next(desc for desc in ALFEN_BUTTON_TYPES if desc.key == "auth_logout")

    button = AlfenButton(mock_config_entry, logout_desc)

    await button.async_press()

    # logout should have been called
    mock_alfen_device.logout.assert_called_once()


async def test_reboot_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test reboot button press."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.button import AlfenButton
    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the reboot button description
    reboot_desc = next(
        desc for desc in ALFEN_BUTTON_TYPES if desc.key == "reboot_wallbox"
    )

    button = AlfenButton(mock_config_entry, reboot_desc)

    await button.async_press()

    # send_command should have been called with reboot command
    mock_alfen_device.send_command.assert_called_once()
    call_args = mock_alfen_device.send_command.call_args[0][0]
    assert "command" in call_args
    assert call_args["command"] == "reboot"


async def test_clear_transaction_button_press(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_alfen_device,
) -> None:
    """Test clear transaction button press."""
    mock_config_entry.add_to_hass(hass)

    from custom_components.alfen_wallbox.button import AlfenButton
    from custom_components.alfen_wallbox.coordinator import AlfenCoordinator

    coordinator = AlfenCoordinator(hass, mock_config_entry)
    coordinator.device = mock_alfen_device
    mock_config_entry.runtime_data = coordinator

    # Find the clear transaction button description
    clear_desc = next(
        desc for desc in ALFEN_BUTTON_TYPES if desc.key == "clear_transaction"
    )

    button = AlfenButton(mock_config_entry, clear_desc)

    await button.async_press()

    # send_command should have been called with clear transaction command
    mock_alfen_device.send_command.assert_called_once()
    call_args = mock_alfen_device.send_command.call_args[0][0]
    assert "command" in call_args
    assert call_args["command"] == "txerase"
