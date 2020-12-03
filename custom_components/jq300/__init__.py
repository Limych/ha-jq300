"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

#  Copyright (c) 2020, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

import asyncio
import json
import logging
from datetime import timedelta
from time import monotonic
from typing import Optional, Dict, Any
from urllib.parse import urlparse

import async_timeout
import homeassistant.helpers.config_validation as cv
import homeassistant.util.dt as dt_util
import paho.mqtt.client as mqtt
import requests
import voluptuous as vol
from homeassistant import exceptions
from homeassistant.const import (
    CONF_USERNAME,
    CONF_PASSWORD,
    CONF_DEVICES,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_MILLION,
)
from homeassistant.helpers import discovery
from homeassistant.helpers.dispatcher import dispatcher_send
from homeassistant.util import Throttle
from requests import PreparedRequest

from .const import (
    DOMAIN,
    VERSION,
    ISSUE_URL,
    QUERY_TYPE_API,
    QUERY_TYPE_DEVICE,
    BASE_URL_API,
    BASE_URL_DEVICE,
    USERAGENT_API,
    USERAGENT_DEVICE,
    QUERY_TIMEOUT,
    MSG_GENERIC_FAIL,
    MSG_LOGIN_FAIL,
    MSG_BUSY,
    SENSORS,
    CONF_RECEIVE_TVOC_IN_PPB,
    CONF_RECEIVE_HCHO_IN_PPB,
    SENSORS_FILTER_FRAME,
    MWEIGTH_TVOC,
    MWEIGTH_HCHO,
    BINARY_SENSORS,
    PLATFORMS,
    UPDATE_TIMEOUT,
    ACCOUNT_CONTROLLER,
    SIGNAL_UPDATE_JQ300,
    CONF_ACCOUNT_ID,
    MQTT_URL,
)
from .util import mask_email

_LOGGER = logging.getLogger(__name__)
_LOGGER_MQTT = logging.getLogger(__name__ + ".mqtt")

ACCOUNT_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_USERNAME): cv.string,
        vol.Required(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_DEVICES): vol.All(cv.ensure_list, [cv.string]),
        vol.Optional(CONF_RECEIVE_TVOC_IN_PPB, default=False): cv.boolean,
        vol.Optional(CONF_RECEIVE_HCHO_IN_PPB, default=False): cv.boolean,
    }
)

CONFIG_SCHEMA = vol.Schema({DOMAIN: ACCOUNT_SCHEMA}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass, config) -> bool:
    """Set up component environment."""
    conf = config.get(DOMAIN)
    if conf is None:
        return True

    # Print startup message
    _LOGGER.info("Version %s", VERSION)
    _LOGGER.info(
        "If you have ANY issues with this, please report them here: %s", ISSUE_URL
    )

    hass.data.setdefault(DOMAIN, {})

    username = config[DOMAIN].get(CONF_USERNAME)
    password = config[DOMAIN].get(CONF_PASSWORD)
    active_devices = config[DOMAIN].get(CONF_DEVICES, [])
    receive_tvoc_in_ppb = config[DOMAIN].get(CONF_RECEIVE_TVOC_IN_PPB)
    receive_hcho_in_ppb = config[DOMAIN].get(CONF_RECEIVE_HCHO_IN_PPB)

    _LOGGER.debug("Connecting to account %s", mask_email(conf[CONF_USERNAME]))

    account = JqAccount(
        hass, username, password, receive_tvoc_in_ppb, receive_hcho_in_ppb
    )

    try:
        devices = await account.async_update_devices_or_timeout()
    except CannotConnect:
        return False

    devs = {}
    for device_id in devices:
        name = devices[device_id]["pt_name"]
        if active_devices and name not in active_devices:
            continue

        account.active_devices.append(device_id)
        devs[name] = device_id

    hass.data[DOMAIN][account.unique_id] = {
        ACCOUNT_CONTROLLER: account,
        CONF_DEVICES: devs,
    }

    # Load platforms
    for platform in PLATFORMS:
        hass.async_create_task(
            discovery.async_load_platform(
                hass, platform, DOMAIN, {CONF_ACCOUNT_ID: account.unique_id}, config
            )
        )

    return True


