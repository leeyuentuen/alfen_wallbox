"""Alfen Wallbox API."""

import datetime
import json
import logging
from ssl import SSLContext

from aiohttp import ClientResponse, ClientSession

from .const import (
    ALFEN_PRODUCT_MAP,
    CAT,
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
        self.logs = []
        self.latest_log_id = None

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
        for prop in self.properties:
            if prop[ID] == "205E_0":
                sockets = int(prop[VALUE])
                break
        return sockets

    def get_licenses(self) -> list | None:
        """Get licenses from the properties."""
        licenses = []
        for prop in self.properties:
            if prop[ID] == "21A2_0":
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

        self.last_updated = datetime.datetime.now()
        dynamic_properties = []
        self.properties = []
        if self.get_static_properties:
            self.static_properties = []

        for cat in CATEGORIES:
            if cat == CAT_TRANSACTIONS:
                continue
            if cat in self.category_options:
                dynamic_properties = (
                    dynamic_properties + await self._get_all_properties_value(cat)
                )
            elif self.get_static_properties:
                self.static_properties = (
                    self.static_properties + await self._get_all_properties_value(cat)
                )
        self.properties = self.static_properties + dynamic_properties
        self.get_static_properties = False

        if CAT_TRANSACTIONS in self.category_options:
            if self.transaction_counter == 0:
                await self._get_transaction()
            self.transaction_counter += 1

            if self.transaction_counter > 60:
                self.transaction_counter = 0
        await self._get_log()
        return True

    async def _post(
        self, cmd, payload=None, allowed_login=True
    ) -> ClientResponse | None:
        """Send a POST request to the API."""
        if self.keep_logout:
            return None

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
                    _LOGGER.debug("POST with login")
                    await self.login()
                    return await self._post(cmd, payload, False)
                response.raise_for_status()
                return response
        except json.JSONDecodeError as e:
            # skip tailing comma error from alfen
            _LOGGER.debug("trailing comma is not allowed")
            if e.msg == "trailing comma is not allowed":
                return None

            _LOGGER.error("JSONDecodeError error on POST %s", str(e))
        except TimeoutError:
            _LOGGER.warning("Timeout on POST")
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            if not allowed_login:
                _LOGGER.error("Unexpected error on POST %s", str(e))

        return None

    async def _get(
        self, url, allowed_login=True, json_decode=True
    ) -> ClientResponse | None:
        """Send a GET request to the API."""
        if self.keep_logout:
            return None

        try:
            async with self._session.get(
                url, timeout=DEFAULT_TIMEOUT, ssl=self.ssl
            ) as response:
                if response.status == 401 and allowed_login:
                    self.logged_in = False
                    _LOGGER.debug("GET with login")
                    await self.login()
                    return await self._get(url, False)

                response.raise_for_status()
                if json_decode:
                    _resp = await response.json(content_type=None)
                else:
                    _resp = await response.text()
                return _resp
        except TimeoutError:
            _LOGGER.warning("Timeout on GET")
            return None
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            if not allowed_login:
                _LOGGER.error("Unexpected error on GET %s", str(e))
            return None

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
                    _LOGGER.debug("POST(Update) with login")
                    await self.login()
                    return await self._update_value(api_param, value, False)
                response.raise_for_status()
                return response
        except Exception as e:  # pylint: disable=broad-except  # noqa: BLE001
            if not allowed_login:
                _LOGGER.error("Unexpected error on UPDATE VALUE %s", str(e))
            return None

    async def _get_value(self, api_param):
        """Get a value from the API."""
        cmd = f"{PROP}?{ID}={api_param}"
        response = await self._get(url=self.__get_url(cmd))
        _LOGGER.debug("Status Response %s: %s", cmd, str(response))

        if response is not None:
            if self.properties is None:
                self.properties = []
            for resp in response[PROPERTIES]:
                for prop in self.properties:
                    if prop[ID] == resp[ID]:
                        prop[VALUE] = resp[VALUE]
                        break

    async def _get_all_properties_value(self, category: str) -> list:
        """Get all properties from the API."""
        _LOGGER.debug("Get properties")

        properties = []
        tx_start = datetime.datetime.now()
        nextRequest = True
        offset = 0
        attempt = 0

        while nextRequest:
            attempt += 1
            cmd = f"{PROP}?{CAT}={category}&{OFFSET}={offset}"
            response = await self._get(url=self.__get_url(cmd))
            _LOGGER.debug("Status Response %s: %s", cmd, str(response))

            if response is not None:
                attempt = 0
                properties += response[PROPERTIES]
                nextRequest = response[TOTAL] > (offset + len(response[PROPERTIES]))
                offset += len(response[PROPERTIES])
            elif attempt >= 3:
                # This only possible in case of series of timeouts or unknown exceptions in self._get()
                # It's better to break completely, otherwise we can provide partial data in self.properties.
                _LOGGER.debug("Returning earlier after %s attempts", str(attempt))
                self.properties = []
                break

        _LOGGER.debug("Properties %s", str(properties))
        runtime = datetime.datetime.now() - tx_start
        _LOGGER.info("Called %s in %.2f seconds", category, runtime.total_seconds())
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

    async def _get_log(self):
        """Get the log."""
        log_offset = 0
        response = await self._get(
            url=self.__get_url("log?offset=" + str(log_offset)),
            json_decode=False,
        )
        index = response.find("_")
        if index == -1 or index >= 20:
            return
        log_id = response[:index]
        if self.latest_log_id is not None:
            if self.latest_log_id >= log_id:
                return
        else:
            self.latest_log_id = log_id

        while response:
            # _LOGGER.debug(response)
            self.logs.append(response)
            log_offset += 1
            response = await self._get(
                url=self.__get_url("log?offset=" + str(log_offset)),
                json_decode=False,
            )
            if log_offset > 50:
                break
        # _LOGGER.debug(self.log_offset)
        # reverse the logs order
        self.logs.reverse()
        for log in self.logs:
            # split on \n
            lines = log.splitlines()
            for line in lines:
                # get the index of _
                index = line.find("_")
                if index == -1 or index >= 20:
                    continue
                id = line[:index]
                # substring on : so we get the date and time
                line = line[index + 1 :]
                index = line.split(":")
                # if we have less then 7 then we skip it
                if len(index) < 7:
                    continue
                # get the date and time
                date = index[0] + ":" + index[1] + ":" + index[2]
                # type of log
                type = index[3]
                # filename
                filename = index[4]
                # line number
                line = index[5]
                # message
                message = index[6]
                # show the rest of all the index after 5
                for i in range(7, len(index)):
                    message += ":" + index[i]

                # if contains 'EV_CONNECTED_AUTHORIZED' then we have a tag
                # Socket #1: main state: EV_CONNECTED_AUTHORIZED, CP: 8.8/8.9, tag: xxxxxxx
                if "EV_CONNECTED_AUTHORIZED" in message and "tag:" in message:
                    # check which socket we have
                    socket = ""
                    if "Socket #1" in message:
                        socket = "1"
                    elif "Socket #2" in message:
                        socket = "2"
                    self.latest_tag["socket " + socket, "start", "tag"] = message.split(
                        "tag: ", 2
                    )[1]
                    # _LOGGER.warning(self.latest_tag)
                # _LOGGER.debug(message)

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
                _LOGGER.debug("Line: %s", line)
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
                        self.latest_tag[socket, "start", "tag"] = tag
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
                        self.latest_tag[socket, "stop", "tag"] = tag
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
        """Set a value on the API."""
        response = await self._update_value(api_param, value)
        if response:
            # we expect that the value is updated so we are just update the value in the properties
            for index, prop in enumerate(self.properties):
                if prop[ID] == api_param:
                    _LOGGER.debug("Set %s value %s", str(api_param), str(value))
                    prop[VALUE] = value
                    self.properties[index] = prop
                    break

    async def get_value(self, api_param):
        """Get a value from the API."""
        return await self._get_value(api_param)

    async def set_current_limit(self, limit) -> None:
        """Set the current limit."""
        _LOGGER.debug("Set current limit %sA", str(limit))
        if limit > 32 | limit < 1:
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
        if value < 0 | value > 100:
            return
        await self.set_value("3280_2", value)

    async def set_comfort_power(self, value) -> None:
        """Set the comfort power."""
        _LOGGER.debug("Set Comfort Level %sW", str(value))
        if value < 1400 | value > 5000:
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
