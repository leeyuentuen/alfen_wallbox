
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
from .const import CMD, METHOD_POST, PARAM_COMMAND, COMMAND_REBOOT

from . import DOMAIN as ALFEN_DOMAIN


_LOGGER = logging.getLogger(__name__)


@dataclass
class AlfenButtonDescriptionMixin:
    """Define an entity description mixin for button entities."""

    method: str
    url_action: str
    json_action: str


@dataclass
class AlfenButtonDescription(ButtonEntityDescription, AlfenButtonDescriptionMixin):
    """Class to describe an Alfen button entity."""


ALFEN_BUTTON_TYPES: Final[tuple[AlfenButtonDescription, ...]] = (
    AlfenButtonDescription(
        key="reboot_wallbox",
        name="Reboot Wallbox",
        method=METHOD_POST,
        url_action=CMD,
        json_action={PARAM_COMMAND: COMMAND_REBOOT},
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
        await self.hass.async_add_executor_job(self._device.login())
        await self.hass.async_add_executor_job(
            self._device.request(),
            self.entity_description.method,
            POST_HEADER_JSON,
            self.entity_description.url_action,
            self.entity_description.json_action)
        await self.hass.async_add_executor_job(self._device.logout())