class CannotConnect(exceptions.HomeAssistantError):
    """Error to indicate we cannot connect."""


# pylint: disable=too-many-instance-attributes
class JqAccount:
    """JQ-300 cloud account controller."""

    # pylint: disable=R0913
    def __init__(
        self,
        hass,
        username,
        password,
        receive_tvoc_in_ppb=False,
        receive_hcho_in_ppb=False,
    ):
        """Initialize configured controller."""
        self.params = {
            "uid": -1000,
            "safeToken": "anonymous",
        }

        self.hass = hass
        self._username = username
        self._password = password
        self._receive_tvoc_in_ppb = receive_tvoc_in_ppb
        self._receive_hcho_in_ppb = receive_hcho_in_ppb

        self._mqtt = None
        self._active_devices = []
        self._session = requests.session()
        self._devices = {}
        self._sensors = {}
        self._sensors_raw = {}
        self._units = {}
        self._sensors_last_update = 0

        for sensor_id, data in BINARY_SENSORS.items():
            self._units[sensor_id] = data[1]
        for sensor_id, data in SENSORS.items():
            if (receive_tvoc_in_ppb and sensor_id == 8) or (
                receive_hcho_in_ppb and sensor_id == 7
            ):
                self._units[sensor_id] = CONCENTRATION_PARTS_PER_BILLION
            else:
                self._units[sensor_id] = data[1]

    @property
    def unique_id(self) -> str:
        """Return a controller unique ID."""
        return self._username

    @property
    def name(self) -> str:
        """Get account name."""
        return self._username

    @property
    def name_secure(self) -> str:
        """Get account name (secure version)."""
        return mask_email(self._username)

    @property
    def available(self) -> bool:
        """Return True if account is available."""
        return self.is_connected

    @property
    def units(self) -> dict:
        """Get list of units for sensors."""
        return self._units

    @staticmethod
    def _get_useragent(query_type) -> str:
        """Generate User-Agent for requests."""
        # pylint: disable=R1705
        if query_type == QUERY_TYPE_API:
            return USERAGENT_API
        elif query_type == QUERY_TYPE_DEVICE:
            return USERAGENT_DEVICE
        else:
            raise ValueError('Unknown query type "%s"' % query_type)

    def _add_url_params(self, url: str, extra_params: dict):
        """Add params to URL."""
        params = self.params.copy()
        params.update(extra_params)

        req = PreparedRequest()
        req.prepare_url(url, params)

        return req.url

    def _get_url(self, query_type, function: str, extra_params=None) -> str:
        """Generate request URL."""
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
    def _query(self, query_type, function: str, extra_params=None) -> Optional[dict]:
        """Query data from cloud."""
        url = self._get_url(query_type, function)
        _LOGGER.debug("Querying %s", url)

        response = None

        # allow to override params when necessary
        # and update self.params globally for the next connection
        params = self.params.copy()
        if query_type == QUERY_TYPE_DEVICE:
            params["saveToken"] = params["safeToken"]
            del params["safeToken"]
        if extra_params:
            params.update(extra_params)

        try:
            ret = self._session.get(
                url,
                params=params,
                headers={"User-Agent": self._get_useragent(query_type)},
                timeout=QUERY_TIMEOUT,
            )
            _LOGGER.debug("_query ret %s", ret.status_code)

        # pylint: disable=broad-except
        except Exception as err_msg:
            _LOGGER.error("Error! %s", err_msg)
            return None

        if ret.status_code == 200 or ret.status_code == 204:
            response = ret

        if response is None:  # pragma: no cover
            _LOGGER.debug(MSG_GENERIC_FAIL)
            return None

        _LOGGER.debug(response.content)
        if response.content.startswith(b"jsoncallback("):
            response = json.loads(response.content[13:-1])
        else:
            response = json.loads(response.content)

        if query_type == QUERY_TYPE_API:
            if response["code"] == 102:
                _LOGGER.error(MSG_LOGIN_FAIL)
                return None
            if response["code"] == 9999:
                _LOGGER.error(MSG_BUSY)
                return None
            if response["code"] != 2000:
                _LOGGER.error(MSG_GENERIC_FAIL)
                return None
        elif query_type == QUERY_TYPE_DEVICE:
            if int(response["returnCode"]) != 0:
                _LOGGER.error(MSG_GENERIC_FAIL)
                self.params["uid"] = -1000
                return None
        else:
            raise ValueError('Unknown query type "%s"' % query_type)

        return response

    @property
    def is_connected(self):
        """Return True if connected to account."""
        return self.params["uid"] > 0

    def connect(self, force=False) -> bool:
        """(Re)Connect to account and return connection status."""
        if not force and self.params["uid"] > 0:
            return True

        _LOGGER.debug("Connecting to cloud server%s", " (FORCE mode)" if force else "")

        self.params["uid"] = -1000
        self.params["safeToken"] = "anonymous"
        ret = self._query(
            QUERY_TYPE_API,
            "loginByEmail",
            extra_params={
                "chr": "clt",
                "email": self._username,
                "password": self._password,
                "os": 2,
            },
        )
        if not ret:
            return self.connect(True) if not force else False

        self.params["uid"] = ret["uid"]
        self.params["safeToken"] = ret["safeToken"]
        self._devices = {}

        self._mqtt_connect()

        return True

    def _mqtt_connect(self):
        _LOGGER.debug("Start connecting to cloud MQTT-server")
        if self._mqtt is not None or not self.is_connected:
            return

        # pylint: disable=unused-argument
        def on_connect_callback(client, userdata, flags, res):
            _LOGGER.debug("Connected to MQTT")
            try:
                self._mqtt_subscribe(self._get_devices_mqtt_topics(self.active_devices))
            except Exception as exc:  # pylint: disable=broad-except
                logging.exception(exc)

        # pylint: disable=unused-argument
        def on_message_callback(client, userdata, message):
            try:
                msg = json.loads(message.payload)
                _LOGGER.debug("Received MQTT message: %s", msg)
                self._mqtt_process_message(msg)
            except Exception as exc:  # pylint: disable=broad-except
                logging.exception(exc)

        self._mqtt = mqtt.Client(
            client_id="_".join(
                (str(self.params["uid"]), str(int(dt_util.now().timestamp() * 1000)))
            ),
            clean_session=True,
        )
        self._mqtt.enable_logger(_LOGGER_MQTT)
        self._mqtt.on_connect = on_connect_callback
        self._mqtt.on_message = on_message_callback
        parsed = urlparse(MQTT_URL)
        if parsed.username is not None:
            if parsed.password is not None:
                self._mqtt.username_pw_set(parsed.username, parsed.password)
            else:
                _LOGGER.error(
                    "The MQTT password was not found, this is required for auth"
                )
        self._mqtt.connect_async(host=parsed.hostname, port=parsed.port)
        self._mqtt.loop_start()

    def _mqtt_subscribe(self, topics: list):
        if self._mqtt.is_connected():
            self._mqtt.subscribe([(x, 0) for x in topics])

    def _mqtt_unsubscribe(self, topics: list):
        if self._mqtt.is_connected():
            self._mqtt.unsubscribe(topics)

    def _mqtt_process_message(self, message: dict):
        device_id = None
        for dev_id, dev in self.devices.items():
            if message["deviceToken"] == dev["deviceToken"]:
                device_id = dev_id
        if device_id is None:
            return

        if message["type"] == "V":
            _LOGGER.debug("Update sensors for device %d", device_id)
            self._extract_sensors_data(
                device_id,
                int(dt_util.now().timestamp()),
                json.loads(message["content"]),
            )

        elif message["type"] == "C":
            _LOGGER.debug("Update online status for device %d", device_id)
            if self.devices.get(device_id) is None:
                return
            self.devices[device_id]["onlinestat"] = message["content"]

        else:
            _LOGGER.warning("Unknown message type: %s", message)
            return

        if self.hass:
            dispatcher_send(self.hass, SIGNAL_UPDATE_JQ300)

    def _get_devices_mqtt_topics(self, device_ids: list) -> list:
        devs = self.update_devices()
        topics = list(
            (devs[dev_id]["deviceToken"] for dev_id in device_ids) if devs else ()
        )
        return topics

    @property
    def active_devices(self) -> list:
        """Get list of devices we want to fetch sensors data."""
        return self._active_devices

    @active_devices.setter
    def active_devices(self, devices: list):
        """Set list of devices we want to fetch sensors data."""
        unsub = self._get_devices_mqtt_topics(
            list(set(self._active_devices) - set(devices))
        )
        sub = self._get_devices_mqtt_topics(
            list(set(devices) - set(self._active_devices))
        )

        self._active_devices = devices

        for device_id in devices:
            self._sensors.setdefault(device_id, {})

        _LOGGER.debug("Unsubscribe from MQTT topics: %s", ", ".join(unsub))
        self._mqtt_unsubscribe(unsub)
        _LOGGER.debug("Subscribe for new MQTT topics: %s", ", ".join(sub))
        self._mqtt_subscribe(sub)

    @property
    def devices(self) -> dict:
        """Get available devices."""
        return self._devices

    def update_devices(self, force=False) -> Optional[Dict[int, Dict[str, Any]]]:
        """Update available devices."""
        if not self.connect():
            _LOGGER.error("Can't connect to cloud.")
            return None

        if not force and self._devices:
            return self._devices

        _LOGGER.debug("Updating devices list for account %s", self.name_secure)

        ret = self._query(
            QUERY_TYPE_API,
            "deviceManager",
            extra_params={
                "platform": "android",
                "clientType": 2,
                "action": "deviceManager",
            },
        )
        if not ret:
            return self.update_devices(True) if not force else None

        tstamp = int(dt_util.now().timestamp() * 1000)
        for dev in ret["deviceInfoBodyList"]:
            dev[""] = tstamp
            self._devices[dev["deviceid"]] = dev

        for device_id in self._devices:
            self._sensors.setdefault(device_id, {})

        return self._devices

    async def async_update_devices_or_timeout(self, timeout=UPDATE_TIMEOUT):
        """Get available devices list from cloud."""
        try:
            with async_timeout.timeout(timeout):
                start = monotonic()
                await self.hass.async_add_job(self.update_devices)
                while not self._devices:
                    # Waiting for connection and check datas ready
                    await asyncio.sleep(1)

                return self._devices

        except asyncio.TimeoutError as exc:
            _LOGGER.error("Timeout fetching %s devices list", self.name_secure)
            raise CannotConnect from exc

        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unexpected error fetching %s devices list: %s", self.name_secure, err
            )

        finally:
            _LOGGER.debug(
                "Finished fetching %s devices list in %.3f seconds",
                self.name_secure,
                monotonic() - start,
            )

    def device_available(self, device_id) -> bool:
        """Return True if device is available."""
        return (
            self.available and self.devices.get(device_id, {}).get("onlinestat") == "1"
        )

    def _extract_sensors_data(self, device_id, ts_now: int, sensors: dict):
        res = {}
        for sensor in sensors:
            sensor_id = sensor["seq"]
            if sensor["content"] is None or (
                sensor_id not in SENSORS.keys()
                and sensor_id not in BINARY_SENSORS.keys()
            ):
                continue

            res[sensor_id] = float(sensor["content"])
            if sensor_id == 8 and self._receive_tvoc_in_ppb:
                res[sensor_id] *= 1000 * 24.45 / MWEIGTH_TVOC
            elif sensor_id == 7 and self._receive_hcho_in_ppb:
                res[sensor_id] *= 1000 * 24.45 / MWEIGTH_HCHO
            if self._units[sensor_id] != CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER:
                res[sensor_id] = int(res[sensor_id])

        self._sensors[device_id][ts_now] = res
        self._sensors_raw[device_id] = res
        self._sensors_last_update = ts_now

    @Throttle(timedelta(minutes=10))
    def update_sensors(self, _=None):
        """Update current states of all active devices for account."""
        _LOGGER.debug("Updating sensors state for account %s", self.name_secure)

        ts_now = int(dt_util.now().timestamp())

        for device_id in self.active_devices:
            if self.get_sensors_raw(device_id) is not None:
                continue

            ret = self._query(
                QUERY_TYPE_DEVICE,
                "list",
                extra_params={
                    "deviceToken": self.devices[device_id]["deviceToken"],
                    "timestamp": ts_now,
                    "callback": "jsoncallback",
                    "_": ts_now,
                },
            )
            if not ret:
                return False

            self._extract_sensors_data(device_id, ts_now, ret["deviceValueVos"])

        if self.hass:
            dispatcher_send(self.hass, SIGNAL_UPDATE_JQ300)

    @Throttle(timedelta(minutes=10))
    async def async_update_sensors_or_timeout(self, timeout=UPDATE_TIMEOUT):
        """Update current states of all active devices for account."""
        try:
            with async_timeout.timeout(timeout):
                start = monotonic()
                await self.hass.async_add_job(self.update_sensors)
                while self._sensors_last_update < start:
                    # Waiting for connection and check datas ready
                    await asyncio.sleep(1)

        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout fetching %s device's sensors", self.name_secure)
            raise CannotConnect from err

        except Exception as err:  # pylint: disable=broad-except
            _LOGGER.exception(
                "Unexpected error fetching %s device's sensors: %s",
                self.name_secure,
                err,
            )

        finally:
            _LOGGER.debug(
                "Finished fetching %s device's sensors in %.3f seconds",
                self.name_secure,
                monotonic() - start,
            )

    def get_sensors_raw(self, device_id) -> Optional[dict]:
        """Get raw values of states of available sensors for device."""
        return self._sensors_raw.get(device_id)

    def get_sensors(self, device_id) -> Optional[dict]:
        """Get states of available sensors for device."""
        ts_now = int(dt_util.now().timestamp())
        ts_overdue = ts_now - SENSORS_FILTER_FRAME.total_seconds()

        self._sensors.setdefault(device_id, {})

        # Filter historic states
        res = {}
        ts_min = max(
            list(filter(lambda x: x <= ts_overdue, self._sensors[device_id].keys()))
            or {ts_overdue}
        )
        # _LOGGER.debug('ts_overdue: %s; ts_min: %s', ts_overdue, ts_min)
        for m_ts, val in self._sensors[device_id].items():
            if m_ts >= ts_min:
                res[m_ts] = val
        self._sensors[device_id] = res

        if not self._sensors[device_id]:
            return None

        # Calculate average state values
        res = {}
        last_ts = ts_overdue
        last_data: Dict[int, float] = {}
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
            1, ts_now - max(min(self._sensors[device_id].keys()), ts_overdue) + 1
        )
        # _LOGGER.debug('Averaging: %s / %s', res, length)
        for sensor_id in res:
            tmp = SENSORS.get(sensor_id)
            rnd = tmp[5] if tmp else 0
            res[sensor_id] = (
                self._sensors_raw[device_id][1]
                if sensor_id == 1
                else int(res[sensor_id] / length)
                if rnd == 0
                or self._units[sensor_id]
                in (CONCENTRATION_PARTS_PER_MILLION, CONCENTRATION_PARTS_PER_BILLION)
                else round(res[sensor_id] / length, rnd)
            )
        # _LOGGER.debug('Result: %s', res)
        return res
