"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

#  Copyright (c) 2020, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
from datetime import timedelta

from homeassistant.components.binary_sensor import (
    DEVICE_CLASS_PROBLEM,
    DOMAIN as BINARY_SENSOR,
)
from homeassistant.components.sensor import DOMAIN as SENSOR

try:
    from homeassistant.const import PERCENTAGE
except ImportError:
    from homeassistant.const import UNIT_PERCENTAGE as PERCENTAGE
from homeassistant.const import (
    TEMP_CELSIUS,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_HUMIDITY,
    CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
)

# Base component constants
DOMAIN = "jq300"
VERSION = "dev"
ISSUE_URL = "https://github.com/Limych/ha-jq300/issues"
ATTRIBUTION = None

SUPPORT_LIB_URL = "https://github.com/Limych/jq300/issues/new/choose"

CONF_ACCOUNT_ID = "account_id"
CONF_RECEIVE_TVOC_IN_PPB = "receive_tvoc_in_ppb"
CONF_RECEIVE_HCHO_IN_PPB = "receive_hcho_in_ppb"

# Error strings
MSG_GENERIC_FAIL = "Sorry.. Something went wrong..."
MSG_LOGIN_FAIL = "Account name or password is wrong, please try again"
MSG_BUSY = "The system is busy"

QUERY_TYPE_API = "API"
QUERY_TYPE_DEVICE = "DEVICE"

BASE_URL_API = "http://www.youpinyuntai.com:32086/ypyt-api/api/app/"
BASE_URL_DEVICE = "https://www.youpinyuntai.com:31447/device/"

_USERAGENT_SYSTEM = "Android 6.0.1; RedMi Note 5 Build/RB3N5C"
USERAGENT_API = "Dalvik/2.1.0 (Linux; U; %s)" % _USERAGENT_SYSTEM
USERAGENT_DEVICE = (
    "Mozilla/5.0 (Linux; %s; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/68.0.3440.91 Mobile Safari/537.36" % _USERAGENT_SYSTEM
)

ACCOUNT_CONTROLLER = "account_controller"

PLATFORMS = (SENSOR, BINARY_SENSOR)

BINARY_SENSORS = {
    1: ["Air Quality Alert", None, "mdi:alert", DEVICE_CLASS_PROBLEM, None],
}

SENSORS = {
    4: [
        "Internal Temperature",
        TEMP_CELSIUS,
        "mdi:thermometer",
        DEVICE_CLASS_TEMPERATURE,
        None,
    ],
    5: ["Humidity", PERCENTAGE, "mdi:water-percent", DEVICE_CLASS_HUMIDITY, None],
    6: [
        "PM 2.5",
        CONCENTRATION_MICROGRAMS_PER_CUBIC_METER,
        "mdi:air-filter",
        None,
        "pm25",
    ],
    7: ["HCHO", CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER, "mdi:cloud", None, None],
    8: ["TVOC", CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER, "mdi:radiator", None, None],
    9: ["eCO2", CONCENTRATION_PARTS_PER_MILLION, "mdi:molecule-co2", None, None],
}

ATTR_DEVICE_ID = "device_id"
ATTR_DEVICE_BRAND = "device_brand"
ATTR_DEVICE_MODEL = "device_model"
ATTR_RAW_STATE = "raw_state"

SCAN_INTERVAL = timedelta(seconds=60)
UPDATE_MIN_INTERVAL = timedelta(minutes=10)
SENSORS_FILTER_FRAME = timedelta(minutes=15)

SIGNAL_UPDATE_JQ300 = "jq300_update"

QUERY_TIMEOUT = 7  # seconds
UPDATE_TIMEOUT = 12  # seconds

MWEIGTH_TVOC = 56.1060  # g/mol
MWEIGTH_HCHO = 30.0260  # g/mol
