
DOMAIN = "alfen_wallbox"

ID = "id"
VALUE = "value"
PROPERTIES = "properties"
CAT = "cat"
OFFSET = "offset"
TOTAL = "total"

METHOD_POST = "POST"
METHOD_GET = "GET"

CMD = "cmd"
PROP = "prop"
INFO = "info"
LOGIN = "login"
LOGOUT = "logout"

PARAM_USERNAME = "username"
PARAM_PASSWORD = "password"
PARAM_COMMAND = "command"
PARAM_DISPLAY_NAME = "displayname"

DISPLAY_NAME_VALUE = "ha"

CAT_GENERIC = "generic"
CAT_GENERIC2 = "generic2"
CAT_METER1 = "meter1"
CAT_METER4 = "meter4"
CAT_STATES = "states"
CAT_TEMP = "temp"
CAT_OCPP = "ocpp"
CAT_MBUS_TCP = "MbusTCP"
CAT_COMM = "comm"
CAT_DISPLAY = "display"

COMMAND_REBOOT = "reboot"


TIMEOUT = 30

SERVICE_REBOOT_WALLBOX = "reboot_wallbox"
SERVICE_SET_CURRENT_LIMIT = "set_current_limit"
SERVICE_ENABLE_RFID_AUTHORIZATION_MODE = "enable_rfid_authorization_mode"
SERVICE_DISABLE_RFID_AUTHORIZATION_MODE = "disable_rfid_authorization_mode"
SERVICE_SET_CURRENT_PHASE = "set_current_phase"
SERVICE_ENABLE_PHASE_SWITCHING = "enable_phase_switching"
SERVICE_DISABLE_PHASE_SWITCHING = "disable_phase_switching"
SERVICE_SET_GREEN_SHARE = "set_green_share"
SERVICE_SET_COMFORT_POWER = "set_comfort_power"

ALFEN_PRODUCT_MAP = {
    "NG900-60503": "Eve Single S-line, 1 phase, LED, type 2 socket",
    "NG900-60505": "Eve Single S-line, 1 phase, LED, type 2 socket shutters",
    "NG900-60507": "Eve Single S-line, 1 phase, LED, tethered cable",
    "NG910-60003": "Eve Single Pro-line, 1 phase, display, type 2 socket",
    "NG910-60005": "Eve Single Pro-line FR, 1 phase, display, type 2 shutters",
    "NG910-60007": "Eve Single Pro-line, 1 phase, display, tethered cable",
    "NG910-60023": "Eve Single Pro-line, 3 phase, display, type 2 socket",
    "NG910-60025": "Eve Single Pro-line FR, 3 phase, display, type 2 shutters",
    "NG910-60027": "Eve Single Pro-line, 3 phase, display, tethered cable",
    "NG910-60123": "Eve Single Pro-Line DE, 3 phase, display, type 2 socket",
    "NG910-60127": "Eve Single Pro-Line DE, 3 phase, display, tethered cable",
    "NG910-60503": "Eve Single S-line, 1 phase, LED, type 2 socket",
    "NG910-60505": "Eve Single S-line, 1 phase, LED, type 2 shutters",
    "NG910-60507": "Eve Single S-line, 1 phase, LED, tethered cable",
    "NG910-60523": "Eve Single S-line, 3 phase, LED, type 2 socket",
    "NG910-60525": "Eve Single S-line, 3 phase, LED, type 2 shutters",
    "NG910-60527": "Eve Single S-line, 3 phase, LED, tethered cable",
    "NG910-60553": "Eve Single S-line, 1 phase, LED, RFID, type 2 socket",
    "NG910-60555": "Eve Single S-line, 3 phase, LED, RFID, type 2 shutters",
    "NG910-60557": "Eve Single S-line, 3 phase, LED, RFID, tethered cable",
    "NG910-60573": "Eve Single S-line, 3 phase, LED, GPRS, type 2 socket",
    "NG910-60575": "Eve Single S-line, 3 phase, LED, GPRS, type 2 shutters",
    "NG910-60577": "Eve Single S-line, 3 phase, LED, GPRS, tethered cable",
    "NG910-60583": "Eve Single S-line, 3 phase, LED, RFID, type 2 socket",
    "NG910-60585": "Eve Single S-line, 3 phase, LED, RFID, type 2 shutters",
    "NG910-60587": "Eve Single S-line, 3 phase, LED, RFID, type 2 tethered cable",
    "NG910-60593": "Eve Single S-line, 3 phase, LED, GPRS, type 2 socket",
    "NG910-60595": "Eve Single S-line, 3 phase, LED, GPRS, type 2 shutters",
    "NG910-60597": "Eve Single S-line, 3 phase, LED, GPRS, type 2 tethered cable",
    "NG920-61031": "Eve Double Pro-line, 2 x type 2 socket, 1 phase, max. 1x32A input current",
    "NG920-61032": "Eve Double Pro-line, 2 x type 2 socket, 2 phase, max. 1x32A input current",
    "NG920-61021": "Eve Double Pro-line, 2 x type 2 socket, 3 phase, max. 1x32A input current",
    "NG920-61022": "Eve Double Pro-line, 2 x type 2 socket, 3 phase, max. 2x32A input current",
    "NG920-61001": "Eve Double Pro-line, 3 phase, 2x socket Type 2, single feeder, RCD Type A",
    "NG920-61002": "Eve Double Pro-line, 3 phase, 2x socket Type 2, dual feeder, RCD Type A",
    "NG920-61011": "Eve Double Pro-line, 2 x type 2 socket, 1-phase, max. 1x32A input current, RCD B 3F 1C T2, Display",
    "NG920-61012": "Eve Double Pro-line, 2 x type 2 socket, 1-phase, max. 2x32A input current, RCD B 3F 1C T2, Display",
    "NG920-61101": "Eve Double Pro-line DE, 2 x type 2 socket, 3-phase, max. 1x32A input current, RCD B 3F 1C T2, Display",
    "NG920-61102": "Eve Double Pro-line DE, 2 x type 2 socket, 3-phase, max. 2x32A input current, RCD B 3F 1C T2, Display",
    "NG920-61205": "Eve Double Pro-line FR, 3 phase, Display, 2x socket Type 2S (shutters), max. 1x32A input current",
    "NG920-61206": "Eve Double Pro-line FR, 3 phase, Display, 2x socket Type 2S (shutters), max. 2x32A input current",
    "NG920-61215": "Eve Double Pro-line FR, 1 phase, Display, 2x socket Type 2S (shutters), max. 1x32A input current",
    "NG920-61216": "Eve Double Pro-line FR, 1 phase, Display, 2x socket Type 2S (shutters), max. 2x32A input current",
}
