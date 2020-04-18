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
from typing import Optional, List

import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
import requests
import voluptuous as vol
from homeassistant.components.sensor import DOMAIN as SENSOR
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_NAME, \
    CONF_DEVICES, CONF_DEVICE_ID
from homeassistant.helpers import discovery
from requests import PreparedRequest

from .const import DOMAIN, VERSION, ISSUE_URL, SUPPORT_LIB_URL, DATA_JQ300, \
    QUERY_TYPE_API, QUERY_TYPE_DEVICE, QUERY_METHOD_GET, BASE_URL_API, \
    BASE_URL_DEVICE, USERAGENT_API, USERAGENT_DEVICE, QUERY_TIMEOUT, \
    MSG_GENERIC_FAIL, MSG_LOGIN_FAIL, QUERY_METHOD_POST, MSG_BUSY, \
    SENSOR_IDS, UPDATE_MIN_TIME

_LOGGER = logging.getLogger(__name__)

ACCOUNT_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_DEVICES): List[str],
})

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.All(cv.ensure_list, [ACCOUNT_SCHEMA])
}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config):
    """Set up component."""
    # Print startup message
    _LOGGER.info('Version %s', VERSION)
    _LOGGER.info('If you have ANY issues with this,'
                 ' please report them here: %s', ISSUE_URL)

    hass.data.setdefault(DATA_JQ300, {})

    for index, account_config in enumerate(config[DOMAIN]):
        username = account_config.get(CONF_USERNAME)
        password = account_config.get(CONF_PASSWORD)
        devices = account_config.get(CONF_DEVICES)

        if username in list(hass.data[DATA_JQ300]):
            _LOGGER.error('Duplicate account! '
                          'Account "%s" is already exists.', username)
            continue

        controller = JqController(hass, username, password)
        hass.data[DATA_JQ300][username] = controller
        _LOGGER.info('Connected to account "%s" as %s',
                     controller.name, username)

        devs = controller.get_devices_list()
        for dev_id in devs.keys():
            if devices and devs[dev_id]['pt_name'] not in devices:
                continue
            discovery.load_platform(hass, SENSOR, DOMAIN, {
                CONF_USERNAME: username,
                CONF_DEVICE_ID: dev_id,
            }, config)

    if not hass.data[DATA_JQ300]:
        return False

    return True


class JqController:
    """JQ device controller"""

    def __init__(self, hass, username, password):
        """Initialize configured device."""
        self.hass = hass
        self.params = {
            'uid': -1000,
            'safeToken': 'anonymous',
        }

        self._username = username
        self._password = password

        self._available = False
        self._session = requests.session()
        self._devices = {}
        self._sensors = {}

    @property
    def unique_id(self):
        """Return a device unique ID."""
        return self._username

    @property
    def name(self):
        """Get custom device name."""
        return self._username

    @property
    def available(self) -> bool:
        """Return True if account is available."""
        return self._login()

    @staticmethod
    def _get_useragent(query_type) -> str:
        """Generate User-Agent for requests"""
        if query_type == QUERY_TYPE_API:
            return USERAGENT_API
        elif query_type == QUERY_TYPE_DEVICE:
            return USERAGENT_DEVICE

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

        except Exception as err_msg:
            _LOGGER.error("Error! %s", err_msg)
            raise err_msg

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
        if not self._login():
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

        for dev in ret['deviceInfoBodyList']:
            self._devices[dev['deviceid']] = dev

        self._sensors = {}
        return self._devices

    def get_sensors(self, device_id, force=False) -> Optional[dict]:
        ts = int(dt_util.now().timestamp() * 1000)
        ts_overdue = ts - UPDATE_MIN_TIME

        if not force and device_id in self._sensors \
                and self._sensors[device_id][''] >= ts_overdue:
            data = self._sensors[device_id].copy()
            del data['']
            return data

        devices = self.get_devices_list()
        _LOGGER.debug(devices)
        if not devices or not devices[device_id]:
            return None

        ret = self.query(QUERY_TYPE_DEVICE, 'list', extra_params={
            'deviceToken': devices[device_id]['deviceToken'],
            'timestamp': ts,
            'callback': 'jsoncallback',
            '_': ts,
        })
        if not ret:
            return self.get_sensors(device_id, True) if not force else None

        data = {}
        for sensor in ret['deviceValueVos']:
            if sensor['seq'] in SENSOR_IDS.keys() and sensor['content'] is \
                    not None and float(sensor['content']) > 0:
                data[sensor['seq']] = float(sensor['content'])

        self._sensors[device_id] = data.copy()
        self._sensors[device_id][''] = ts
        return data
