import logging

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.helpers import entity_platform

from .const import ID, SERVICE_DISABLE_PHASE_SWITCHING, SERVICE_ENABLE_PHASE_SWITCHING, VALUE
from .alfen import AlfenDevice
from .entity import AlfenEntity

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as ALFEN_DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class AlfenSwitchDescriptionMixin:
    """Define an entity description mixin for binary sensor entities."""

    api_param: str


@dataclass
class AlfenSwitchDescription(SwitchEntityDescription, AlfenSwitchDescriptionMixin):
    """Class to describe an Alfen binary sensor entity."""


ALFEN_BINARY_SENSOR_TYPES: Final[tuple[AlfenSwitchDescription, ...]] = (
    AlfenSwitchDescription(
        key="lb_enable_phase_switching",
        name="Load Balancing Enable Phase Switching",
        api_param="2185_0",
    ),
    AlfenSwitchDescription(
        key="dp_light_auto_dim",
        name="Display Light Auto Dim",
        api_param="2061_1",
    ),
    AlfenSwitchDescription(
        key="lb_solar_charging_boost",
        name="Solar Charging Boost",
        api_param="3280_4",
    ),
    AlfenSwitchDescription(
        key="auth_white_list",
        name="Auth. Whitelist",
        api_param="213B_0",
    ),
    AlfenSwitchDescription(
        key="auth_local_list",
        name="Auth. Local List",
        api_param="213D_0",
    ),
    AlfenSwitchDescription(
        key="auth_restart_after_power_outage",
        name="Auth. Restart after Power Outage",
        api_param="215E_0",
    ),
    AlfenSwitchDescription(
        key="auth_remote_transaction_request",
        name="Auth. Remote Transaction requests",
        api_param="209B_0",
    ),
    AlfenSwitchDescription(
        key="proxy_enabled",
        name="Proxy Enabled",
        api_param="2117_0",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfen switch entities from a config entry."""
    device = hass.data[ALFEN_DOMAIN][entry.entry_id]
    switches = [AlfenSwitchSensor(device, description)
                for description in ALFEN_BINARY_SENSOR_TYPES]

    async_add_entities(switches)

    platform = entity_platform.current_platform.get()

    platform.async_register_entity_service(
        SERVICE_ENABLE_PHASE_SWITCHING,
        {},
        "async_enable_phase_switching",
    )

    platform.async_register_entity_service(
        SERVICE_DISABLE_PHASE_SWITCHING,
        {},
        "async_disable_phase_switching",
    )


class AlfenSwitchSensor(AlfenEntity, SwitchEntity):
    """Define an Alfen binary sensor."""
    entity_description: AlfenSwitchDescription

    def __init__(self,
                 device: AlfenDevice,
                 description: AlfenSwitchDescription
                 ) -> None:
        """Initialize."""
        super().__init__(device)
        self._device = device
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{self._device.id}_{description.key}"
        self.entity_description = description

    @property
    def available(self) -> bool:
        for prop in self._device.properties:
            if prop[ID] == self.entity_description.api_param:
                return True
        return False

    @property
    def is_on(self) -> bool:
        for prop in self._device.properties:
            if prop[ID] == self.entity_description.api_param:
                return prop[VALUE] == 1

        return False

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Do the turning on.
        await self._device.set_value(self.entity_description.api_param, 1)
        await self._device.async_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self._device.set_value(self.entity_description.api_param, 0)
        await self._device.async_update()

    async def async_enable_phase_switching(self):
        """Enable phase switching."""
        await self._device.set_phase_switching(True)
        await self.async_turn_on()

    async def async_disable_phase_switching(self):
        """Disable phase switching."""
        await self._device.set_phase_switching(False)
        await self.async_turn_off()
