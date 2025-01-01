"""Support for Alfen Eve Single Proline Wallbox."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from homeassistant.components.counter import VALUE
from homeassistant.components.text import TextEntity, TextEntityDescription, TextMode
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import CAT, ID
from .coordinator import AlfenConfigEntry
from .entity import AlfenEntity


@dataclass
class AlfenTextDescriptionMixin:
    """Define an entity description mixin for text entities."""

    api_param: str


@dataclass
class AlfenTextDescription(TextEntityDescription, AlfenTextDescriptionMixin):
    """Class to describe an Alfen text entity."""


ALFEN_TEXT_TYPES: Final[tuple[AlfenTextDescription, ...]] = (
    AlfenTextDescription(
        key="auth_plug_and_charge_id",
        name="Auth. Plug & Charge ID",
        icon="mdi:key",
        mode=TextMode.TEXT,
        api_param="2063_0",
    ),
    AlfenTextDescription(
        key="proxy_address_port",
        name="Proxy Address And Port",
        icon="mdi:earth",
        mode=TextMode.TEXT,
        api_param="2115_0",
    ),
    AlfenTextDescription(
        key="proxy_username",
        name="Proxy Username",
        icon="mdi:account",
        mode=TextMode.TEXT,
        api_param="2116_0",
    ),
    AlfenTextDescription(
        key="proxy_password",
        name="Proxy Password",
        icon="mdi:key",
        mode=TextMode.PASSWORD,
        api_param="2116_1",
    ),
    AlfenTextDescription(
        key="price_other_description",
        name="Price other description",
        icon="mdi:tag-text-outline",
        mode=TextMode.TEXT,
        api_param="3262_7",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: AlfenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Add Alfen Select from a config_entry."""

    texts = [AlfenText(entry, description) for description in ALFEN_TEXT_TYPES]

    async_add_entities(texts)


class AlfenText(AlfenEntity, TextEntity):
    """Representation of a Alfen text entity."""

    entity_description: AlfenTextDescription

    def __init__(
        self, entry: AlfenConfigEntry, description: AlfenTextDescription
    ) -> None:
        """Initialize the Alfen text entity."""
        super().__init__(entry)

        self._attr_name = f"{self.coordinator.device.name} {description.name}"
        self._attr_mode = description.mode
        self._attr_unique_id = f"{self.coordinator.device.id}_{description.key}"
        self.entity_description = description
        self._async_update_attrs()

    @callback
    def _async_update_attrs(self) -> None:
        """Update text attributes."""
        self._attr_native_value = self._get_current_value()

    def _get_current_value(self) -> str | None:
        """Return the current value."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                return prop[VALUE]
        return None

    async def async_set_value(self, value: str) -> None:
        """Update the value."""
        self._attr_native_value = value
        await self.coordinator.device.set_value(
            self.entity_description.api_param, value
        )
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self):
        """Return the default attributes of the element."""
        for prop in self.coordinator.device.properties:
            if prop[ID] == self.entity_description.api_param:
                return {"category": prop[CAT]}
        return None
