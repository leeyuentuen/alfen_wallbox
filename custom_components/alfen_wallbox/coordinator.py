"""Class representing a Alfen Wallbox update coordinator."""

import asyncio
from asyncio import timeout
from datetime import timedelta
import logging
from ssl import CERT_NONE

from aiohttp import ClientConnectionError, ClientSession, TCPConnector
from aiohttp.connector import TCPConnector as TCPConnectorType
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_SCAN_INTERVAL,
    CONF_TIMEOUT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util.ssl import get_default_context

from .alfen import AlfenDevice
from .const import (
    CONF_CATEGORIES_PER_CYCLE,
    CONF_CATEGORY_FETCH_DELAY,
    CONF_REFRESH_CATEGORIES,
    DEFAULT_CATEGORIES_PER_CYCLE,
    DEFAULT_CATEGORY_FETCH_DELAY,
    DEFAULT_REFRESH_CATEGORIES,
    DEFAULT_SCAN_INTERVAL,
    DEFAULT_TIMEOUT,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

type AlfenConfigEntry = ConfigEntry[AlfenCoordinator]


def _create_tcp_connector() -> TCPConnectorType:
    """Create a TCPConnector configured for Alfen wallbox communication.

    The wallbox uses CONNECTION-BASED authentication:
    - Login authenticates a specific TCP connection, not a cookie/token
    - Subsequent requests MUST reuse the same TCP connection to stay authenticated
    - If connection is closed/reset, a 401 error occurs and re-authentication is needed

    Returns:
        TCPConnector configured for single persistent connection
    """
    return TCPConnector(
        limit=1,
        limit_per_host=1,
        ttl_dns_cache=600,
        keepalive_timeout=300,
        enable_cleanup_closed=True,
    )


class AlfenCoordinator(DataUpdateCoordinator[None]):
    """Alfen update coordinator."""

    def __init__(self, hass: HomeAssistant, entry: AlfenConfigEntry) -> None:
        """Initialize the coordinator."""
        # Create a custom logger adapter that prefixes all logs with device identifier
        log_id = f"{entry.data[CONF_NAME]}@{entry.data[CONF_HOST]}"

        # Create a logging adapter that automatically adds the identifier
        class PrefixAdapter(logging.LoggerAdapter):
            """Logger adapter that prefixes messages with device identifier."""
            def process(self, msg, kwargs):
                return f"[{log_id}] {msg}", kwargs

        coordinator_logger = PrefixAdapter(_LOGGER, {})

        super().__init__(
            hass,
            coordinator_logger,  # type: ignore[arg-type]
            name=DOMAIN,
            update_interval=timedelta(
                seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
            ),
        )

        self.entry = entry
        self.hass = hass
        self.device: AlfenDevice = None  # type: ignore[assignment]
        self.timeout = self.entry.options.get(CONF_TIMEOUT, DEFAULT_TIMEOUT)
        self._session: ClientSession | None = None
        self._session_lock = asyncio.Lock()  # Protect session recreation from race conditions

    async def _async_setup(self):
        """Set up the coordinator."""
        self._session = ClientSession(connector=_create_tcp_connector())

        # Default ciphers needed as of python 3.10
        context = get_default_context()

        context.set_ciphers("DEFAULT")
        context.check_hostname = False
        context.verify_mode = CERT_NONE

        self.device = AlfenDevice(
            self._session,
            self.entry.data[CONF_HOST],
            self.entry.data[CONF_NAME],
            self.entry.data[CONF_USERNAME],
            self.entry.data[CONF_PASSWORD],
            self.entry.options.get(CONF_REFRESH_CATEGORIES, DEFAULT_REFRESH_CATEGORIES),
            context,
            lambda: self.async_refresh(),  # Use async_refresh() for immediate updates (no debounce)
            self.entry.options.get(CONF_CATEGORIES_PER_CYCLE, DEFAULT_CATEGORIES_PER_CYCLE),
            self.entry.options.get(CONF_CATEGORY_FETCH_DELAY, DEFAULT_CATEGORY_FETCH_DELAY),
        )
        # Set callback for session recreation after logout
        self.device._session_recreate_callback = lambda: self._recreate_session()
        if not await self.async_connect():
            raise UpdateFailed("Error communicating with API")

    async def _recreate_session(self):
        """Recreate the ClientSession with a new connector (e.g., after logout closes the connection)."""
        # Use lock to prevent multiple concurrent recreation attempts
        async with self._session_lock:
            # Double-check session is still closed after acquiring lock
            # (another thread might have already recreated it)
            if self._session and not self._session.closed:
                _LOGGER.debug("[%s] Session already open after lock acquisition - skipping recreation", self.device.log_id)
                return

            # Close existing session if it exists
            if self._session:
                try:
                    await self._session.close()
                except Exception as e:
                    _LOGGER.debug("[%s] Error closing session: %s", self.device.log_id, str(e))

            # Create new session with same connector configuration
            self._session = ClientSession(connector=_create_tcp_connector())
            self.device._session = self._session
            _LOGGER.debug("[%s] Recreated ClientSession with new connector", self.device.log_id)

    async def _async_update_data(self) -> None:
        """Fetch data from API endpoint."""
        try:
            # Use longer timeout for first update when loading static properties
            # Static properties can take 30-60s depending on number of categories and delay
            update_timeout = 120 if self.device.get_static_properties else self.timeout

            async with timeout(update_timeout):
                if not await self.device.async_update():
                    raise UpdateFailed("Error updating")
        except TimeoutError as exc:
            _LOGGER.warning("[%s] Update timed out after %ss", self.device.log_id, update_timeout)
            # Force re-login on next update to clear potentially stale connection state
            _LOGGER.debug("[%s] Resetting logged_in flag to force re-authentication", self.device.log_id)
            self.device.logged_in = False
            # Don't sleep - let the coordinator's update_interval handle retry timing
            # Sleeping here would block the entire coordinator
            raise UpdateFailed("Update timed out") from exc

    async def async_connect(self) -> bool:
        """Connect to the API endpoint."""
        # Get log_id - use device's if available, otherwise construct from config
        log_id = (
            self.device.log_id
            if self.device and hasattr(self.device, "log_id")
            else f"{self.entry.data[CONF_NAME]}@{self.entry.data[CONF_HOST]}"
        )

        try:
            async with timeout(self.timeout):
                return await self.device.init()
        except TimeoutError:
            _LOGGER.debug("[%s] Connection timed out", log_id)
            return False
        except ClientConnectionError as e:
            _LOGGER.debug(
                "[%s] ClientConnectionError: %s",
                log_id,
                str(e),
            )
            return False
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error(
                "[%s] Unexpected error creating device: %s",
                log_id,
                str(e),
            )
            return False


async def options_update_listener(self, entry: AlfenConfigEntry):
    """Handle options update."""
    coordinator = entry.runtime_data
    coordinator.device.get_static_properties = True
    coordinator.device.category_options = entry.options.get(
        CONF_REFRESH_CATEGORIES, DEFAULT_REFRESH_CATEGORIES
    )
    coordinator.device.categories_per_cycle = entry.options.get(
        CONF_CATEGORIES_PER_CYCLE, DEFAULT_CATEGORIES_PER_CYCLE
    )
    coordinator.device.category_fetch_delay = entry.options.get(
        CONF_CATEGORY_FETCH_DELAY, DEFAULT_CATEGORY_FETCH_DELAY
    )

    coordinator.update_interval = timedelta(
        seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
    )
