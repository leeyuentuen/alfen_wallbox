"""Support for Alfen Eve Single Proline Wallbox."""

from dataclasses import dataclass
from typing import Any, Final

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_platform
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CAT, SERVICE_DISABLE_PHASE_SWITCHING, SERVICE_ENABLE_PHASE_SWITCHING, VALUE
from .coordinator import AlfenConfigEntry
from .entity import AlfenEntity


@dataclass(frozen=True)
class AlfenSwitchDescriptionMixin:
    """Define an entity description mixin for binary sensor entities."""

    api_param: str


@dataclass(frozen=True)
class AlfenSwitchDescription(SwitchEntityDescription, AlfenSwitchDescriptionMixin):
    """Class to describe an Alfen binary sensor entity."""


ALFEN_SWITCH_TYPES: Final[tuple[AlfenSwitchDescription, ...]] = (
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
        name="Solar Charging Boost Socket 1",
        api_param="3280_4",
    ),
    AlfenSwitchDescription(
        key="lb_solar_charging_boost_socket_2",
        name="Solar Charging Boost Socket 2",
        api_param="3280_5",
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
        for description in ALFEN_SWITCH_TYPES
    ]

    async_add_entities(switches)

    platform = entity_platform.current_platform.get()
    if platform is not None:
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
        return self.entity_description.api_param in self.coordinator.device.properties

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""
        if self.entity_description.api_param in self.coordinator.device.properties:
            prop = self.coordinator.device.properties[self.entity_description.api_param]
            return prop[VALUE] in [1, 3]

        return False

    @property
    def extra_state_attributes(self):
        """Return the default attributes of the element."""
        if self.entity_description.api_param in self.coordinator.device.properties:
            return {
                "category": self.coordinator.device.properties[
                    self.entity_description.api_param
                ][CAT],
            }
        return None

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the light on."""
        # Do the turning on.
        on_value = 3 if self.entity_description.api_param == "2064_0" else 1
        await self.coordinator.device.set_value(self.entity_description.api_param, on_value)
        # set_value() triggers immediate coordinator refresh via callback - no need to call async_update()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the entity off."""
        await self.coordinator.device.set_value(self.entity_description.api_param, 0)
        # set_value() triggers immediate coordinator refresh via callback - no need to call async_update()

    async def async_enable_phase_switching(self):
        """Enable phase switching."""
        await self.coordinator.device.set_phase_switching(True)
        await self.async_turn_on()

    async def async_disable_phase_switching(self):
        """Disable phase switching."""
        await self.coordinator.device.set_phase_switching(False)
        await self.async_turn_off()
