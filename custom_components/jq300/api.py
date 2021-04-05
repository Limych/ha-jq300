"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

#  Copyright (c) 2020-2021, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

import asyncio
import json
import logging
from datetime import timedelta
from time import monotonic, sleep
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import async_timeout
import homeassistant.util.dt as dt_util
import paho.mqtt.client as mqtt
import requests
from aiohttp import ClientSession
from homeassistant.const import (
    CONCENTRATION_MILLIGRAMS_PER_CUBIC_METER,
    CONCENTRATION_PARTS_PER_BILLION,
    CONCENTRATION_PARTS_PER_MILLION,
    CONF_UNIT_OF_MEASUREMENT,
    HTTP_OK,
)
from homeassistant.core import HomeAssistant
from homeassistant.util import Throttle
from requests import PreparedRequest

from .const import (
    AVAILABLE_TIMEOUT,
    BINARY_SENSORS,
    CONF_PRECISION,
    HTTP_NO_CONTENT,
    MWEIGTH_HCHO,
    MWEIGTH_TVOC,
    QUERY_TIMEOUT,
    SENSORS,
    SENSORS_FILTER_FRAME,
    UPDATE_TIMEOUT,
)
from .util import mask_email

_LOGGER = logging.getLogger(__name__)

# Error strings
MSG_GENERIC_FAIL = "Sorry.. Something went wrong..."
MSG_LOGIN_FAIL = "Account name or password is wrong, please try again"
MSG_BUSY = "The system is busy"

QUERY_TYPE_API = "API"
QUERY_TYPE_DEVICE = "DEVICE"

BASE_URL_API = "http://www.youpinyuntai.com:32086/ypyt-api/api/app/"
BASE_URL_DEVICE = "https://www.youpinyuntai.com:31447/device/"
MQTT_URL = "mqtt://ye5h8c3n:T%4ran8c@www.youpinyuntai.com:55450"

_USERAGENT_SYSTEM = "Android 6.0.1; RedMi Note 5 Build/RB3N5C"
USERAGENT_API = "Dalvik/2.1.0 (Linux; U; %s)" % _USERAGENT_SYSTEM
USERAGENT_DEVICE = (
    "Mozilla/5.0 (Linux; %s; wv) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Version/4.0 "
    "Chrome/68.0.3440.91 Mobile Safari/537.36" % _USERAGENT_SYSTEM
)


class ApiError(Exception):
    """Raised when API request ended in error."""

    def __init__(self, status):
        """Initialize."""
        super().__init__(status)
        self.status = status


