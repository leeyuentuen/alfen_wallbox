"""Base entity for Alfen Wallbox integration."""

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN as ALFEN_DOMAIN
from .coordinator import AlfenConfigEntry, AlfenCoordinator


class AlfenEntity(CoordinatorEntity[AlfenCoordinator], Entity):
    """Define a base Alfen entity."""

    # Note: _attr_has_entity_name = True would be ideal for gold tier compliance,
    # but enabling it would change entity_id patterns and break existing installations.
    # This should be enabled in a future major version with proper migration.

    def __init__(self, entry: AlfenConfigEntry) -> None:
        """Initialize the Alfen entity."""

        super().__init__(entry.runtime_data)
        self.coordinator = entry.runtime_data

        device_info = self.coordinator.device.info
        self._attr_device_info = DeviceInfo(
            identifiers={(ALFEN_DOMAIN, self.coordinator.device.name)},
            manufacturer="Alfen",
            model=device_info.model if device_info else "Unknown",
            name=self.coordinator.device.name,
            sw_version=device_info.firmware_version if device_info else "Unknown",
        )

    @property
    def available(self) -> bool:
        """Return if entity is available.

        Entities remain available even when coordinator updates fail, as long as we have
        cached data from previous successful updates. This prevents all sensors from
        becoming unavailable during brief network interruptions or timeouts.

        The coordinator preserves the properties dict between update cycles, so entities
        can continue displaying the last known values during transient failures.
        """
        return True

    async def async_added_to_hass(self) -> None:
        """Add listener for state changes."""
        await super().async_added_to_hass()
