"""Support for Alfen Eve Single Proline Wallbox."""

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CAT,
    ID,
    SERVICE_DISABLE_PHASE_SWITCHING,
    SERVICE_ENABLE_PHASE_SWITCHING,
    VALUE,
)
from .coordinator import AlfenConfigEntry
from .entity import AlfenEntity


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
    AlfenSwitchDescription(
        key="active_load_balancing",
        name="Active Load Balancing",
        api_param="2064_0",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlfenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfen switch entities from a config entry."""

    switches = [
        AlfenSwitchSensor(entry, description)
        for description in ALFEN_BINARY_SENSOR_TYPES
    ]

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

    def __init__(
        self, entry: AlfenConfigEntry, description: AlfenSwitchDescription
    ) -> None:
        """Initialize."""
        super().__init__(entry)

        self._attr_name = f"{self.coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{self.coordinator.device.id}_{description.key}"
        self.entity_description = description

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                return True
        return False

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                return prop[VALUE] == 1 or 3

        return False

    @property
    def extra_state_attributes(self):
        """Return the default attributes of the element."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                return {"category": prop[CAT]}
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Do the turning on.
        if self.entity_description.api_param == "2064_0":
            on_value = 3
        else:
            on_value = 1

        await self.coordinator.device.set_value(
            self.entity_description.api_param, on_value
        )
        await self.coordinator.device.async_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.device.set_value(self.entity_description.api_param, 0)
        await self.coordinator.device.async_update()

    async def async_enable_phase_switching(self):
        """Enable phase switching."""
        await self.coordinator.device.set_phase_switching(True)
        await self.async_turn_on()

    async def async_disable_phase_switching(self):
        """Disable phase switching."""
        await self.coordinator.device.set_phase_switching(False)
        await self.async_turn_off()
