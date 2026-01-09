"""Support for Alfen Eve Proline binary sensors."""

from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    CAT,
    LICENSE_HIGH_POWER,
    LICENSE_LOAD_BALANCING_ACTIVE,
    LICENSE_LOAD_BALANCING_STATIC,
    LICENSE_MOBILE,
    LICENSE_NONE,
    LICENSE_PAYMENT_GIROE,
    LICENSE_PERSONALIZED_DISPLAY,
    LICENSE_RFID,
    LICENSE_SCN,
    VALUE,
)
from .coordinator import AlfenConfigEntry
from .entity import AlfenEntity

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class AlfenBinaryDescriptionMixin:
    """Define an entity description mixin for binary sensor entities."""

    api_param: str | None


@dataclass(frozen=True)
class AlfenBinaryDescription(
    BinarySensorEntityDescription, AlfenBinaryDescriptionMixin
):
    """Class to describe an Alfen binary sensor entity."""


ALFEN_BINARY_SENSOR_TYPES: Final[tuple[AlfenBinaryDescription, ...]] = (
    AlfenBinaryDescription(
        key="system_date_light_savings",
        name="System Daylight Savings",
        device_class=None,
        api_param="205B_0",
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AlfenBinaryDescription(
        key="license_scn",
        name="License Smart Charging Network",
        device_class=None,
        api_param=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AlfenBinaryDescription(
        key="license_active_loadbalancing",
        name="License Active Loadbalancing",
        device_class=None,
        api_param=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AlfenBinaryDescription(
        key="license_static_loadbalancing",
        name="License Static Loadbalancing",
        device_class=None,
        api_param=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AlfenBinaryDescription(
        key="license_high_power_sockets",
        name="License 32A Output per Socket",
        device_class=None,
        api_param=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AlfenBinaryDescription(
        key="license_rfid_reader",
        name="License RFID Reader",
        device_class=None,
        api_param=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AlfenBinaryDescription(
        key="license_personalized_display",
        name="License Personalized Display",
        device_class=None,
        api_param=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AlfenBinaryDescription(
        key="license_mobile_3g_4g",
        name="License Mobile 3G & 4G",
        device_class=None,
        api_param=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AlfenBinaryDescription(
        key="license_giro_e",
        name="License Giro-e Payment",
        device_class=None,
        api_param=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    AlfenBinaryDescription(
        key="https_api_login_status",
        name="HTTPS API Login Status",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        api_param=None,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlfenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfen binary sensor entities from a config entry."""

    binaries = [
        AlfenBinarySensor(entry, description)
        for description in ALFEN_BINARY_SENSOR_TYPES
    ]

    async_add_entities(binaries)


class AlfenBinarySensor(AlfenEntity, BinarySensorEntity):
    """Define an Alfen binary sensor."""

    entity_description: AlfenBinaryDescription

    def __init__(
        self, entry: AlfenConfigEntry, description: AlfenBinaryDescription
    ) -> None:
        """Initialize."""
        super().__init__(entry)
        self._attr_name = f"{self.coordinator.device.name} {description.name}"
        self._attr_unique_id = f"{self.coordinator.device.id}_{description.key}"
        self.entity_description = description

        licenses = self.coordinator.device.get_licenses()

        # custom code for license
        if self.entity_description.api_param is None:
            # check if license is available
            if "21A2_0" in self.coordinator.device.properties and self.coordinator.device.properties["21A2_0"][VALUE] == LICENSE_NONE:
                return
            if self.entity_description.key == "license_scn":
                self._attr_is_on = LICENSE_SCN in licenses
            if self.entity_description.key == "license_active_loadbalancing":
                self._attr_is_on = (
                    LICENSE_SCN in licenses or LICENSE_LOAD_BALANCING_ACTIVE in licenses
                )
            if self.entity_description.key == "license_static_loadbalancing":
                self._attr_is_on = (
                    LICENSE_SCN in licenses
                    or LICENSE_LOAD_BALANCING_STATIC in licenses
                    or LICENSE_LOAD_BALANCING_STATIC in licenses
                )
            if self.entity_description.key == "license_high_power_sockets":
                self._attr_is_on = LICENSE_HIGH_POWER in licenses
            if self.entity_description.key == "license_rfid_reader":
                self._attr_is_on = LICENSE_RFID in licenses
            if self.entity_description.key == "license_personalized_display":
                self._attr_is_on = LICENSE_PERSONALIZED_DISPLAY in licenses
            if self.entity_description.key == "license_mobile_3g_4g":
                self._attr_is_on = LICENSE_MOBILE in licenses
            if self.entity_description.key == "license_giro_e":
                self._attr_is_on = LICENSE_PAYMENT_GIROE in licenses

    #            if self.entity_description.key == "license_qrcode":
    #                self._attr_is_on = LICENSE_PAYMENT_QRCODE in licenses
    #            if self.entity_description.key == "license_expose_smartmeterdata":
    #                self._attr_is_on = LICENSE_EXPOSE_SMARTMETERDATA in licenses

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        if self.entity_description.api_param is not None:
            return (
                self.entity_description.api_param in self.coordinator.device.properties
            )

        return True

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""

        if self.entity_description.api_param is not None:
            if self.entity_description.api_param in self.coordinator.device.properties:
                prop = self.coordinator.device.properties[
                    self.entity_description.api_param
                ]
                return prop[VALUE] == 1
            return False

        if self.entity_description.key == "https_api_login_status":
            return self.coordinator.device.logged_in

        return self._attr_is_on if self._attr_is_on is not None else False

    @property
    def extra_state_attributes(self) -> dict | None:
        """Return the default attributes of the element."""
        if self.entity_description.api_param in self.coordinator.device.properties:
            return {
                "category": self.coordinator.device.properties[
                    self.entity_description.api_param
                ][CAT],
            }

        if self.entity_description.key == "https_api_login_status":
            return {"last_updated": self.coordinator.device.last_updated}

        return None
