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
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_DEVICES, \
    CONF_DEVICE_ID, CONCENTRATION_PARTS_PER_BILLION, \
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER, CONCENTRATION_PARTS_PER_MILLION
from homeassistant.helpers import discovery
from requests import PreparedRequest

from .const import DOMAIN, VERSION, ISSUE_URL, SUPPORT_LIB_URL, DATA_JQ300, \
    QUERY_TYPE_API, QUERY_TYPE_DEVICE, QUERY_METHOD_GET, BASE_URL_API, \
    BASE_URL_DEVICE, USERAGENT_API, USERAGENT_DEVICE, QUERY_TIMEOUT, \
    MSG_GENERIC_FAIL, MSG_LOGIN_FAIL, QUERY_METHOD_POST, MSG_BUSY, \
    SENSORS, UPDATE_MIN_TIME, CONF_RECEIVE_TVOC_IN_PPB, \
    CONF_RECEIVE_HCHO_IN_PPB, SENSORS_FILTER_TIME, MWEIGTH_TVOC, MWEIGTH_HCHO, \
    ATTR_DEVICE_BRAND, ATTR_DEVICE_MODEL, ATTR_DEVICE_ID, ATTR_RAW_STATE, \
    BINARY_SENSORS

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
        username, password, receive_tvoc_in_ppb, receive_hcho_in_ppb)
    hass.data[DATA_JQ300][username] = controller
    _LOGGER.info('Connected to cloud account %s', username)

    devs = controller.get_devices_list()
    if not devs:
        _LOGGER.error("Can't receive devices list from cloud.")
        return False
    for dev_id in devs.keys():
        if devices and devs[dev_id]['pt_name'] not in devices:
            continue
        hass.async_create_task(
            discovery.async_load_platform(hass, BINARY_SENSOR, DOMAIN, {
                CONF_USERNAME: username,
                CONF_DEVICE_ID: dev_id,
            }, config))
        hass.async_create_task(
            discovery.async_load_platform(hass, SENSOR, DOMAIN, {
                CONF_USERNAME: username,
                CONF_DEVICE_ID: dev_id,
            }, config))

    return True


# pylint: disable=R0902
class JqController:
    """JQ device controller"""

    # pylint: disable=R0913
    def __init__(self, username, password, receive_tvoc_in_ppb=False,
                 receive_hcho_in_ppb=False):
        """Initialize configured device."""
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
        self._sensors_raw = {}
        self._units = {}

        for sensor_id, data in BINARY_SENSORS.items():
            self._units[sensor_id] = data[1]
        for sensor_id, data in SENSORS.items():
            if (receive_tvoc_in_ppb and sensor_id == 8) \
                    or (receive_hcho_in_ppb and sensor_id == 7):
                self._units[sensor_id] = CONCENTRATION_PARTS_PER_BILLION
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

        return self._devices

    def _fetch_sensors(self, device_id, ts_now, force=False) -> bool:
        """Fetch states of available sensors for device."""
        devices = self.get_devices_list()
        _LOGGER.debug(devices)
        if not devices or not devices[device_id]:
            _LOGGER.error("Can't receive devices list from cloud.")
            return False

        ret = self.query(QUERY_TYPE_DEVICE, 'list', extra_params={
            'deviceToken': devices[device_id]['deviceToken'],
            'timestamp': ts_now,
            'callback': 'jsoncallback',
            '_': ts_now,
        })
        if not ret:
            return self._fetch_sensors(device_id, ts_now, True) \
                if not force else False

        res = {}
        for sensor in ret['deviceValueVos']:
            sensor_id = sensor['seq']
            if sensor['content'] is None \
                    or (sensor_id not in SENSORS.keys()
                            and sensor_id not in BINARY_SENSORS.keys()):
                continue

            res[sensor_id] = float(sensor['content'])
            if sensor_id == 8 and self._receive_tvoc_in_ppb:
                res[sensor_id] *= 1000 * 24.45 / MWEIGTH_TVOC
            elif sensor_id == 7 and self._receive_hcho_in_ppb:
                res[sensor_id] *= 1000 * 24.45 / MWEIGTH_HCHO
            if self._units[sensor_id] != \
                    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER:
                res[sensor_id] = int(res[sensor_id])

        self._sensors[device_id][ts_now] = res
        self._sensors_raw[device_id] = res
        return True

    def get_sensors(self, device_id) -> Optional[dict]:
        """Get states of available sensors for device."""
        ts_now = int(dt_util.now().timestamp())
        ts_overdue = ts_now - SENSORS_FILTER_TIME

        self._sensors.setdefault(device_id, {})

        # Filter historic states
        res = {}
        ts_min = max(list(filter(
            lambda x: x <= ts_overdue,
            self._sensors[device_id].keys()
        )) or {ts_overdue})
        # _LOGGER.debug('ts_overdue: %s; ts_min: %s', ts_overdue, ts_min)
        for m_ts, val in self._sensors[device_id].items():
            if m_ts >= ts_min:
                res[m_ts] = val
        self._sensors[device_id] = res

        if (not res or max(res) < ts_now - UPDATE_MIN_TIME) \
                and not self._fetch_sensors(device_id, ts_now):
            return None

        # Calculate average state values
        res = {}
        last_ts = ts_overdue
        last_data = {}
        for sensor_id in self._sensors_raw[device_id]:
            res.setdefault(sensor_id, 0)
            last_data.setdefault(sensor_id, 0)
        # Sum values
        for m_ts, data in self._sensors[device_id].items():
            val_t = m_ts - last_ts
            if val_t > 0:
                # _LOGGER.debug('%s: %s [%s]', m_ts, data, (m_ts - last_ts))
                for sensor_id, val in last_data.items():
                    res[sensor_id] += val * val_t
            last_ts = max(m_ts, ts_overdue)
            last_data = data
        # Add last values
        # _LOGGER.debug('%s: %s [%s]', last_ts, last_data,
        #               max(ts_now - last_ts, 1))
        val_t = ts_now - last_ts + 1
        for sensor_id, val in last_data.items():
            res[sensor_id] += val * val_t
        # Average and round
        length = max(
            1,
            ts_now - max(min(self._sensors[device_id].keys()), ts_overdue) + 1
        )
        # _LOGGER.debug('Averaging: %s / %s', res, length)
        for sensor_id in res:
            res[sensor_id] = self._sensors_raw[device_id][1] \
                if sensor_id == 1 \
                else int(
                    res[sensor_id] / length
                ) if self._units[sensor_id] in (
                    CONCENTRATION_PARTS_PER_MILLION,
                    CONCENTRATION_PARTS_PER_BILLION,
                ) else round(
                    res[sensor_id] / length,
                    1 if isinstance(res[sensor_id], int) else 3
                )
        # _LOGGER.debug('Result: %s', res)
        return res

    def get_sensors_raw(self, device_id) -> Optional[dict]:
        """Get raw values of states of available sensors for device."""
        return self._sensors_raw.get(device_id)