# pylint: disable=too-many-instance-attributes
class Jq300Account:
    """JQ-300 cloud account controller."""

    # pylint: disable=too-many-arguments
    def __init__(
        self,
        hass: HomeAssistant,
        session: ClientSession,
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
        self._session = session
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

        for sensor_id, data in BINARY_SENSORS.items():
            self._units[sensor_id] = None

        for sensor_id, data in SENSORS.items():
            if (receive_tvoc_in_ppb and sensor_id == 8) or (
                receive_hcho_in_ppb and sensor_id == 7
            ):
                self._units[sensor_id] = CONCENTRATION_PARTS_PER_BILLION
            else:
                self._units[sensor_id] = data.get(CONF_UNIT_OF_MEASUREMENT)

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
        if query_type == QUERY_TYPE_API:
            return USERAGENT_API

        if query_type == QUERY_TYPE_DEVICE:
            return USERAGENT_DEVICE

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

    # pylint: disable=too-many-return-statements,too-many-branches
    async def _async_query(
        self, query_type, function: str, extra_params=None
    ) -> Optional[dict]:
        """Query data from cloud."""
        url = self._get_url(query_type, function)
        _LOGGER.debug("Requesting URL %s", url)

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

        if ret.status_code == HTTP_OK or ret.status_code == HTTP_NO_CONTENT:
            response = ret

        if response is None:  # pragma: no cover
            _LOGGER.debug(MSG_GENERIC_FAIL)
            return None

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
        else:
            if int(response["returnCode"]) != 0:
                _LOGGER.error(MSG_GENERIC_FAIL)
                self.params["uid"] = -1000
                return None

        return response

    @property
    def is_connected(self) -> bool:
        """Return True if connected to account."""
        return self.params["uid"] > 0

    async def async_connect(self, force: bool = False) -> bool:
        """(Re)Connect to account and return connection status."""
        if not force and self.params["uid"] > 0:
            return True

        _LOGGER.debug("Connecting to cloud server%s", " (FORCE mode)" if force else "")

        self.params["uid"] = -1000
        self.params["safeToken"] = "anonymous"
        ret = await self._async_query(
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
            return await self.async_connect(True) if not force else False

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
        self._mqtt.enable_logger(_LOGGER)
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
            if self.devices.get(device_id) is None:
                return
            online = int(message["content"])
            _LOGGER.debug("Update online status for device %d: %d", device_id, online)
            if online != self.devices[device_id].get("onlinestat"):
                self.devices[device_id]["onlinets"] = monotonic()
            self.devices[device_id]["onlinestat"] = online

        else:
            _LOGGER.warning("Unknown message type: %s", message)

    def _get_devices_mqtt_topics(self, device_ids: list) -> list:
        if not self.devices:
            self.hass.add_job(self.async_update_devices())
            sleep(1)

        if not self.devices:
            return []

        return list(self.devices[dev_id]["deviceToken"] for dev_id in device_ids)

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

    async def async_update_devices(
        self, force=False
    ) -> Optional[Dict[int, Dict[str, Any]]]:
        """Update available devices."""
        if not await self.async_connect():
            _LOGGER.error("Can't connect to cloud.")
            return None

        if not force and self._devices:
            return self._devices

        _LOGGER.debug("Updating devices list for account %s", self.name_secure)

        ret = await self._async_query(
            QUERY_TYPE_API,
            "deviceManager",
            extra_params={
                "platform": "android",
                "clientType": 2,
                "action": "deviceManager",
            },
        )
        if not ret:
            return await self.async_update_devices(True) if not force else None

        tstamp = int(dt_util.now().timestamp() * 1000)
        for dev in ret["deviceInfoBodyList"]:
            dev[""] = tstamp
            dev["onlinets"] = monotonic()
            self._devices[dev["deviceid"]] = dev

        for device_id in self._devices:
            self._sensors.setdefault(device_id, {})

        return self._devices

    async def async_update_devices_or_timeout(self, timeout=UPDATE_TIMEOUT):
        """Get available devices list from cloud."""
        start = monotonic()
        try:
            with async_timeout.timeout(timeout):
                return await self.async_update_devices()

        except TimeoutError as exc:
            _LOGGER.error("Timeout fetching %s devices list", self.name_secure)
            raise exc

        finally:
            _LOGGER.debug(
                "Finished fetching %s devices list in %.3f seconds",
                self.name_secure,
                monotonic() - start,
            )

    def device_available(self, device_id) -> bool:
        """Return True if device is available."""
        dev = self.devices.get(device_id, {})
        device_available = dev.get("onlinestat") == 1
        device_timeout = (monotonic() - dev.get("onlinets", 0)) <= AVAILABLE_TIMEOUT
        online = self.available and device_available and device_timeout

        # pylint: disable=logging-too-many-args
        _LOGGER.debug(
            "Availability: %s (account) AND %s (device %s) AND %s (timeout) = %s",
            self.available,
            device_available,
            device_id,
            device_timeout,
            online,
        )

        return online

    def _extract_sensors_data(self, device_id, ts_now: int, sensors: dict):
        res = {}
        for sensor in sensors:
            sensor_id = sensor["seq"]
            if sensor["content"] is None or (
                sensor_id not in SENSORS and sensor_id not in BINARY_SENSORS
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

    @Throttle(timedelta(minutes=10))
    async def async_update_sensors(self):
        """Update current states of all active devices for account."""
        _LOGGER.debug("Updating sensors state for account %s", self.name_secure)

        ts_now = int(dt_util.now().timestamp())

        for device_id in self.active_devices:
            if self.get_sensors_raw(device_id) is not None:
                continue

            ret = await self._async_query(
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
                return

            self._extract_sensors_data(device_id, ts_now, ret["deviceValueVos"])

    @Throttle(timedelta(minutes=10))
    async def async_update_sensors_or_timeout(self, timeout=UPDATE_TIMEOUT):
        """Update current states of all active devices for account."""
        start = monotonic()
        try:
            with async_timeout.timeout(timeout):
                await self.async_update_sensors()

        except asyncio.TimeoutError as err:
            _LOGGER.error("Timeout fetching %s device's sensors", self.name_secure)
            raise err

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
            rnd = SENSORS.get(sensor_id, {}).get(CONF_PRECISION, 0)
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
