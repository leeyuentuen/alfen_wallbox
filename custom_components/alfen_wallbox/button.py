
from dataclasses import dataclass
import logging
from typing import Final

from homeassistant import core
from .alfen import POST_HEADER_JSON, AlfenDevice
from .entity import AlfenEntity

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from .const import CMD, DISPLAY_NAME_VALUE, LOGIN, LOGOUT, METHOD_POST, PARAM_COMMAND, COMMAND_REBOOT, PARAM_DISPLAY_NAME, PARAM_PASSWORD, PARAM_USERNAME

from . import DOMAIN as ALFEN_DOMAIN


_LOGGER = logging.getLogger(__name__)


@dataclass
class AlfenButtonDescriptionMixin:
    """Define an entity description mixin for button entities."""

    method: str
    url_action: str
    json_data: str


@dataclass
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
        json_data=None
    ),
    AlfenButtonDescription(
        key="auth_login",
        name="HTTPS API Login",
        method=METHOD_POST,
        url_action=LOGIN,
        json_data=None
    ),
    AlfenButtonDescription(
        key="wallbox_force_update",
        name="Force Update",
        method=METHOD_POST,
        url_action='Force Update',
        json_data=None
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfen switch entities from a config entry."""
    device = hass.data[ALFEN_DOMAIN][entry.entry_id]
    buttons = [AlfenButton(device, description)
               for description in ALFEN_BUTTON_TYPES]

    async_add_entities(buttons)


class AlfenButton(AlfenEntity, ButtonEntity):
    """Representation of a Alfen button entity."""

    entity_description: AlfenButtonDescription

    def __init__(
        self,
        device: AlfenDevice,
        description: AlfenButtonDescription,
    ) -> None:
        """Initialize the Alfen button entity."""
        super().__init__(device)
        self._device = device
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{device.id}-{description.key}"
        self.entity_description = description

    async def async_press(self) -> None:
        """Press the button."""
        if self.entity_description.url_action == "Force Update":
            await self._device.async_update()
            return
        elif self.entity_description.url_action == LOGIN:
            resp = await self._device.async_request(
                method=self.entity_description.method,
                cmd=self.entity_description.url_action,
                json_data={PARAM_USERNAME: self._device.username,
                           PARAM_PASSWORD: self._device.password,
                           PARAM_DISPLAY_NAME: DISPLAY_NAME_VALUE}
            )
            if resp and resp.status_code == 200:
                self._device.keepLogout = False
                return
            resp.raise_for_status()
        else:
            resp = await self._device.async_request(
                method=self.entity_description.method,
                cmd=self.entity_description.url_action,
                json_data=self.entity_description.json_data
            )
            if resp and resp.status_code == 200:
                self._device.keepLogout = True
                return
            resp.raise_for_status()
