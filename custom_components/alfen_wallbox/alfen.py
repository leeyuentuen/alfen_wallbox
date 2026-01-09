"""Alfen Wallbox API."""

from __future__ import annotations

import asyncio
from asyncio import timeout
from collections import deque
from collections.abc import Callable
import datetime
import hashlib
import json
import logging
import re
from ssl import SSLContext
import time
from typing import Any
from urllib.parse import urlencode

from aiohttp import ClientSession, ClientTimeout

from .const import (
    ALFEN_PRODUCT_MAP,
    CAT,
    CAT_GENERIC,
    CAT_LOGS,
    CAT_STATES,
    CAT_TRANSACTIONS,
    CATEGORIES,
    CMD,
    COMMAND_CLEAR_TRANSACTIONS,
    COMMAND_REBOOT,
    DEFAULT_TIMEOUT,
    DOMAIN,
    ID,
    INFO,
    LICENSES,
    LOGIN,
    LOGOUT,
    METHOD_GET,
    OFFSET,
    PARAM_COMMAND,
    PARAM_DISPLAY_NAME,
    PARAM_PASSWORD,
    PARAM_USERNAME,
    PROP,
    PROPERTIES,
    TOTAL,
    VALUE,
)

POST_HEADER_JSON = {"Content-Type": "application/json"}

_LOGGER = logging.getLogger(__name__)

# Pattern for extracting socket number from log messages
SOCKET_PATTERN = re.compile(r'Socket #(\d+)')
# Pattern for extracting tag from log messages
TAG_PATTERN = re.compile(r'tag:\s*(\S+)')

# Rate limiting constants for login attempts
LOGIN_RATE_LIMIT_WINDOW = 60  # seconds
LOGIN_RATE_LIMIT_MAX_ATTEMPTS = 5  # max attempts per window

# Valid characters for API parameter IDs (alphanumeric, underscore, hyphen)
API_PARAM_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')


