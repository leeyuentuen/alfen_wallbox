import json
import logging
from anyio import sleep
from async_timeout import timeout
import requests

from urllib3 import disable_warnings
from datetime import timedelta

from homeassistant.core import HomeAssistant


from .const import (
    CAT,
    CAT_GENERIC,
    CAT_GENERIC2,
    CAT_METER1,
    CAT_METER4,
    CAT_OCPP,
    CAT_STATES,
    CAT_TEMP,
    CAT_MBUS_TCP,
    CAT_COMM,
    CAT_DISPLAY,
    CMD,
    DISPLAY_NAME_VALUE,
    DOMAIN,
    ALFEN_PRODUCT_MAP,
    ID,
    METHOD_GET,
    METHOD_POST,
    OFFSET,
    INFO,
    LOGIN,
    LOGOUT,
    PARAM_COMMAND,
    PARAM_DISPLAY_NAME,
    PARAM_PASSWORD,
    PARAM_USERNAME,
    PROP,
    PROPERTIES,
    TIMEOUT,
    TOTAL,
    VALUE
)

POST_HEADER_JSON = {"Content-Type": "application/json"}

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=5)


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
        self._session = requests.Session()
        self.username = username
        self.info = None
        self.id = None
        if self.username is None:
            self.username = "admin"
        self.password = password
        self.properties = []
        self._session.verify = False
        self.keepLogout = False
        self.updating = False
        self.need_wait = False
        self.number_socket = 1
        self._hass = hass
        disable_warnings()

    async def init(self):
        await self._hass.async_add_executor_job(self.get_info)
        self.id = "alfen_{}".format(self.name)
        if self.name is None:
            self.name = f"{self.info.identity} ({self.host})"

    def get_number_of_socket(self):
        for prop in self.properties:
            if prop[ID] == '205E_0':
                self.number_socket = int(prop[VALUE])
                break

    def get_info(self):
        response = self._session.get(
            url=self.__get_url(INFO),
        )
        _LOGGER.debug(f"Response {response}")

        if response.status_code != 200:
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
            response.raise_for_status()
            resp = response.text
            self.info = AlfenDeviceInfo(json.loads(resp))

    @property
    def status(self) -> str:
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
        if not self.updating and not self.need_wait:
            self.updating = True
            if not self.keepLogout:
                await self._hass.async_add_executor_job(self._get_all_properties_value)
            self.updating = False

    def _post(self, cmd, payload=None, allowed_login=True):
        try:
            self.need_wait = True
            response = self._session.post(
                url=self.__get_url(cmd),
                json=payload,
                headers=POST_HEADER_JSON,
                timeout=TIMEOUT)
            self.need_wait = False
            if response.status_code == 401 and allowed_login:
                _LOGGER.debug("POST with login")
                self.login()
                return self._post(cmd, payload, False)
            response.raise_for_status()
            if response:
                return response
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on POST %s", str(e))
            self.need_wait = False
            return None

    def _get(self, url, allowed_login=True):
        try:
            self.need_wait = True
            response = self._session.get(url, timeout=TIMEOUT)
            self.need_wait = False
            if response.status_code == 401 and allowed_login:
                _LOGGER.debug("GET with login")
                self.login()
                return self._get(url, False)
            response.raise_for_status()

            if response is not None and response != '':
                return json.loads(response.text)
            return None
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on GET %s", str(e))
            self.need_wait = False
            return None

    def login(self):
        try:
            self.need_wait = True
            del self._session.cookies["session"]
            response = self._post(cmd=LOGIN, payload={
                PARAM_USERNAME: self.username, PARAM_PASSWORD: self.password, PARAM_DISPLAY_NAME: DISPLAY_NAME_VALUE})
            _LOGGER.debug(f"Login response {response}")
            self.need_wait = False
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on LOGIN %s", str(e))
            self.need_wait = False
            return None

    def logout(self):
        try:
            self.need_wait = True
            del self._session.cookies["session"]
            response = self._post(cmd=LOGOUT)
            _LOGGER.debug(f"Logout response {response}")
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on LOGOUT %s", str(e))
            self.need_wait = False
            return None

    def _update_value(self, api_param, value):
        try:
            response = self._post(cmd=PROP, payload={api_param: {
                ID: api_param, VALUE: str(value)}})
            _LOGGER.debug(f"Set {api_param} value {value} response {response}")
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error on UPDATE VALUE %s", str(e))
            self.need_wait = False
            return None

    def _get_value(self, api_param):
        response = self._get(url=self.__get_url(
            "{}?{}={}".format(PROP, ID, api_param)))

        _LOGGER.debug(f"Status Response {response}")

        if response is not None:
            if self.properties is None:
                self.properties = []
            for resp in response[PROPERTIES]:
                for prop in self.properties:
                    if prop[ID] == resp[ID]:
                        prop[VALUE] = resp[VALUE]
                        break

    def _get_all_properties_value(self):
        properties = []
        for cat in (CAT_GENERIC, CAT_GENERIC2, CAT_METER1, CAT_STATES, CAT_TEMP, CAT_OCPP, CAT_METER4, CAT_MBUS_TCP, CAT_COMM, CAT_DISPLAY):
            nextRequest = True
            offset = 0
            while (nextRequest):
                response = self._get(url=self.__get_url(
                    "{}?{}={}&{}={}".format(PROP, CAT, cat, OFFSET, offset)))
                _LOGGER.debug(f"Status Response {response}")

                if response is not None:
                    properties += response[PROPERTIES]
                nextRequest = response[TOTAL] > (
                    offset + len(response[PROPERTIES]))
                offset += len(response[PROPERTIES])
        _LOGGER.debug(f"Properties {properties}")
        self.properties = properties

    async def reboot_wallbox(self):
        response = self._post(cmd=CMD, payload={PARAM_COMMAND: "reboot"})
        _LOGGER.debug(f"Reboot response {response}")

    async def async_request(self, method: str, cmd: str, json_data=None):
        try:
            response_json = await self._hass.async_add_executor_job(self.request, method, cmd, json_data)
            return response_json
        except Exception as e:  # pylint: disable=broad-except
            _LOGGER.error("Unexpected error async request %s", str(e))
            return None

    def request(self, method: str, cmd: str, json_data=None):
        if method == METHOD_POST:
            response = self._post(cmd=cmd, payload=json_data)
        elif method == METHOD_GET:
            response = self._get(url=self.__get_url(cmd))

        _LOGGER.debug(f"Request response {response}")
        return response

    async def set_value(self, api_param, value):
        self.need_wait = True
        await self._hass.async_add_executor_job(self._update_value, api_param, value)

        # we expect that the value is updated so we are just update the value in the properties
        for prop in self.properties:
            if prop[ID] == api_param:
                _LOGGER.debug(f"Set {api_param} value {value}")
                prop[VALUE] = value
                break
        self.need_wait = False

    async def get_value(self, api_param):
        await self._hass.async_add_executor_job(self._get_value, api_param)

    async def set_current_limit(self, limit):
        _LOGGER.debug(f"Set current limit {limit}A")
        if limit > 32 | limit < 1:
            return None
        await self.set_value("2129_0", limit)

    async def set_rfid_auth_mode(self, enabled):
        _LOGGER.debug(f"Set RFID Auth Mode {enabled}")

        value = 0
        if enabled:
            value = 2

        await self.set_value("2126_0", value)

    async def set_current_phase(self, phase):
        _LOGGER.debug(f"Set current phase {phase}")
        if phase not in ('L1', 'L2', 'L3'):
            return None
        await self.set_value("2069_0", phase)

    async def set_phase_switching(self, enabled):
        _LOGGER.debug(f"Set Phase Switching {enabled}")

        value = 0
        if enabled:
            value = 1
        await self.set_value("2185_0", value)

    async def set_green_share(self, value):
        _LOGGER.debug(f"Set green share value {value}%")
        if value < 0 | value > 100:
            return None
        await self.set_value("3280_2", value)

    async def set_comfort_power(self, value):
        _LOGGER.debug(f"Set Comfort Level {value}W")
        if value < 1400 | value > 5000:
            return None
        await self.set_value("3280_3", value)

    def __get_url(self, action) -> str:
        return "https://{}/api/{}".format(self.host, action)


class AlfenDeviceInfo:
    def __init__(self, response) -> None:
        self.identity = response["Identity"]
        self.firmware_version = response["FWVersion"]
        self.model_id = response["Model"]

        self.model = ALFEN_PRODUCT_MAP.get(self.model_id, self.model_id)
        self.object_id = response["ObjectId"]
        self.type = response["Type"]
