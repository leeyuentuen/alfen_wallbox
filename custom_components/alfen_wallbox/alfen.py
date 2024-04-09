"""Alfen Wallbox API."""
import json
import logging
import ssl

from aiohttp import ClientResponse
from urllib3 import disable_warnings

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    ALFEN_PRODUCT_MAP,
    CAT,
    CAT_COMM,
    CAT_DISPLAY,
    CAT_GENERIC,
    CAT_GENERIC2,
    CAT_MBUS_TCP,
    CAT_METER1,
    CAT_METER2,
    CAT_METER4,
    CAT_OCPP,
    CAT_STATES,
    CAT_TEMP,
    CMD,
    DISPLAY_NAME_VALUE,
    DOMAIN,
    ID,
    INFO,
    LICENSES,
    LOGIN,
    LOGOUT,
    METHOD_GET,
    METHOD_POST,
    OFFSET,
    PARAM_COMMAND,
    PARAM_DISPLAY_NAME,
    PARAM_PASSWORD,
    PARAM_USERNAME,
    PROP,
    PROPERTIES,
    TIMEOUT,
    TOTAL,
    VALUE,
)

POST_HEADER_JSON = {"Content-Type": "application/json"}

_LOGGER = logging.getLogger(__name__)


class AlfenDevice:
    def __init__(self,
                 hass: HomeAssistant,
                 host: str,
                 name: str,
                 username: str,
                 password: str) -> None:

        self.host = host
        self.name = name
        self._status = None
        self._session = async_get_clientsession(hass, verify_ssl=False)
        self.username = username
        self.info = None
        self.id = None
        if self.username is None:
            self.username = "admin"
        self.password = password
        self.properties = []
        self.licenses = []
        self._session.verify = False
        self.keepLogout = False
        self.wait = False
        self.updating = False
        self.number_socket = 1
        self._hass = hass
        disable_warnings()

        # Default ciphers needed as of python 3.10
        context = ssl.create_default_context()
        context.set_ciphers("DEFAULT")
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
        self.ssl = context

    async def init(self):
        """Initialize the Alfen API."""
        await self.get_info()
        self.id = f"alfen_{self.name}"
        if self.name is None:
            self.name = f"{self.info.identity} ({self.host})"

    def get_number_of_socket(self):
        """Get number of socket from the properties."""
        for prop in self.properties:
            if prop[ID] == '205E_0':
                self.number_socket = int(prop[VALUE])
                break

    def get_licenses(self):
        """Get licenses from the properties."""
        for prop in self.properties:
            if prop[ID] == '21A2_0':
                for key, value in LICENSES.items():
                    if int(prop[VALUE]) & int(value):
                        self.licenses.append(key)
                break

    async def get_info(self):
        """Get info from the API."""
        response = await self._session.get(
            url=self.__get_url(INFO), ssl=self.ssl
        )
        _LOGGER.debug(f"Response {response}")
        if response.status != 200:
            _LOGGER.debug("Info API not available, use generic info")

            generic_info = {
                "Identity": self.host,
                "FWVersion": "?",
                "Model": "Generic Alfen Wallbox",
                "ObjectId": "?",
                "Type": "?",
            }
            self.info = AlfenDeviceInfo(generic_info)
        else:
            resp = await response.json(content_type=None)
            self.info = AlfenDeviceInfo(resp)

    @property
    def status(self) -> str:
        """Return the status of the device."""
        return self._status

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

    async def async_update(self):
        """Update the device properties."""
        if not self.keepLogout and not self.wait and not self.updating:
            self.updating = True
            await self._get_all_properties_value()
            self.updating = False

    async def _post(self, cmd, payload=None, allowed_login=True) -> ClientResponse | None:
        """Send a POST request to the API."""
        try:
            self.wait = True
            _LOGGER.debug("Send Post Request")
            async with self._session.post(
                    url=self.__get_url(cmd),
                    json=payload,
                    headers=POST_HEADER_JSON,
                    timeout=TIMEOUT,
                    ssl=self.ssl) as response:
                if response.status == 401 and allowed_login:
                    _LOGGER.debug("POST with login")
                    await self.login()
                    return await self._post(cmd, payload, False)
                self.wait = False
                return response
        except json.JSONDecodeError as e:
            # skip tailing comma error from alfen
            _LOGGER.debug('trailing comma is not allowed')
            if e.msg == "trailing comma is not allowed":
                self.wait = False
                return None

            _LOGGER.error("JSONDecodeError error on POST %s", str(e))
        except TimeoutError as e:
            _LOGGER.warning("Timeout on POST")
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on POST %s", str(e))
        self.wait = False
        return None

    async def _get(self, url, allowed_login=True) -> ClientResponse | None:
        """Send a GET request to the API."""
        try:
            async with self._session.get(url, timeout=TIMEOUT, ssl=self.ssl) as response:
                if response.status == 401 and allowed_login:
                    _LOGGER.debug("GET with login")
                    await self.login()
                    return await self._get(url, False)
                _resp = await response.json(content_type=None)
                return _resp
        except TimeoutError as e:
            _LOGGER.warning("Timeout on GET")
            return None
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on GET %s", str(e))
            return None

    async def login(self):
        """Login to the API."""
        try:
            response = await self._post(cmd=LOGIN, payload={
                PARAM_USERNAME: self.username, PARAM_PASSWORD: self.password, PARAM_DISPLAY_NAME: DISPLAY_NAME_VALUE})
            _LOGGER.debug(f"Login response {response}")
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on LOGIN %s", str(e))
            return None

    async def logout(self):
        """Logout from the API."""
        try:
            response = await self._post(cmd=LOGOUT)
            _LOGGER.debug(f"Logout response {response}")
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on LOGOUT %s", str(e))
            return None

    async def _update_value(self, api_param, value, allowed_login=True) -> ClientResponse | None:
        """Update a value on the API."""
        try:
            self.wait = True
            async with self._session.post(
                    url=self.__get_url(PROP),
                    json={api_param: {ID: api_param, VALUE: str(value)}},
                    headers=POST_HEADER_JSON,
                    timeout=TIMEOUT,
                    ssl=self.ssl) as response:
                if response.status == 401 and allowed_login:
                    _LOGGER.debug("POST(Update) with login")
                    await self.login()
                    return await self._update_value(api_param, value, False)
                self.wait = False
                return response
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on UPDATE VALUE %s", str(e))
            self.wait = False
            return None

    async def _get_value(self, api_param):
        """Get a value from the API."""
        cmd = f"{PROP}?{ID}={api_param}"
        response = await self._get(url=self.__get_url(cmd))
        _LOGGER.debug(f"Status Response {cmd}: {response}")

        if response is not None:
            if self.properties is None:
                self.properties = []
            for resp in response[PROPERTIES]:
                for prop in self.properties:
                    if prop[ID] == resp[ID]:
                        prop[VALUE] = resp[VALUE]
                        break

    async def _get_all_properties_value(self):
        """Get all properties from the API."""
        _LOGGER.debug(f"Get properties")
        properties = []
        for cat in (CAT_GENERIC, CAT_GENERIC2, CAT_METER1, CAT_STATES, CAT_TEMP, CAT_OCPP, CAT_METER4, CAT_MBUS_TCP, CAT_COMM, CAT_DISPLAY, CAT_METER2):
            nextRequest = True
            offset = 0
            while (nextRequest):
                cmd = f"{PROP}?{CAT}={cat}&{OFFSET}={offset}"
                response = await self._get(url=self.__get_url(cmd))
                _LOGGER.debug(f"Status Response {cmd}: {response}")

                if response is not None:
                    properties += response[PROPERTIES]
                    nextRequest = response[TOTAL] > (
                        offset + len(response[PROPERTIES]))
                    offset += len(response[PROPERTIES])
        _LOGGER.debug(f"Properties {properties}")
        self.properties = properties

    async def reboot_wallbox(self):
        """Reboot the wallbox."""
        response = await self._post(cmd=CMD, payload={PARAM_COMMAND: "reboot"})
        _LOGGER.debug(f"Reboot response {response}")

    async def async_request(self, method: str, cmd: str, json_data=None) -> ClientResponse | None:
        """Send a request to the API."""
        try:
            return await self.request(method, cmd, json_data)
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error async request %s", str(e))
            return None

    async def request(self, method: str, cmd: str, json_data=None) -> ClientResponse:
        """Send a request to the API."""
        if method == METHOD_POST:
            response = await self._post(cmd=cmd, payload=json_data)
        elif method == METHOD_GET:
            response = await self._get(url=self.__get_url(cmd))

        _LOGGER.debug(f"Request response {response}")
        return response

    async def set_value(self, api_param, value):
        """Set a value on the API."""
        response = await self._update_value(api_param, value)
        if response:
            # we expect that the value is updated so we are just update the value in the properties
            for index, prop in enumerate(self.properties):
                if prop[ID] == api_param:
                    _LOGGER.debug(f"Set {api_param} value {value}")
                    prop[VALUE] = value
                    self.properties[index] = prop
                    break

    async def get_value(self, api_param):
        """Get a value from the API."""
        await self._get_value(api_param)

    async def set_current_limit(self, limit) -> None:
        """Set the current limit."""
        _LOGGER.debug(f"Set current limit {limit}A")
        if limit > 32 | limit < 1:
            return None
        await self.set_value("2129_0", limit)

    async def set_rfid_auth_mode(self, enabled):
        """Set the RFID Auth Mode."""
        _LOGGER.debug(f"Set RFID Auth Mode {enabled}")

        value = 0
        if enabled:
            value = 2

        await self.set_value("2126_0", value)

    async def set_current_phase(self, phase) -> None:
        """Set the current phase."""
        _LOGGER.debug(f"Set current phase {phase}")
        if phase not in ('L1', 'L2', 'L3'):
            return None
        await self.set_value("2069_0", phase)

    async def set_phase_switching(self, enabled):
        """Set the phase switching."""
        _LOGGER.debug(f"Set Phase Switching {enabled}")

        value = 0
        if enabled:
            value = 1
        await self.set_value("2185_0", value)

    async def set_green_share(self, value) -> None:
        """Set the green share."""
        _LOGGER.debug(f"Set green share value {value}%")
        if value < 0 | value > 100:
            return None
        await self.set_value("3280_2", value)

    async def set_comfort_power(self, value) -> None:
        """Set the comfort power."""
        _LOGGER.debug(f"Set Comfort Level {value}W")
        if value < 1400 | value > 5000:
            return None
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