class AlfenDevice:
    """Alfen Device."""

    def __init__(
        self,
        session: ClientSession,
        host: str,
        name: str,
        username: str,
        password: str,
        category_options: list,
        ssl: SSLContext,
        value_updated_callback: Callable[[], Any] | None = None,
        categories_per_cycle: int = 3,
        category_fetch_delay: float = 2.0,
    ) -> None:
        """Init."""

        self.host = host
        self.name = name
        # Create unique identifier for logging (e.g., "MyWallbox@192.168.1.100")
        self.log_id = f"{name}@{host}"
        self._session = session
        self.username = username
        self.category_options = category_options
        self.categories_per_cycle = categories_per_cycle
        self.info: AlfenDeviceInfo | None = None
        self.id: str | None = None
        self.username = username if username is not None else "admin"
        self.password = password
        self.properties: dict[str, Any] = {}
        # SSL verification is handled via ssl parameter in each request, not session attribute
        self.keep_logout = False
        self.max_allowed_phases = 1
        self.latest_tag: dict[tuple[str, str, str], Any] | None = None
        self.transaction_offset = 0
        self.transaction_counter = 0
        self.log_counter = 0
        self.category_rotation_index = 0
        self.ssl = ssl
        self.static_properties: list[dict[str, Any]] = []
        self.get_static_properties = True
        # Start logged out - proactive login will authenticate before first request
        self.logged_in = False
        # Delay between category fetches to spread API load (configurable, 0-5 seconds)
        self.category_fetch_delay = category_fetch_delay
        self.last_updated: datetime.datetime | None = None
        # Use deque with maxlen to limit memory usage
        self.latest_logs: deque[str] = deque(maxlen=500)
        # prevent multiple call to wallbox
        self._lock = asyncio.Lock()
        self.update_values: dict[str, dict[str, Any]] = {}
        self._updating_lock = asyncio.Lock()
        self._update_values_lock = asyncio.Lock()
        # Callback to trigger immediate refresh after value updates
        self._value_updated_callback = value_updated_callback
        # Callback to recreate session after logout closes the connection
        self._session_recreate_callback: Callable[[], Any] | None = None
        # Rate limiting for login attempts (security)
        self._login_attempts: list[float] = []

    async def init(self) -> bool:
        """Initialize the Alfen API."""
        # Proactively login before first API call
        if not self.logged_in:
            _LOGGER.debug("[%s] Not logged in - logging in before init", self.log_id)
            await self.login()
            if not self.logged_in:
                _LOGGER.debug("[%s] Login failed - init cannot continue", self.log_id)
                return False

        result = await self.get_info()
        if not self.name and self.info:
            self.name = f"{self.info.identity} ({self.host})"
        self.id = f"alfen_{self.name}"

        return result

    def get_number_of_sockets(self) -> int | None:
        """Get number of sockets from the properties."""
        sockets = 1
        if "205E_0" in self.properties:
            sockets = self.properties["205E_0"][VALUE]
        return sockets

    def get_licenses(self) -> list[str]:
        """Get licenses from the properties."""
        licenses: list[str] = []
        if "21A2_0" in self.properties:
            prop = self.properties["21A2_0"]
            for key, value in LICENSES.items():
                if int(prop[VALUE]) & int(value):
                    licenses.append(key)
        return licenses

    async def get_info(self) -> bool:
        """Get info from the API."""
        response = await self._session.get(url=self.__get_url(INFO), ssl=self.ssl)
        _LOGGER.debug("[%s] Response %s", self.log_id, str(response))

        if response.status == 200:
            resp = await response.json(content_type=None)
            self.info = AlfenDeviceInfo(resp)

            return True

        _LOGGER.debug("[%s] Info API not available, use generic info", self.log_id)
        generic_info = {
            "Identity": self.host,
            "FWVersion": "?",
            "Model": "Generic Alfen Wallbox",
            "ObjectId": "?",
            "Type": "?",
        }
        self.info = AlfenDeviceInfo(generic_info)
        return False

    @property
    def device_info(self) -> dict[str, Any]:
        """Return a device description for device registry."""
        return {
            "identifiers": {(DOMAIN, self.name)},
            "manufacturer": "Alfen",
            "model": self.info.model if self.info else "Unknown",
            "name": self.name,
            "sw_version": self.info.firmware_version if self.info else "Unknown",
        }

    async def _proactive_login(self) -> bool:
        """Proactively login if not logged in to avoid 401 warnings.

        Returns:
            True if logged in successfully or already logged in, False otherwise
        """
        if not self.logged_in:
            _LOGGER.debug("[%s] Not logged in - logging in proactively", self.log_id)
            try:
                # Use 10-second timeout for proactive login to prevent hanging
                async with timeout(10):
                    await self.login()
            except TimeoutError:
                _LOGGER.warning(
                    "[%s] Proactive login timed out after 10s - aborting update cycle",
                    self.log_id
                )
                self.logged_in = False
            except Exception as e:
                _LOGGER.warning(
                    "[%s] Proactive login failed: %s - aborting update cycle",
                    self.log_id,
                    str(e)
                )
                self.logged_in = False

            return self.logged_in
        return True

    async def _process_value_updates(self) -> bool:
        """Process pending value updates from the update queue.

        Returns:
            True if any values were updated successfully, False otherwise
        """
        # Copy the values to avoid dict changed size error
        async with self._update_values_lock:
            values = self.update_values.copy()

        # Process pending value updates
        value_was_updated = False
        updated_categories = set()  # Track which categories had updates
        successfully_processed_keys = set()  # Track which keys were successfully processed

        if values:
            _LOGGER.debug("[%s] Processing %d pending value updates", self.log_id, len(values))

        for key, value in values.items():
            response = await self._update_value(value["api_param"], value["value"])

            if response:
                # Update the value in the properties dict
                if value["api_param"] in self.properties:
                    prop = self.properties[value["api_param"]]
                    _LOGGER.debug(
                        "[%s] Set %s value %s",
                        self.log_id,
                        str(value["api_param"]),
                        str(value["value"]),
                    )
                    prop[VALUE] = value["value"]
                    self.properties[value["api_param"]] = prop
                    # Track which category this property belongs to
                    if CAT in prop:
                        updated_categories.add(prop[CAT])
                # Track this key for deletion (but don't delete yet to avoid race condition)
                successfully_processed_keys.add(key)
                value_was_updated = True
            else:
                # Log failure but don't remove from update_values so it will retry
                _LOGGER.warning(
                    "[%s] Failed to update %s to %s - will retry on next update cycle",
                    self.log_id,
                    value["api_param"],
                    value["value"],
                )

        # Remove all successfully processed keys in a single locked operation
        # This prevents race condition where new values are added during processing
        if successfully_processed_keys:
            async with self._update_values_lock:
                for key in successfully_processed_keys:
                    # Check key still exists and has same value we processed
                    # If value changed, keep it in queue for next cycle
                    if key in self.update_values:
                        if self.update_values[key]["value"] == values[key]["value"]:
                            del self.update_values[key]
                        else:
                            _LOGGER.debug(
                                "[%s] Value for %s changed during processing - will process new value next cycle",
                                self.log_id,
                                key
                            )

        # After updating values, wallbox closes the connection
        if value_was_updated:
            # Mark as not logged in - next request will automatically re-authenticate
            self.logged_in = False
            _LOGGER.debug(
                "[%s] Value updated - marked as logged out (wallbox closes connection after updates)",
                self.log_id
            )

            # Fetch categories that contain updated properties to confirm changes
            await self._fetch_post_update_categories(updated_categories)

        return value_was_updated

    async def _fetch_post_update_categories(self, updated_categories: set[str]) -> None:
        """Fetch categories after value updates to confirm changes.

        Args:
            updated_categories: Set of category names that had property updates
        """
        # Also include CAT_STATES for status information if not already included
        categories_to_fetch = list(updated_categories)
        if CAT_STATES not in categories_to_fetch and CAT_STATES in self.category_options:
            categories_to_fetch.append(CAT_STATES)

        # Filter to only categories that are in category_options
        categories_to_fetch = [cat for cat in categories_to_fetch
                              if cat in self.category_options]

        if categories_to_fetch:
            _LOGGER.debug(
                "[%s] Fetching %d categories after value update: %s",
                self.log_id,
                len(categories_to_fetch),
                categories_to_fetch,
            )
            try:
                for idx, cat in enumerate(categories_to_fetch):
                    props = await self._get_all_properties_value(cat)
                    # Update properties dict with fresh data
                    for prop in props:
                        if ID in prop:
                            self.properties[prop[ID]] = prop

                    # Add delay between category fetches
                    if idx < len(categories_to_fetch) - 1 and self.category_fetch_delay > 0:
                        await asyncio.sleep(self.category_fetch_delay)
            except Exception as e:
                _LOGGER.warning(
                    "[%s] Failed to fetch categories after value update: %s",
                    self.log_id,
                    str(e),
                )

    async def _fetch_static_properties(self) -> list[dict[str, Any]]:
        """Fetch static properties (one-time load at startup).

        Returns:
            List of property dictionaries from static categories
        """
        static_properties = []

        # Always include CAT_GENERIC in static load - it contains critical config
        # (licenses, socket count, etc.) that entities depend on during setup
        static_cats = [cat for cat in CATEGORIES if cat not in (CAT_TRANSACTIONS, CAT_LOGS) and cat not in self.category_options]
        # Ensure generic is always loaded first, even if it's in refresh categories
        if CAT_GENERIC not in static_cats and CAT_GENERIC in CATEGORIES:
            static_cats.insert(0, CAT_GENERIC)

        _LOGGER.debug(
            "[%s] Loading static properties from %d categories (this may take a while)",
            self.log_id,
            len(static_cats),
        )

        for idx, cat in enumerate(static_cats):
            props = await self._get_all_properties_value(cat)
            static_properties.extend(props)

            # Add delay between static category fetches to reduce initial load
            if idx < len(static_cats) - 1 and self.category_fetch_delay > 0:
                await asyncio.sleep(self.category_fetch_delay)

        _LOGGER.debug("[%s] Static properties loaded successfully", self.log_id)
        return static_properties

    async def _fetch_dynamic_properties(self) -> list[dict[str, Any]]:
        """Fetch dynamic properties using rotating categories to reduce load.

        Returns:
            List of property dictionaries from fetched categories
        """
        dynamic_properties: list[dict] = []

        # Filter out logs/transactions (handled separately with their own schedule)
        regular_categories = [cat for cat in self.category_options
                             if cat not in (CAT_TRANSACTIONS, CAT_LOGS)]

        if not regular_categories:
            return dynamic_properties

        # Number of categories to fetch per cycle (configurable in HA options)
        total_categories = len(regular_categories)

        # Calculate start index for this cycle's categories
        start_idx = (self.category_rotation_index * self.categories_per_cycle) % total_categories

        # Get the categories to fetch this cycle (wraps around if needed)
        categories_to_fetch = []
        for i in range(self.categories_per_cycle):
            idx = (start_idx + i) % total_categories
            categories_to_fetch.append(regular_categories[idx])

        _LOGGER.debug(
            "[%s] Rotating fetch: cycle %d, fetching categories %s (out of %d total)",
            self.log_id,
            self.category_rotation_index,
            categories_to_fetch,
            total_categories
        )

        # Fetch only the selected categories for this cycle
        # Add delay between fetches to reduce wallbox load and prevent crashes
        for idx, cat in enumerate(categories_to_fetch):
            props = await self._get_all_properties_value(cat)
            dynamic_properties.extend(props)

            # Add delay between category fetches (but not after the last one)
            # This spreads out API load and gives wallbox time to process
            if idx < len(categories_to_fetch) - 1 and self.category_fetch_delay > 0:
                await asyncio.sleep(self.category_fetch_delay)

        # Increment rotation index for next cycle (wrap around to prevent unbounded growth)
        self.category_rotation_index = (self.category_rotation_index + 1) % total_categories

        return dynamic_properties

    def _build_properties_dict(self, dynamic_properties: list[dict[str, Any]]) -> None:
        """Build/update properties dict from static and dynamic properties.

        Args:
            dynamic_properties: List of property dicts from dynamic categories
        """
        # Build/update properties dict
        # Static properties are loaded once at startup, dynamic properties update via rotation
        # With rotation: preserve existing properties and only update newly fetched ones
        if not self.properties:
            # First run: initialize with static properties
            self.properties = {str(prop[ID]): prop for prop in self.static_properties}

        # Update properties from the categories we just fetched (rotation or full)
        # This preserves properties from categories we didn't fetch this cycle
        for prop in dynamic_properties:
            self.properties[str(prop[ID])] = prop

    async def _fetch_logs_and_transactions(self) -> None:
        """Fetch logs and transactions according to their schedules."""
        # Only fetch logs every 20th update cycle (reduces API load)
        # With 30s scan interval, this means every ~10 minutes
        if CAT_LOGS in self.category_options:
            self.log_counter = (self.log_counter + 1) % 20
            if self.log_counter == 0:
                await self._get_log()

        # Only fetch transactions every 60th update cycle (reduces API load)
        # With 30s scan interval, this means every ~30 minutes
        if CAT_TRANSACTIONS in self.category_options:
            self.transaction_counter = (self.transaction_counter + 1) % 60
            if self.transaction_counter == 0:
                await self._get_transaction()

    async def async_update(self) -> bool:
        """Update the device properties.

        This is the main update loop that coordinates all data fetching operations.
        The method is refactored into smaller helper methods for better maintainability.
        """
        if self.keep_logout:
            return True

        update_start = datetime.datetime.now()

        # Use a proper lock to prevent concurrent updates
        async with self._updating_lock:
            # 1. Proactively login if not logged in
            if not await self._proactive_login():
                update_duration = (datetime.datetime.now() - update_start).total_seconds()
                _LOGGER.warning(
                    "[%s] Update cycle FAILED (login failed) after %.2fs",
                    self.log_id,
                    update_duration
                )
                return False

            # 2. Process pending value updates
            await self._process_value_updates()

            # 3. Update timestamp
            self.last_updated = datetime.datetime.now()

            # 4. Fetch static properties (one-time load at startup)
            if self.get_static_properties:
                self.static_properties = await self._fetch_static_properties()
                self.get_static_properties = False

            # 5. Fetch dynamic properties (rotating categories)
            dynamic_properties = await self._fetch_dynamic_properties()

            # 6. Build/update properties dict
            self._build_properties_dict(dynamic_properties)

            # 7. Fetch logs and transactions (according to schedule)
            await self._fetch_logs_and_transactions()

            # 8. Log total update time for monitoring
            update_duration = (datetime.datetime.now() - update_start).total_seconds()
            _LOGGER.info("[%s] Update cycle completed in %.2fs", self.log_id, update_duration)

            return True

    async def _post(
        self, cmd: str, payload: dict[str, Any] | None = None, allowed_login: bool = True
    ) -> Any | None:
        """Send a POST request to the API."""
        if self.keep_logout:
            return None

        # If not logged in, authenticate first (e.g., after value updates close connection)
        if not self.logged_in and allowed_login:
            _LOGGER.debug("[%s] Not logged in, authenticating before POST", self.log_id)
            await self.login()
            # If login failed, don't attempt the request
            if not self.logged_in:
                _LOGGER.debug("[%s] Login failed - skipping POST request", self.log_id)
                return None

        needs_auth = False
        async with self._lock:
            try:
                # Debug: Log connector state before request
                connector = getattr(self._session, 'connector', None)
                if connector:
                    _LOGGER.debug(
                        "[%s] POST request - connector open=%s, limit=%s, limit_per_host=%s",
                        self.log_id,
                        not connector.closed,
                        connector.limit,
                        connector.limit_per_host,
                    )

                async with self._session.post(
                    url=self.__get_url(cmd),
                    json=payload,
                    headers=POST_HEADER_JSON,
                    timeout=ClientTimeout(total=DEFAULT_TIMEOUT),
                    ssl=self.ssl,
                ) as response:
                    if response.status == 401 and allowed_login:
                        self.logged_in = False
                        _LOGGER.warning(
                            "[%s] POST returned 401 Unauthorized - connection may have been closed by wallbox",
                            self.log_id
                        )
                        needs_auth = True
                    else:
                        response.raise_for_status()
                        # Process response inside context manager
                        try:
                            result = await response.json(content_type=None)
                            return result
                        except json.JSONDecodeError as e:
                            # skip tailing comma error from alfen (known API issue with malformed JSON)
                            if e.msg == "trailing comma is not allowed":
                                _LOGGER.debug("[%s] Ignoring malformed JSON response (trailing comma) - request succeeded", self.log_id)
                                return None
                            _LOGGER.error("[%s] JSONDecodeError error on POST %s", self.log_id, str(e))
                            raise
            except TimeoutError:
                _LOGGER.warning("[%s] Timeout on POST", self.log_id)
                return None
            except Exception as e:  # pylint: disable=broad-except
                if not allowed_login:
                    _LOGGER.error("[%s] Unexpected error on POST: %s", self.log_id, self._sanitize_exception(e))
                return None

        # After lock is released, handle reauth if needed
        if needs_auth:
            await self.login()
            # Only retry if login succeeded
            if self.logged_in:
                return await self._post(cmd, payload, False)
            else:
                _LOGGER.debug("[%s] Re-authentication failed - skipping retry", self.log_id)
                return None

        return None

    async def _get(
        self, url: str, allowed_login: bool = True, json_decode: bool = True
    ) -> Any | None:
        """Send a GET request to the API."""
        if self.keep_logout:
            return None

        # If not logged in, authenticate first (e.g., after value updates close connection)
        if not self.logged_in and allowed_login:
            _LOGGER.debug("[%s] Not logged in, authenticating before GET", self.log_id)
            await self.login()
            # If login failed, don't attempt the request
            if not self.logged_in:
                _LOGGER.debug("[%s] Login failed - skipping GET request", self.log_id)
                return None

        needs_auth = False
        async with self._lock:
            try:
                # Debug: Log connector state before request
                connector = getattr(self._session, 'connector', None)
                if connector:
                    # Extract path from full URL (remove scheme and host)
                    # e.g., https://charger.local/api/prop?cat=generic&offset=0 -> /api/prop?cat=generic&offset=0
                    url_path = url
                    if "://" in url:
                        url_path = "/" + url.split("://", 1)[1].split("/", 1)[1] if "/" in url.split("://", 1)[1] else url

                    _LOGGER.debug(
                        "[%s] GET request %s - connector open=%s, limit=%s, limit_per_host=%s",
                        self.log_id,
                        url_path,
                        not connector.closed,
                        connector.limit,
                        connector.limit_per_host,
                    )

                async with self._session.get(
                    url, timeout=ClientTimeout(total=DEFAULT_TIMEOUT), ssl=self.ssl
                ) as response:
                    if response.status == 401 and allowed_login:
                        self.logged_in = False
                        _LOGGER.warning(
                            "[%s] GET returned 401 Unauthorized - connection may have been closed by wallbox",
                            self.log_id
                        )
                        needs_auth = True
                    else:
                        response.raise_for_status()
                        # Process response inside context manager
                        if json_decode:
                            result = await response.json(content_type=None)
                        else:
                            result = await response.text()
                        return result
            except TimeoutError:
                _LOGGER.warning("[%s] Timeout on GET", self.log_id)
                return None
            except Exception as e:  # pylint: disable=broad-except
                if not allowed_login:
                    _LOGGER.error("[%s] Unexpected error on GET: %s", self.log_id, self._sanitize_exception(e))
                return None

        # After lock is released, handle reauth if needed
        if needs_auth:
            await self.login()
            # Only retry if login succeeded
            if self.logged_in:
                return await self._get(url=url, allowed_login=False, json_decode=json_decode)
            else:
                _LOGGER.debug("[%s] Re-authentication failed - skipping retry", self.log_id)
                return None

        return None

    def _check_login_rate_limit(self) -> bool:
        """Check if login attempts are within rate limit.

        Returns:
            True if login is allowed, False if rate limited
        """
        current_time = time.time()
        # Remove old attempts outside the window
        self._login_attempts = [
            t for t in self._login_attempts
            if current_time - t < LOGIN_RATE_LIMIT_WINDOW
        ]
        # Check if we've exceeded the limit
        if len(self._login_attempts) >= LOGIN_RATE_LIMIT_MAX_ATTEMPTS:
            _LOGGER.warning(
                "[%s] Login rate limited: %d attempts in %ds window",
                self.log_id,
                len(self._login_attempts),
                LOGIN_RATE_LIMIT_WINDOW,
            )
            return False
        return True

    def _record_login_attempt(self) -> None:
        """Record a login attempt for rate limiting."""
        self._login_attempts.append(time.time())

    @staticmethod
    def _sanitize_exception(exc: Exception) -> str:
        """Sanitize exception message to avoid leaking sensitive information.

        Args:
            exc: The exception to sanitize

        Returns:
            A sanitized error message safe for logging
        """
        # Get exception type and message
        exc_type = type(exc).__name__
        exc_msg = str(exc)

        # Remove potential file paths (Unix and Windows)
        exc_msg = re.sub(r'(/[^\s:]+)+', '<path>', exc_msg)
        exc_msg = re.sub(r'([A-Za-z]:\\[^\s:]+)+', '<path>', exc_msg)

        # Remove IP addresses (but keep hostname references generic)
        exc_msg = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '<ip>', exc_msg)

        # Remove potential credentials or tokens (long alphanumeric strings)
        exc_msg = re.sub(r'\b[A-Za-z0-9]{32,}\b', '<redacted>', exc_msg)

        # Truncate if too long
        if len(exc_msg) > 200:
            exc_msg = exc_msg[:200] + "..."

        return f"{exc_type}: {exc_msg}"

    def _validate_api_param(self, api_param: str) -> bool:
        """Validate API parameter ID format.

        Args:
            api_param: The API parameter ID to validate

        Returns:
            True if valid, False otherwise
        """
        if not api_param or not isinstance(api_param, str):
            return False
        # API params should be alphanumeric with underscores (e.g., "2129_0")
        return bool(API_PARAM_PATTERN.match(api_param))

    def _sanitize_tag_for_logging(self) -> dict[str, Any]:
        """Create a sanitized version of latest_tag for safe logging.

        Returns:
            A dict with RFID tags hashed for privacy
        """
        if self.latest_tag is None:
            return {}

        sanitized = {}
        for key, value in self.latest_tag.items():
            key_str = str(key)
            # Hash actual RFID tag values (key[2] == "tag")
            if isinstance(key, tuple) and len(key) >= 3 and key[2] == "tag":
                if value and value not in (None, "No Tag", ""):
                    # Create short hash for identification
                    hash_val = hashlib.sha256(str(value).encode()).hexdigest()[:8]
                    sanitized[key_str] = f"<tag:{hash_val}>"
                else:
                    sanitized[key_str] = value
            else:
                sanitized[key_str] = value
        return sanitized

    def _validate_properties_response(self, response: Any) -> bool:
        """Validate the structure of a properties API response.

        Args:
            response: The API response to validate

        Returns:
            True if valid structure, False otherwise
        """
        if not isinstance(response, dict):
            return False

        # Check required keys
        if PROPERTIES not in response or TOTAL not in response:
            return False

        # Validate PROPERTIES is a list
        if not isinstance(response[PROPERTIES], list):
            return False

        # Validate TOTAL is an integer
        if not isinstance(response[TOTAL], int):
            return False

        # Validate each property has required structure
        for prop in response[PROPERTIES]:
            if not isinstance(prop, dict):
                return False
            if ID not in prop:
                return False

        return True

    async def login(self):
        """Login to the API."""
        self.keep_logout = False

        # Check rate limiting before attempting login
        if not self._check_login_rate_limit():
            _LOGGER.warning("[%s] Login blocked by rate limiter", self.log_id)
            return

        # Record this login attempt
        self._record_login_attempt()

        # Check if session/connector needs recreation (e.g., after logout)
        if self._session.closed or (hasattr(self._session, 'connector') and self._session.connector and self._session.connector.closed):
            _LOGGER.debug("[%s] Session or connector is closed, recreating before login", self.log_id)
            if self._session_recreate_callback:
                await self._session_recreate_callback()
            else:
                _LOGGER.warning("[%s] Session is closed but no recreation callback available", self.log_id)

        try:
            _LOGGER.debug("[%s] Attempting login for user %s", self.log_id, self.username)

            # Capture response headers to understand authentication mechanism
            response = None
            async with self._lock:
                try:
                    async with self._session.post(
                        url=self.__get_url(LOGIN),
                        json={
                            PARAM_USERNAME: self.username,
                            PARAM_PASSWORD: self.password,
                            # Use friendly name (truncated to 32 chars) as session display name
                            PARAM_DISPLAY_NAME: self.name[:32] if self.name else "HomeAssistant",
                        },
                        headers=POST_HEADER_JSON,
                        timeout=ClientTimeout(total=DEFAULT_TIMEOUT),
                        ssl=self.ssl,
                    ) as http_response:
                        _LOGGER.debug("[%s] Login response status: %d", self.log_id, http_response.status)

                        # Log headers for debugging (convert to dict safely)
                        try:
                            headers_dict = dict(http_response.headers)
                            _LOGGER.debug("[%s] Login response headers: %s", self.log_id, headers_dict)
                        except Exception:
                            _LOGGER.debug("[%s] Could not log response headers", self.log_id)

                        http_response.raise_for_status()
                        try:
                            response = await http_response.json(content_type=None)
                        except Exception:
                            response = None
                except Exception as e:
                    _LOGGER.error("[%s] Login request failed: %s", self.log_id, self._sanitize_exception(e))
                    # Don't set logged_in = True if login failed
                    raise

            # Only set logged_in = True if we got here without exception
            self.logged_in = True
            self.last_updated = datetime.datetime.now()

            if response is None:
                _LOGGER.debug("[%s] Login successful (no response body or malformed JSON)", self.log_id)
            else:
                _LOGGER.debug("[%s] Login successful: %s", self.log_id, response)
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("[%s] Unexpected error on LOGIN: %s", self.log_id, self._sanitize_exception(e))
            # Ensure logged_in stays False on error
            self.logged_in = False
            return

    async def logout(self):
        """Logout from the API."""
        self.keep_logout = True

        try:
            response = await self._post(cmd=LOGOUT, allowed_login=False)
            self.logged_in = False
            self.last_updated = datetime.datetime.now()

            if response is None:
                _LOGGER.debug("[%s] Logout successful (no response body or malformed JSON)", self.log_id)
            else:
                _LOGGER.debug("[%s] Logout successful: %s", self.log_id, response)

            # Close the TCP connection after logout (connection-based auth)
            # This ensures the wallbox knows we've disconnected and allows other clients to connect
            if hasattr(self._session, 'connector') and self._session.connector:
                # Close all connections in the connector (should only be 1)
                await self._session.connector.close()
                _LOGGER.debug("[%s] Closed TCP connection after logout", self.log_id)

        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("[%s] Unexpected error on LOGOUT: %s", self.log_id, self._sanitize_exception(e))
            return

    async def _update_value(
        self, api_param: str, value: Any, allowed_login: bool = True
    ) -> bool | None:
        """Update a value on the API."""
        if self.keep_logout:
            return None

        needs_auth = False
        async with self._lock:
            try:
                async with self._session.post(
                    url=self.__get_url(PROP),
                    json={api_param: {ID: api_param, VALUE: str(value)}},
                    headers=POST_HEADER_JSON,
                    timeout=ClientTimeout(total=DEFAULT_TIMEOUT),
                    ssl=self.ssl,
                ) as response:
                    if response.status == 401 and allowed_login:
                        self.logged_in = False
                        _LOGGER.debug("[%s] POST(Update) with login - will retry after lock release", self.log_id)
                        needs_auth = True
                    else:
                        response.raise_for_status()
                        # Note: Wallbox may close connection after value updates
                        # Next request will get 401 and automatically re-authenticate
                        # Return True to indicate success
                        return True
            except TimeoutError:
                _LOGGER.warning("[%s] Timeout on UPDATE VALUE", self.log_id)
                return None
            except Exception as e:  # pylint: disable=broad-except
                if not allowed_login:
                    _LOGGER.error("[%s] Unexpected error on UPDATE VALUE: %s", self.log_id, self._sanitize_exception(e))
                return None

        # After lock is released, handle reauth if needed
        if needs_auth:
            await self.login()
            return await self._update_value(api_param, value, False)

        return None

    async def _get_value(self, api_param: str) -> None:
        """Get a value from the API."""
        # Validate API parameter format
        if not self._validate_api_param(api_param):
            _LOGGER.warning("[%s] Invalid API parameter format: %s", self.log_id, api_param[:50] if api_param else "None")
            return

        # Use urlencode for safe URL construction
        query = urlencode({ID: api_param})
        cmd = f"{PROP}?{query}"
        response = await self._get(url=self.__get_url(cmd))
        # _LOGGER.debug("Status Response %s: %s", cmd, str(response))

        if response is not None:
            for resp in response[PROPERTIES]:
                if resp[ID] in self.properties:
                    self.properties[str(resp[ID])] = resp

    async def _get_all_properties_value(self, category: str) -> list[dict[str, Any]]:
        """Get all properties from the API."""
        properties: list[dict[str, Any]] = []
        tx_start = datetime.datetime.now()
        nextRequest = True
        offset = 0
        attempt = 0

        while nextRequest:
            attempt += 1
            # Use urlencode for safe URL construction
            query = urlencode({CAT: category, OFFSET: offset})
            cmd = f"{PROP}?{query}"
            response = await self._get(url=self.__get_url(cmd))

            if response is not None:
                attempt = 0
                # if response is a string, convert it to json
                if isinstance(response, str):
                    try:
                        response = json.loads(response)
                    except json.JSONDecodeError:
                        _LOGGER.error("[%s] Failed to parse JSON response for category %s", self.log_id, category)
                        break

                # Validate response structure using comprehensive validation
                if not self._validate_properties_response(response):
                    _LOGGER.warning("[%s] Invalid response structure for category %s", self.log_id, category)
                    break

                # merge the properties with response properties
                properties.extend(response[PROPERTIES])
                nextRequest = response[TOTAL] > (offset + len(response[PROPERTIES]))
                offset += len(response[PROPERTIES])
            elif attempt >= 3:
                # This only possible in case of series of timeouts or unknown exceptions in self._get()
                # It's better to break completely, otherwise we can provide partial data in self.properties.
                _LOGGER.warning("[%s] Failed to fetch %s after %d attempts, returning partial data", self.log_id, category, attempt)
                break
            else:
                # Brief backoff before retry
                await asyncio.sleep(2)

        runtime = (datetime.datetime.now() - tx_start).total_seconds()
        if properties:
            # Log at INFO level if category fetch is slow (>5s), otherwise DEBUG
            if runtime > 5:
                _LOGGER.info("[%s] Fetched %d properties from %s in %.2fs (SLOW)", self.log_id, len(properties), category, runtime)
            else:
                _LOGGER.debug("[%s] Fetched %d properties from %s in %.2fs", self.log_id, len(properties), category, runtime)
        else:
            _LOGGER.warning("[%s] No properties fetched from %s (took %.2fs)", self.log_id, category, runtime)

        return properties

    async def reboot_wallbox(self):
        """Reboot the wallbox."""
        response = await self._post(cmd=CMD, payload={PARAM_COMMAND: COMMAND_REBOOT})
        _LOGGER.debug("[%s] Reboot response %s", self.log_id, str(response))

    async def clear_transactions(self):
        """Clear the transactions."""
        response = await self._post(
            cmd=CMD, payload={PARAM_COMMAND: COMMAND_CLEAR_TRANSACTIONS}
        )
        _LOGGER.debug("[%s] Clear Transactions response %s", self.log_id, str(response))

    async def send_command(self, command: dict[str, Any]) -> None:
        """Run a command."""
        response = await self._post(cmd=CMD, payload=command)
        _LOGGER.debug("[%s] Run Command response %s", self.log_id, str(response))

    async def _fetch_log(self, log_offset: int) -> bool | None:
        """Fetch the log."""
        # Validate and cap offset to prevent unbounded values
        if not isinstance(log_offset, int) or log_offset < 0:
            log_offset = 0
        log_offset = min(log_offset, 100000)

        # Use urlencode for safe URL construction
        query = urlencode({OFFSET: log_offset})
        response = await self._get(
            url=self.__get_url(f"log?{query}"),
            json_decode=False,
        )
        if response is None:
            return None
        lines = response.splitlines()

        # Add unique lines to deque (deque automatically handles maxlen)
        for line in lines:
            if line and line not in self.latest_logs:
                self.latest_logs.append(line)

        return True

    async def _get_log(self) -> None:
        """Get the log."""
        log_offset = 0

        # Fetch logs (max 5 pages)
        while await self._fetch_log(log_offset):
            log_offset += 1
            if log_offset > 5:
                break

        # Process logs in reverse order (most recent first)
        if self.latest_tag is None:
            self.latest_tag = {}

        for log_line in reversed(self.latest_logs):
            # Parse log line format: <line_id>_<rest>
            underscore_pos = log_line.find("_")
            if underscore_pos == -1 or underscore_pos >= 20:
                continue

            try:
                line_id = int(log_line[:underscore_pos])
            except ValueError:
                _LOGGER.debug("[%s] Skipping log line with invalid ID format: %s", self.log_id, log_line)
                continue

            # Split remaining content by colons
            parts = log_line[underscore_pos + 1:].split(":")
            if len(parts) < 7:
                continue

            # Reconstruct message from parts[6] onwards
            message = ":".join(parts[6:])

            # Extract socket number if present
            socket_match = SOCKET_PATTERN.search(message)
            if not socket_match:
                continue
            socket = socket_match.group(1)

            # Check for connection events with tags
            is_connect = any(event in message for event in ("EV_CONNECTED_AUTHORIZED", "CHARGING_POWER_ON", "CABLE_CONNECTED"))
            is_disconnect = any(event in message for event in ("CHARGING_POWER_OFF", "CHARGING_TERMINATING"))

            if (is_connect or is_disconnect) and "tag:" in message:
                tag_key = ("socket " + socket, "start", "tag")
                taglog_key = ("socket " + socket, "start", "taglog")

                # Initialize if needed
                if taglog_key not in self.latest_tag:
                    self.latest_tag[taglog_key] = 0
                if tag_key not in self.latest_tag:
                    self.latest_tag[tag_key] = None

                # Only update if this is a newer log entry
                if line_id > self.latest_tag[taglog_key]:
                    self.latest_tag[taglog_key] = line_id

                    if is_connect:
                        # Extract tag value
                        tag_match = TAG_PATTERN.search(message)
                        if tag_match:
                            self.latest_tag[tag_key] = tag_match.group(1)
                    else:  # is_disconnect
                        self.latest_tag[tag_key] = "No Tag"

    async def _get_transaction(self) -> None:
        """Get transaction data."""
        _LOGGER.debug("[%s] Get Transaction", self.log_id)
        offset = self.transaction_offset
        transactionLoop = True
        counter = 0
        unknownLine = 0
        while transactionLoop:
            # Validate and cap offset to prevent unbounded values
            if not isinstance(offset, int) or offset < 0:
                offset = 0
            offset = min(offset, 100000)

            # Use urlencode for safe URL construction
            query = urlencode({OFFSET: offset})
            response = await self._get(
                url=self.__get_url(f"transactions?{query}"),
                json_decode=False,
            )
            # _LOGGER.debug(response)
            # split this text into lines with \n
            lines = str(response).splitlines()

            # if the lines are empty, break the loop
            if not lines or not response:
                transactionLoop = False
                break

            for line in lines:
                # _LOGGER.debug("Line: %s", line)
                if not line:
                    transactionLoop = False
                    break

                try:
                    if "version" in line:
                        # _LOGGER.debug("Version line" + line)
                        line = line.split(":2,", 2)[1]

                    splitline = line.split(" ")

                    tid_str = ""
                    if "txstart" in line:
                        # _LOGGER.debug("start line: " + line)
                        tid_str = line.split(":", 2)[0].split("_", 2)[0]

                        tid_str = splitline[0].split("_", 2)[0]
                        socket = splitline[3] + " " + splitline[4].split(",", 2)[0]

                        date = splitline[5] + " " + splitline[6]
                        kWh = splitline[7].split("kWh", 2)[0]
                        # tag = splitline[8]  # Unused

                        # 3: transaction id
                        # 9: 1
                        # 10: y

                        if self.latest_tag is None:
                            self.latest_tag = {}
                        # self.latest_tag[socket, "start", "tag"] = tag
                        self.latest_tag[socket, "start", "date"] = date
                        self.latest_tag[socket, "start", "kWh"] = kWh

                    elif "txstop" in line:
                        # _LOGGER.debug("stop line: " + line)

                        tid_str = splitline[0].split("_", 2)[0]
                        socket = splitline[3] + " " + splitline[4].split(",", 2)[0]

                        date = splitline[5] + " " + splitline[6]
                        kWh = splitline[7].split("kWh", 2)[0]
                        # tag = splitline[8]  # Unused

                        # 2: transaction id
                        # 9: y

                        if self.latest_tag is None:
                            self.latest_tag = {}
                        # self.latest_tag[socket, "stop", "tag"] = tag
                        self.latest_tag[socket, "stop", "date"] = date
                        self.latest_tag[socket, "stop", "kWh"] = kWh

                        # store the latest start kwh and date
                        for key in list(self.latest_tag):
                            if (
                                key[0] == socket
                                and key[1] == "start"
                                and key[2] == "kWh"
                            ):
                                self.latest_tag[socket, "last_start", "kWh"] = (
                                    self.latest_tag[socket, "start", "kWh"]
                                )
                            if (
                                key[0] == socket
                                and key[1] == "start"
                                and key[2] == "date"
                            ):
                                self.latest_tag[socket, "last_start", "date"] = (
                                    self.latest_tag[socket, "start", "date"]
                                )

                    elif "mv" in line:
                        # _LOGGER.debug("mv line: " + line)
                        tid_str = splitline[0].split("_", 2)[0]
                        socket = splitline[1] + " " + splitline[2].split(",", 2)[0]
                        date = splitline[3] + " " + splitline[4]
                        kWh = splitline[5]

                        if self.latest_tag is None:
                            self.latest_tag = {}
                        self.latest_tag[socket, "mv", "date"] = date
                        self.latest_tag[socket, "mv", "kWh"] = kWh

                        # _LOGGER.debug(self.latest_tag)

                    elif "dto" in line:
                        # get the value from begin till _dto
                        tid = int(splitline[0].split("_", 2)[0])
                        if tid > offset:
                            offset = tid
                            # Cap offset to prevent unbounded growth
                            offset = min(offset, 100000)
                            continue
                        offset = offset + 1
                        # Cap offset to prevent unbounded growth
                        offset = min(offset, 100000)
                        continue
                    elif "0_Empty" in line:
                        # break if the transaction is empty
                        transactionLoop = False
                        break
                    else:
                        _LOGGER.debug("[%s] Unknown line: %s", self.log_id, str(line))
                        offset = offset + 1
                        unknownLine += 1
                        if unknownLine > 2:
                            transactionLoop = False
                        continue
                except IndexError:
                    break

                # check if tid_str is integer
                try:
                    offset = int(tid_str)
                    if self.transaction_offset == offset:
                        counter += 1
                    else:
                        self.transaction_offset = offset
                        counter = 0

                    if counter == 2:
                        _LOGGER.debug("[%s] Transaction tags: %s", self.log_id, self._sanitize_tag_for_logging())
                        transactionLoop = False
                        break
                except ValueError:
                    continue

                # check if last line is reached
                if line == lines[-1]:
                    break

    async def async_request(
        self, method: str, cmd: str, json_data: dict[str, Any] | None = None
    ) -> Any | None:
        """Send a request to the API."""
        try:
            return await self.request(method, cmd, json_data)
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("[%s] Unexpected error async request: %s", self.log_id, self._sanitize_exception(e))
            return None

    async def request(self, method: str, cmd: str, json_data: dict[str, Any] | None = None) -> Any:
        """Send a request to the API."""
        if method == METHOD_GET:
            response = await self._get(url=self.__get_url(cmd))
        else:  # METHOD_POST
            response = await self._post(cmd=cmd, payload=json_data)

        _LOGGER.debug("[%s] Request response %s", self.log_id, str(response))
        return response

    async def set_value(self, api_param: str, value: Any) -> None:
        """Set a value on the API.

        Note: This queues the value and triggers an immediate coordinator update.
        Check logs for "Failed to update" warnings if updates are not applied.
        """
        # Use lock to prevent race conditions when modifying update_values
        async with self._update_values_lock:
            # check if the api_param is already in the update_values, update the value
            if api_param in self.update_values:
                self.update_values[api_param]["value"] = value
                _LOGGER.debug(
                    "[%s] Updated queued value for %s to %s (triggering immediate update)",
                    self.log_id,
                    api_param,
                    value,
                )
            else:
                self.update_values[api_param] = {"api_param": api_param, "value": value}
                _LOGGER.debug(
                    "[%s] Queued value update for %s to %s (triggering immediate update)",
                    self.log_id,
                    api_param,
                    value,
                )

        # Trigger immediate coordinator update to process the queued value
        if self._value_updated_callback:
            _LOGGER.debug("[%s] Triggering immediate coordinator update for queued value", self.log_id)
            # Schedule callback as a task to avoid blocking
            task = asyncio.create_task(self._value_updated_callback())
            # Add done callback to log any errors
            task.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)

    async def get_value(self, api_param: str) -> None:
        """Get a value from the API."""
        return await self._get_value(api_param)

    async def set_current_limit(self, limit: int) -> None:
        """Set the current limit."""
        _LOGGER.debug("[%s] Set current limit %sA", self.log_id, str(limit))
        if limit > 32 or limit < 1:
            return
        await self.set_value("2129_0", limit)

    async def set_rfid_auth_mode(self, enabled: bool) -> None:
        """Set the RFID Auth Mode."""
        _LOGGER.debug("[%s] Set RFID Auth Mode %s", self.log_id, str(enabled))

        value = 2 if enabled else 0
        await self.set_value("2126_0", value)

    async def set_current_phase(self, phase: str) -> None:
        """Set the current phase."""
        _LOGGER.debug("[%s] Set current phase %s", self.log_id, str(phase))
        if phase not in ("L1", "L2", "L3"):
            return
        await self.set_value("2069_0", phase)

    async def set_phase_switching(self, enabled: bool) -> None:
        """Set the phase switching."""
        _LOGGER.debug("[%s] Set Phase Switching %s", self.log_id, str(enabled))

        value = 1 if enabled else 0
        await self.set_value("2185_0", value)

    async def set_green_share(self, value: int) -> None:
        """Set the green share."""
        _LOGGER.debug("[%s] Set green share value %s", self.log_id, str(value))
        if value < 0 or value > 100:
            return
        await self.set_value("3280_2", value)

    async def set_comfort_power(self, value: int) -> None:
        """Set the comfort power."""
        _LOGGER.debug("[%s] Set Comfort Level %sW", self.log_id, str(value))
        if value < 1400 or value > 5000:
            return
        await self.set_value("3280_3", value)

    def __get_url(self, action) -> str:
        """Get the URL for the API."""
        return f"https://{self.host}/api/{action}"


class AlfenDeviceInfo:
    """Representation of a Alfen device info."""

    def __init__(self, response: dict[str, Any]) -> None:
        """Initialize the Alfen device info."""
        self.identity = response["Identity"]
        self.firmware_version = response["FWVersion"]
        self.model_id = response["Model"]

        self.model = ALFEN_PRODUCT_MAP.get(self.model_id, self.model_id)
        self.object_id = response["ObjectId"]
        self.type = response["Type"]
