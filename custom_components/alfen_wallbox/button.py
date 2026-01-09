"""Button entity for Alfen EV chargers.""" ""

from dataclasses import dataclass
from typing import Final

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CMD,
    COMMAND_CLEAR_TRANSACTIONS,
    COMMAND_REBOOT,
    FORCE_UPDATE,
    LOGIN,
    LOGOUT,
    METHOD_POST,
    PARAM_COMMAND,
)
from .coordinator import AlfenConfigEntry
from .entity import AlfenEntity


@dataclass(frozen=True)
class AlfenButtonDescriptionMixin:
    """Define an entity description mixin for button entities."""

    method: str
    url_action: str
    json_data: dict[str, str] | None


@dataclass(frozen=True)
class AlfenButtonDescription(ButtonEntityDescription, AlfenButtonDescriptionMixin):
    """Class to describe an Alfen button entity."""


ALFEN_BUTTON_TYPES: Final[tuple[AlfenButtonDescription, ...]] = (
    AlfenButtonDescription(
        key="reboot_wallbox",
        name="Reboot Wallbox",
        method=METHOD_POST,
        url_action=CMD,
        json_data={PARAM_COMMAND: COMMAND_REBOOT},
    ),
    AlfenButtonDescription(
        key="auth_logout",
        name="HTTPS API Logout",
        method=METHOD_POST,
        url_action=LOGOUT,
        json_data=None,
    ),
    AlfenButtonDescription(
        key="auth_login",
        name="HTTPS API Login",
        method=METHOD_POST,
        url_action=LOGIN,
        json_data=None,
    ),
    AlfenButtonDescription(
        key="wallbox_force_update",
        name="Force Update",
        method=METHOD_POST,
        url_action="Force Update",
        json_data=None,
    ),
    AlfenButtonDescription(
        key="clear_transaction",
        name="Clear Transaction",
        method=METHOD_POST,
        url_action=CMD,
        json_data={PARAM_COMMAND: COMMAND_CLEAR_TRANSACTIONS},
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlfenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfen switch entities from a config entry."""

    buttons = [AlfenButton(entry, description) for description in ALFEN_BUTTON_TYPES]

    async_add_entities(buttons)


class AlfenButton(AlfenEntity, ButtonEntity):
    """Representation of a Alfen button entity."""

    entity_description: AlfenButtonDescription

    def __init__(
        self,
        entry: AlfenConfigEntry,
        description: AlfenButtonDescription,
    ) -> None:
        """Initialize the Alfen button entity."""
        super().__init__(entry)
        self._attr_name = f"{self.coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{self.coordinator.device.id}-{description.key}"
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        if self.entity_description.url_action == FORCE_UPDATE:
            self.coordinator.device.get_static_properties = True
            await self.coordinator.device.async_update()
            return

        if self.entity_description.url_action == LOGIN:
            await self.coordinator.device.login()
            return

        if self.entity_description.url_action == LOGOUT:
            await self.coordinator.device.logout()
            return

        if self.entity_description.json_data is not None:
            await self.coordinator.device.send_command(self.entity_description.json_data)
            return
