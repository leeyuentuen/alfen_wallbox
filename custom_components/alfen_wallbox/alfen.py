"""Alfen Wallbox API."""

import asyncio
from collections import deque
import datetime
import json
import logging
import re
from ssl import SSLContext

from aiohttp import ClientResponse, ClientSession

from .const import (
    ALFEN_PRODUCT_MAP,
    CAT,
    CAT_LOGS,
    CAT_TRANSACTIONS,
    CATEGORIES,
    CMD,
    COMMAND_CLEAR_TRANSACTIONS,
    COMMAND_REBOOT,
    DEFAULT_TIMEOUT,
    DISPLAY_NAME_VALUE,
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

# Regex pattern for parsing log entries
# Format: <line_id>_<date>:<time>:<type>:<filename>:<line>:<message>
LOG_PATTERN = re.compile(r'^(\d+)_(.+?):(.+?):(.+?):(.+?):(.+?):(.+)$')
# Pattern for extracting socket number from log messages
SOCKET_PATTERN = re.compile(r'Socket #(\d+)')
# Pattern for extracting tag from log messages
TAG_PATTERN = re.compile(r'tag:\s*(\S+)')


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
    ) -> None:
        """Init."""

        self.host = host
        self.name = name
        self._session = session
        self.username = username
        self.category_options = category_options
        self.info = None
        self.id = None
        if self.username is None:
            self.username = "admin"
        self.password = password
        self.properties = []
        self._session.verify = False
        self.keep_logout = False
        self.max_allowed_phases = 1
        self.latest_tag = None
        self.transaction_offset = 0
        self.transaction_counter = 0
        self.ssl = ssl
        self.static_properties = []
        self.get_static_properties = True
        self.logged_in = False
        self.last_updated = None
        # Use deque with maxlen to limit memory usage
        self.latest_logs = deque(maxlen=500)
        # prevent multiple call to wallbox
        self._lock = asyncio.Lock()
        self.update_values = {}
        self._updating_lock = asyncio.Lock()
        self._update_values_lock = asyncio.Lock()

    async def init(self) -> bool:
        """Initialize the Alfen API."""
        result = await self.get_info()
        self.id = f"alfen_{self.name}"
        if self.name is None:
            self.name = f"{self.info.identity} ({self.host})"

        return result

    def get_number_of_sockets(self) -> int | None:
        """Get number of sockets from the properties."""
        sockets = 1
        if "205E_0" in self.properties:
            sockets = self.properties["205E_0"][VALUE]
        return sockets

    def get_licenses(self) -> list | None:
        """Get licenses from the properties."""
        licenses = []
        if "21A2_0" in self.properties:
            prop = self.properties["21A2_0"]
            for key, value in LICENSES.items():
                if int(prop[VALUE]) & int(value):
                    licenses.append(key)
        return licenses

    async def get_info(self) -> bool:
        """Get info from the API."""
        response = await self._session.get(url=self.__get_url(INFO), ssl=self.ssl)
        _LOGGER.debug("Response %s", str(response))

        if response.status == 200:
            resp = await response.json(content_type=None)
            self.info = AlfenDeviceInfo(resp)

            return True

        _LOGGER.debug("Info API not available, use generic info")
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
    def device_info(self) -> dict:
        """Return a device description for device registry."""
        return {
            "identifiers": {(DOMAIN, self.name)},
            "manufacturer": "Alfen",
            "model": self.info.model,
            "name": self.name,
            "sw_version": self.info.firmware_version,
        }

    async def async_update(self) -> bool:
        """Update the device properties."""
        if self.keep_logout:
            return True

        update_start = datetime.datetime.now()

        # Use a proper lock to prevent concurrent updates
        async with self._updating_lock:
            # we update first the self.update_values
            # copy the values to other dict
            # we need to copy the values to avoid the dict changed size error
            async with self._update_values_lock:
                values = self.update_values.copy()

            # Process pending value updates
            if values:
                _LOGGER.debug("Processing %d pending value updates", len(values))

            for value in values.values():
                response = await self._update_value(value["api_param"], value["value"])

                if response:
                    # we expect that the value is updated so we are just update the value in the properties
                    if value["api_param"] in self.properties:
                        prop = self.properties[value["api_param"]]
                        _LOGGER.debug(
                            "Set %s value %s",
                            str(value["api_param"]),
                            str(value["value"]),
                        )
                        prop[VALUE] = value["value"]
                        self.properties[value["api_param"]] = prop
                    # remove the update from the list
                    async with self._update_values_lock:
                        if value["api_param"] in self.update_values:
                            del self.update_values[value["api_param"]]
                else:
                    # Log failure but don't remove from update_values so it will retry
                    _LOGGER.warning(
                        "Failed to update %s to %s - will retry on next update cycle",
                        value["api_param"],
                        value["value"],
                    )

            self.last_updated = datetime.datetime.now()

            # Fetch static properties only once
            if self.get_static_properties:
                self.static_properties = []
                static_cats = [cat for cat in CATEGORIES if cat not in (CAT_TRANSACTIONS, CAT_LOGS) and cat not in self.category_options]
                for cat in static_cats:
                    props = await self._get_all_properties_value(cat)
                    self.static_properties.extend(props)
                self.get_static_properties = False

            # Fetch dynamic properties
            dynamic_properties = []
            for cat in self.category_options:
                if cat not in (CAT_TRANSACTIONS, CAT_LOGS):
                    props = await self._get_all_properties_value(cat)
                    dynamic_properties.extend(props)

            # Build properties dict using comprehension (more efficient)
            # Static properties are loaded once, dynamic properties update each cycle
            self.properties = {prop[ID]: prop for prop in self.static_properties}
            self.properties.update({prop[ID]: prop for prop in dynamic_properties})

            if CAT_LOGS in self.category_options:
                await self._get_log()

            # Only fetch transactions every 60th update cycle (reduces API load)
            # With 5s scan interval, this means every ~5 minutes
            if CAT_TRANSACTIONS in self.category_options:
                self.transaction_counter = (self.transaction_counter + 1) % 60
                if self.transaction_counter == 0:
                    await self._get_transaction()

            # Log total update time for monitoring
            update_duration = (datetime.datetime.now() - update_start).total_seconds()
            if update_duration > 2:
                _LOGGER.info("Update cycle completed in %.2fs", update_duration)
            else:
                _LOGGER.debug("Update cycle completed in %.2fs", update_duration)

            return True

    async def _post(
        self, cmd, payload=None, allowed_login=True
    ) -> ClientResponse | None:
        """Send a POST request to the API."""
        if self.keep_logout:
            return None

        needs_auth = False
        async with self._lock:
            try:
                _LOGGER.debug("Send Post Request")
                async with self._session.post(
                    url=self.__get_url(cmd),
                    json=payload,
                    headers=POST_HEADER_JSON,
                    timeout=DEFAULT_TIMEOUT,
                    ssl=self.ssl,
                ) as response:
                    if response.status == 401 and allowed_login:
                        self.logged_in = False
                        _LOGGER.debug("POST with login - will retry after lock release")
                        needs_auth = True
                    else:
                        response.raise_for_status()
                        # Process response inside context manager
                        try:
                            result = await response.json(content_type=None)
                            return result
                        except json.JSONDecodeError as e:
                            # skip tailing comma error from alfen
                            if e.msg == "trailing comma is not allowed":
                                _LOGGER.debug("trailing comma is not allowed")
                                return None
                            _LOGGER.error("JSONDecodeError error on POST %s", str(e))
                            raise
            except TimeoutError:
                _LOGGER.warning("Timeout on POST")
                return None
            except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
                if not allowed_login:
                    _LOGGER.error("Unexpected error on POST %s", str(e))
                return None

        # After lock is released, handle reauth if needed
        if needs_auth:
            await self.login()
            return await self._post(cmd, payload, False)

    async def _get(
        self, url, allowed_login=True, json_decode=True
    ) -> ClientResponse | None:
        """Send a GET request to the API."""
        if self.keep_logout:
            return None

        needs_auth = False
        async with self._lock:
            try:
                async with self._session.get(
                    url, timeout=DEFAULT_TIMEOUT, ssl=self.ssl
                ) as response:
                    if response.status == 401 and allowed_login:
                        self.logged_in = False
                        _LOGGER.debug("GET with login - will retry after lock release")
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
                _LOGGER.warning("Timeout on GET")
                return None
            except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
                if not allowed_login:
                    _LOGGER.error("Unexpected error on GET %s", str(e))
                return None

        # After lock is released, handle reauth if needed
        if needs_auth:
            await self.login()
            return await self._get(url=url, allowed_login=False, json_decode=json_decode)

    async def login(self):
        """Login to the API."""
        self.keep_logout = False

        try:
            response = await self._post(
                cmd=LOGIN,
                payload={
                    PARAM_USERNAME: self.username,
                    PARAM_PASSWORD: self.password,
                    PARAM_DISPLAY_NAME: DISPLAY_NAME_VALUE,
                },
            )
            self.logged_in = True
            self.last_updated = datetime.datetime.now()

            _LOGGER.debug("Login response %s", response)
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error("Unexpected error on LOGIN %s", str(e))
            return

    async def logout(self):
        """Logout from the API."""
        self.keep_logout = True

        try:
            response = await self._post(cmd=LOGOUT, allowed_login=False)
            self.logged_in = False
            self.last_updated = datetime.datetime.now()

            _LOGGER.debug("Logout response %s", str(response))
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error("Unexpected error on LOGOUT %s", str(e))
            return

    async def _update_value(
        self, api_param, value, allowed_login=True
    ) -> ClientResponse | None:
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
                    timeout=DEFAULT_TIMEOUT,
                    ssl=self.ssl,
                ) as response:
                    if response.status == 401 and allowed_login:
                        self.logged_in = False
                        _LOGGER.debug("POST(Update) with login - will retry after lock release")
                        needs_auth = True
                    else:
                        response.raise_for_status()
                        # Return True to indicate success
                        return True
            except TimeoutError:
                _LOGGER.warning("Timeout on UPDATE VALUE")
                return None
            except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
                if not allowed_login:
                    _LOGGER.error("Unexpected error on UPDATE VALUE %s", str(e))
                return None

        # After lock is released, handle reauth if needed
        if needs_auth:
            await self.login()
            return await self._update_value(api_param, value, False)

    async def _get_value(self, api_param):
        """Get a value from the API."""
        cmd = f"{PROP}?{ID}={api_param}"
        response = await self._get(url=self.__get_url(cmd))
        # _LOGGER.debug("Status Response %s: %s", cmd, str(response))

        if response is not None:
            if self.properties is None:
                self.properties = {}
            for resp in response[PROPERTIES]:
                if resp[ID] in self.properties:
                    self.properties[resp[ID]] = resp

    async def _get_all_properties_value(self, category: str) -> list:
        """Get all properties from the API."""
        properties = []
        tx_start = datetime.datetime.now()
        nextRequest = True
        offset = 0
        attempt = 0

        while nextRequest:
            attempt += 1
            cmd = f"{PROP}?{CAT}={category}&{OFFSET}={offset}"
            response = await self._get(url=self.__get_url(cmd))

            if response is not None:
                attempt = 0
                # if response is a string, convert it to json
                if isinstance(response, str):
                    try:
                        response = json.loads(response)
                    except json.JSONDecodeError:
                        _LOGGER.error("Failed to parse JSON response for category %s", category)
                        break

                # Validate response structure
                if PROPERTIES not in response or TOTAL not in response:
                    _LOGGER.warning("Invalid response structure for category %s", category)
                    break

                # merge the properties with response properties
                properties.extend(response[PROPERTIES])
                nextRequest = response[TOTAL] > (offset + len(response[PROPERTIES]))
                offset += len(response[PROPERTIES])
            elif attempt >= 3:
                # This only possible in case of series of timeouts or unknown exceptions in self._get()
                # It's better to break completely, otherwise we can provide partial data in self.properties.
                _LOGGER.warning("Failed to fetch %s after %d attempts, returning partial data", category, attempt)
                break
            else:
                # Brief backoff before retry
                await asyncio.sleep(2)

        runtime = datetime.datetime.now() - tx_start
        if properties:
            _LOGGER.debug("Fetched %d properties from %s in %.2fs", len(properties), category, runtime.total_seconds())
        else:
            _LOGGER.warning("No properties fetched from %s (took %.2fs)", category, runtime.total_seconds())

        return properties

    async def reboot_wallbox(self):
        """Reboot the wallbox."""
        response = await self._post(cmd=CMD, payload={PARAM_COMMAND: COMMAND_REBOOT})
        _LOGGER.debug("Reboot response %s", str(response))

    async def clear_transactions(self):
        """Clear the transactions."""
        response = await self._post(
            cmd=CMD, payload={PARAM_COMMAND: COMMAND_CLEAR_TRANSACTIONS}
        )
        _LOGGER.debug("Clear Transactions response %s", str(response))

    async def send_command(self, command):
        """Run a command."""
        response = await self._post(cmd=CMD, payload=command)
        _LOGGER.debug("Run Command response %s", str(response))

    async def _fetch_log(self, log_offset) -> str | None:
        """Fetch the log."""
        response = await self._get(
            url=self.__get_url("log?offset=" + str(log_offset)),
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

    async def _get_log(self):
        """Get the log."""
        log_offset = 0
        # Clear logs only on first fetch, deque will auto-manage size
        temp_logs = deque(maxlen=500)

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

    async def _get_transaction(self):
        _LOGGER.debug("Get Transaction")
        offset = self.transaction_offset
        transactionLoop = True
        counter = 0
        unknownLine = 0
        while transactionLoop:
            response = await self._get(
                url=self.__get_url("transactions?offset=" + str(offset)),
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
                if line is None:
                    transactionLoop = False
                    break

                try:
                    if "version" in line:
                        # _LOGGER.debug("Version line" + line)
                        line = line.split(":2,", 2)[1]

                    splitline = line.split(" ")

                    if "txstart" in line:
                        # _LOGGER.debug("start line: " + line)
                        tid = line.split(":", 2)[0].split("_", 2)[0]

                        tid = splitline[0].split("_", 2)[0]
                        socket = splitline[3] + " " + splitline[4].split(",", 2)[0]

                        date = splitline[5] + " " + splitline[6]
                        kWh = splitline[7].split("kWh", 2)[0]
                        tag = splitline[8]

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

                        tid = splitline[0].split("_", 2)[0]
                        socket = splitline[3] + " " + splitline[4].split(",", 2)[0]

                        date = splitline[5] + " " + splitline[6]
                        kWh = splitline[7].split("kWh", 2)[0]
                        tag = splitline[8]

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
                        tid = splitline[0].split("_", 2)[0]
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
                            continue
                        offset = offset + 1
                        continue
                    elif "0_Empty" in line:
                        # break if the transaction is empty
                        transactionLoop = False
                        break
                    else:
                        _LOGGER.debug("Unknown line: %s", str(line))
                        offset = offset + 1
                        unknownLine += 1
                        if unknownLine > 2:
                            transactionLoop = False
                        continue
                except IndexError:
                    break

                # check if tid is integer
                try:
                    offset = int(tid)
                    if self.transaction_offset == offset:
                        counter += 1
                    else:
                        self.transaction_offset = offset
                        counter = 0

                    if counter == 2:
                        _LOGGER.debug(self.latest_tag)
                        transactionLoop = False
                        break
                except ValueError:
                    continue

                # check if last line is reached
                if line == lines[-1]:
                    break

    async def async_request(
        self, method: str, cmd: str, json_data=None
    ) -> ClientResponse | None:
        """Send a request to the API."""
        try:
            return await self.request(method, cmd, json_data)
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            _LOGGER.error("Unexpected error async request %s", str(e))
            return None

    async def request(self, method: str, cmd: str, json_data=None) -> ClientResponse:
        """Send a request to the API."""
        if method == METHOD_GET:
            response = await self._get(url=self.__get_url(cmd))
        else:  # METHOD_POST
            response = await self._post(cmd=cmd, payload=json_data)

        _LOGGER.debug("Request response %s", str(response))
        return response

    async def set_value(self, api_param, value):
        """Set a value on the API.

        Note: This queues the value for update on the next coordinator cycle.
        The value is not sent immediately. Check logs for "Failed to update" warnings
        if updates are not applied.
        """
        # Use lock to prevent race conditions when modifying update_values
        async with self._update_values_lock:
            # check if the api_param is already in the update_values, update the value
            if api_param in self.update_values:
                self.update_values[api_param]["value"] = value
                _LOGGER.debug(
                    "Updated queued value for %s to %s (will be sent on next update)",
                    api_param,
                    value,
                )
                return
            self.update_values[api_param] = {"api_param": api_param, "value": value}
            _LOGGER.debug(
                "Queued value update for %s to %s (will be sent on next update)",
                api_param,
                value,
            )
        # Value will be sent during next async_update() call by coordinator

    async def get_value(self, api_param):
        """Get a value from the API."""
        return await self._get_value(api_param)

    async def set_current_limit(self, limit) -> None:
        """Set the current limit."""
        _LOGGER.debug("Set current limit %sA", str(limit))
        if limit > 32 or limit < 1:
            return
        await self.set_value("2129_0", limit)

    async def set_rfid_auth_mode(self, enabled):
        """Set the RFID Auth Mode."""
        _LOGGER.debug("Set RFID Auth Mode %s", str(enabled))

        value = 0
        if enabled:
            value = 2

        await self.set_value("2126_0", value)

    async def set_current_phase(self, phase) -> None:
        """Set the current phase."""
        _LOGGER.debug("Set current phase %s", str(phase))
        if phase not in ("L1", "L2", "L3"):
            return
        await self.set_value("2069_0", phase)

    async def set_phase_switching(self, enabled):
        """Set the phase switching."""
        _LOGGER.debug("Set Phase Switching %s", str(enabled))

        value = 0
        if enabled:
            value = 1
        await self.set_value("2185_0", value)

    async def set_green_share(self, value) -> None:
        """Set the green share."""
        _LOGGER.debug("Set green share value %s", str(value))
        if value < 0 or value > 100:
            return
        await self.set_value("3280_2", value)

    async def set_comfort_power(self, value) -> None:
        """Set the comfort power."""
        _LOGGER.debug("Set Comfort Level %sW", str(value))
        if value < 1400 or value > 5000:
            return
        await self.set_value("3280_3", value)

    def __get_url(self, action) -> str:
        """Get the URL for the API."""
        return f"https://{self.host}/api/{action}"


class AlfenDeviceInfo:
    """Representation of a Alfen device info."""

    def __init__(self, response) -> None:
        """Initialize the Alfen device info."""
        self.identity = response["Identity"]
        self.firmware_version = response["FWVersion"]
        self.model_id = response["Model"]

        self.model = ALFEN_PRODUCT_MAP.get(self.model_id, self.model_id)
        self.object_id = response["ObjectId"]
        self.type = response["Type"]
