"""Support for Alfen Eve Proline binary sensors."""
from dataclasses import dataclass
import logging
from typing import Final

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import DOMAIN as ALFEN_DOMAIN
from .alfen import AlfenDevice
from .const import (
    ID,
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
from .entity import AlfenEntity

_LOGGER = logging.getLogger(__name__)


@dataclass
class AlfenBinaryDescriptionMixin:
    """Define an entity description mixin for binary sensor entities."""

    api_param: str


@dataclass
class AlfenBinaryDescription(BinarySensorEntityDescription, AlfenBinaryDescriptionMixin):
    """Class to describe an Alfen binary sensor entity."""


ALFEN_BINARY_SENSOR_TYPES: Final[tuple[AlfenBinaryDescription, ...]] = (
    AlfenBinaryDescription(
        key="system_date_light_savings",
        name="System Daylight Savings",
        device_class=None,
        api_param="205B_0",
    ),
    AlfenBinaryDescription(
        key="license_scn",
        name="License Smart Charging Network",
        device_class=None,
        api_param=None,
    ),
    AlfenBinaryDescription(
        key="license_active_loadbalancing",
        name="License Active Loadbalancing",
        device_class=None,
        api_param=None,
    ),
    AlfenBinaryDescription(
        key="license_static_loadbalancing",
        name="License Static Loadbalancing",
        device_class=None,
        api_param=None,
    ),
    AlfenBinaryDescription(
        key="license_high_power_sockets",
        name="License 32A Output per Socket",
        device_class=None,
        api_param=None,
    ),
    AlfenBinaryDescription(
        key="license_rfid_reader",
        name="License RFID Reader",
        device_class=None,
        api_param=None,
    ),
    AlfenBinaryDescription(
        key="license_personalized_display",
        name="License Personalized Display",
        device_class=None,
        api_param=None,
    ),
    AlfenBinaryDescription(
        key="license_mobile_3G_4G",
        name="License Mobile 3G & 4G",
        device_class=None,
        api_param=None,
    ),
    AlfenBinaryDescription(
        key="license_giro_e",
        name="License Giro-e Payment",
        device_class=None,
        api_param=None,
    ),

)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Alfen binary sensor entities from a config entry."""
    device = hass.data[ALFEN_DOMAIN][entry.entry_id]
    binaries = [AlfenBinarySensor(device, description)
                for description in ALFEN_BINARY_SENSOR_TYPES]

    async_add_entities(binaries)


class AlfenBinarySensor(AlfenEntity, BinarySensorEntity):
    """Define an Alfen binary sensor."""

    entity_description: AlfenBinaryDescription

    def __init__(self,
                 device: AlfenDevice,
                 description: AlfenBinaryDescription
                 ) -> None:
        """Initialize."""
        super().__init__(device)
        self._device = device
        self._attr_name = f"{device.name} {description.name}"
        self._attr_unique_id = f"{self._device.id}_{description.key}"
        self.entity_description = description

        # custom code for license
        if self.entity_description.api_param is None:
            # check if license is available
            if '21A2_0' in self._device.properties:
                if self._device.properties['21A2_0'][VALUE] == LICENSE_NONE:
                    return
            _LOGGER.debug(self._device.licenses)
            if self.entity_description.key == "license_scn":
                self._attr_is_on = LICENSE_SCN in self._device.licenses
            if self.entity_description.key == "license_active_loadbalancing":
                self._attr_is_on = LICENSE_SCN in self._device.licenses or LICENSE_LOAD_BALANCING_ACTIVE in self._device.licenses
            if self.entity_description.key == "license_static_loadbalancing":
                self._attr_is_on = LICENSE_SCN in self._device.licenses or LICENSE_LOAD_BALANCING_STATIC in self._device.licenses or LICENSE_LOAD_BALANCING_STATIC in self._device.licenses
            if self.entity_description.key == "license_high_power_sockets":
                self._attr_is_on = LICENSE_HIGH_POWER in self._device.licenses
            if self.entity_description.key == "license_rfid_reader":
                self._attr_is_on = LICENSE_RFID in self._device.licenses
            if self.entity_description.key == "license_personalized_display":
                self._attr_is_on = LICENSE_PERSONALIZED_DISPLAY in self._device.licenses
            if self.entity_description.key == "license_mobile_3G_4G":
                self._attr_is_on = LICENSE_MOBILE in self._device.licenses
            if self.entity_description.key == "license_giro_e":
                self._attr_is_on = LICENSE_PAYMENT_GIROE in self._device.licenses
#            if self.entity_description.key == "license_qrcode":
#                self._attr_is_on = LICENSE_PAYMENT_QRCODE in self._device.licenses
#            if self.entity_description.key == "license_expose_smartmeterdata":
#                self._attr_is_on = LICENSE_EXPOSE_SMARTMETERDATA in self._device.licenses

    @property
    def available(self) -> bool:
        """Return True if entity is available."""

        if self.entity_description.api_param is not None:
            for prop in self._device.properties:
                if prop[ID] == self.entity_description.api_param:
                    return True
            return False
        else:
            return True

    @property
    def is_on(self) -> bool:
        """Return True if entity is on."""

        if self.entity_description.api_param is not None:
            for prop in self._device.properties:
                if prop[ID] == self.entity_description.api_param:
                    return prop[VALUE] == 1
            return False
        else:
            return self._attr_is_on
