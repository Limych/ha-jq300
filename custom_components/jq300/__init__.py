"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

#
#  Copyright (c) 2020, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)
#

import json
import logging
from typing import Optional

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
import requests
import voluptuous as vol
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_DEVICES, \
    CONF_DEVICE_ID
from homeassistant.helpers import discovery
from requests import PreparedRequest

from .const import DOMAIN, VERSION, ISSUE_URL, SUPPORT_LIB_URL, DATA_JQ300, \
    QUERY_TYPE_API, QUERY_TYPE_DEVICE, QUERY_METHOD_GET, BASE_URL_API, \
    BASE_URL_DEVICE, USERAGENT_API, USERAGENT_DEVICE, QUERY_TIMEOUT, \
    MSG_GENERIC_FAIL, MSG_LOGIN_FAIL, QUERY_METHOD_POST, MSG_BUSY, \
    SENSORS, UPDATE_MIN_TIME, CONF_RECEIVE_TVOC_IN_PPB, \
    CONF_RECEIVE_HCHO_IN_PPB, UNIT_PPM, UNIT_MGM3, UNIT_PPB

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_RECEIVE_TVOC_IN_PPB, default=False): cv.boolean,
        vol.Optional(CONF_RECEIVE_HCHO_IN_PPB, default=False): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up component."""
    # Print startup message
    _LOGGER.info('Version %s', VERSION)
    _LOGGER.info('If you have ANY issues with this,'
                 ' please report them here: %s', ISSUE_URL)

    hass.data.setdefault(DATA_JQ300, {})

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    devices = config[DOMAIN].get(CONF_DEVICES)
    receive_tvoc_in_ppb = config[DOMAIN].get(CONF_RECEIVE_TVOC_IN_PPB)
    receive_hcho_in_ppb = config[DOMAIN].get(CONF_RECEIVE_HCHO_IN_PPB)

    controller = JqController(
        hass, username, password, receive_tvoc_in_ppb, receive_hcho_in_ppb)
    hass.data[DATA_JQ300][username] = controller
    _LOGGER.info('Connected to cloud account %s', username)

    devs = controller.get_devices_list()
    if not devs:
        _LOGGER.error("Can't receive devices list from cloud.")
        return False
    for dev_id in devs.keys():
        if devices and devs[dev_id]['pt_name'] not in devices:
            continue
        discovery.load_platform(hass, SENSOR, DOMAIN, {
            CONF_USERNAME: username,
            CONF_DEVICE_ID: dev_id,
        }, config)

    return True


# pylint: disable=R0902
class JqController:
    """JQ device controller"""

    # pylint: disable=R0913
    def __init__(self, hass, username, password, receive_tvoc_in_ppb,
                 receive_hcho_in_ppb):
        """Initialize configured device."""
        self.hass = hass
        self.params = {
            'uid': -1000,
            'safeToken': 'anonymous',
        }

        self._username = username
        self._password = password
        self._receive_tvoc_in_ppb = receive_tvoc_in_ppb
        self._receive_hcho_in_ppb = receive_hcho_in_ppb

        self._available = False
        self._session = requests.session()
        self._devices = {}
        self._sensors = {}
        self._units = {}

        for sensor_id, data in SENSORS.items():
            if (receive_tvoc_in_ppb and sensor_id == 8) \
                    or (receive_hcho_in_ppb and sensor_id == 7):
                self._units[sensor_id] = UNIT_PPB
            else:
                self._units[sensor_id] = data[1]

    @property
    def unique_id(self):
        """Return a device unique ID."""
        return self._username

    @property
    def name(self):
        """Get custom device name."""
        return 'JQ300'

    @property
    def available(self) -> bool:
        """Return True if account is available."""
        return self._login()

    @property
    def units(self):
        """Get list of units for sensors."""
        return self._units

    @staticmethod
    def _get_useragent(query_type) -> str:
        """Generate User-Agent for requests"""
        # pylint: disable=R1705
        if query_type == QUERY_TYPE_API:
            return USERAGENT_API
        elif query_type == QUERY_TYPE_DEVICE:
            return USERAGENT_DEVICE
        else:
            raise ValueError('Unknown query type "%s"' % query_type)

    def _add_url_params(self, url: str, extra_params: dict) -> str:
        """Add params to URL."""
        params = self.params.copy()
        params.update(extra_params)

        req = PreparedRequest()
        req.prepare_url(url, params)

        return req.url

    def _get_url(self, query_type, function: str, extra_params=None) -> str:
        """Generate request URL"""
        if query_type == QUERY_TYPE_API:
            url = BASE_URL_API + function
        elif query_type == QUERY_TYPE_DEVICE:
            url = BASE_URL_DEVICE + function
        else:
            raise ValueError('Unknown query type "%s"' % query_type)

        if extra_params:
            url = self._add_url_params(url, extra_params)
        return url

    # pylint: disable=R0911,R0912
    def query(self, query_type, function: str,
              extra_params=None) -> Optional[dict]:
        """Query data from cloud."""
        url = self._get_url(query_type, function)
        _LOGGER.debug("Querying %s", url)

        response = None

        # allow to override params when necessary
        # and update self.params globally for the next connection
        params = self.params.copy()
        if query_type == QUERY_TYPE_DEVICE:
            params['saveToken'] = params['safeToken']
            del params['safeToken']
        if extra_params:
            params.update(extra_params)

        try:
            ret = self._session.get(url, params=params, headers={
                'User-Agent': self._get_useragent(query_type)
            }, timeout=QUERY_TIMEOUT)
            _LOGGER.debug("_query ret %s", ret.status_code)

        # pylint: disable=W0703
        except Exception as err_msg:
            _LOGGER.error("Error! %s", err_msg)
            return None

        if ret.status_code == 200 or ret.status_code == 204:
            response = ret

        if response is None:  # pragma: no cover
            _LOGGER.debug(MSG_GENERIC_FAIL)
            return None

        _LOGGER.debug(response.content)
        if response.content.startswith(b'jsoncallback('):
            response = json.loads(response.content[13:-1])
        else:
            response = json.loads(response.content)

        if query_type == QUERY_TYPE_API:
            if response['code'] == 102:
                _LOGGER.error(MSG_LOGIN_FAIL)
                return None
            if response['code'] == 9999:
                _LOGGER.error(MSG_BUSY)
                return None
            if response['code'] != 2000:
                _LOGGER.error(MSG_GENERIC_FAIL)
                return None
        elif query_type == QUERY_TYPE_DEVICE:
            if int(response['returnCode']) != 0:
                _LOGGER.error(MSG_GENERIC_FAIL)
                self.params['uid'] = -1000
                return None
        else:
            raise ValueError('Unknown query type "%s"' % query_type)

        return response

    def _login(self, force=False) -> bool:
        if not force and self.params['uid'] > 0:
            return True

        self.params['uid'] = -1000
        self.params['safeToken'] = 'anonymous'
        ret = self.query(QUERY_TYPE_API, 'loginByEmail', extra_params={
            'chr': 'clt',
            'email': self._username,
            'password': self._password,
            'os': 2
        })
        if not ret:
            return self._login(True) if not force else False

        self.params['uid'] = ret['uid']
        self.params['safeToken'] = ret['safeToken']
        self._devices = {}
        return True

    def get_devices_list(self, force=False) -> Optional[dict]:
        """Get list of available devices."""
        if not self._login():
            _LOGGER.error("Can't login to cloud.")
            return None

        if not force and self._devices:
            return self._devices

        ret = self.query(QUERY_TYPE_API, 'deviceManager', extra_params={
            'platform': 'android',
            'clientType': 2,
            'action': 'deviceManager',
        })
        if not ret:
            return self.get_devices_list(True) if not force else None

        tstamp = int(dt_util.now().timestamp() * 1000)
        for dev in ret['deviceInfoBodyList']:
            dev[''] = tstamp
            self._devices[dev['deviceid']] = dev

        self._sensors = {}
        return self._devices

    def get_sensors(self, device_id, force=False) -> Optional[dict]:
        """Get list of available sensors for device."""
        tstamp = int(dt_util.now().timestamp() * 1000)
        ts_overdue = tstamp - UPDATE_MIN_TIME

        if not force and device_id in self._sensors \
                and self._sensors[device_id][''] >= ts_overdue:
            res = self._sensors[device_id].copy()
            del res['']
            return res

        devices = self.get_devices_list()
        _LOGGER.debug(devices)
        if not devices or not devices[device_id]:
            _LOGGER.error("Can't receive devices list from cloud.")
            return None

        ret = self.query(QUERY_TYPE_DEVICE, 'list', extra_params={
            'deviceToken': devices[device_id]['deviceToken'],
            'timestamp': tstamp,
            'callback': 'jsoncallback',
            '_': tstamp,
        })
        if not ret:
            return self.get_sensors(device_id, True) if not force else None

        res = {}
        for sensor in ret['deviceValueVos']:
            sensor_id = sensor['seq']
            if sensor['content'] is None \
                    or float(sensor['content']) <= 0 \
                    or sensor_id not in SENSORS.keys():
                continue

            res[sensor_id] = float(sensor['content'])
            if sensor_id == 8 and self._receive_tvoc_in_ppb:
                res[sensor_id] *= 310     # M = 78.9516 g/mol
            elif sensor_id == 7 and self._receive_hcho_in_ppb:
                res[sensor_id] *= 814     # M = 30.026 g/mol
            if self._units[sensor_id] != UNIT_MGM3:
                res[sensor_id] = int(res[sensor_id])

        self._sensors[device_id] = res.copy()
        self._sensors[device_id][''] = tstamp
        return res
