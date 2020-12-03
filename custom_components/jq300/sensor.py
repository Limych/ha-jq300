"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

#  Copyright (c) 2020, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

import logging
from time import sleep

from homeassistant import exceptions
from homeassistant.components.sensor import ENTITY_ID_FORMAT
from homeassistant.const import CONF_DEVICES
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity, async_generate_entity_id

from . import JqAccount, CannotConnect
from .const import (
    SENSORS,
    ATTR_RAW_STATE,
    DOMAIN,
    ATTR_DEVICE_BRAND,
    ATTR_DEVICE_MODEL,
    ATTR_DEVICE_ID,
    ACCOUNT_CONTROLLER,
    CONF_ACCOUNT_ID,
    SIGNAL_UPDATE_JQ300,
)

_LOGGER = logging.getLogger(__name__)


# pylint: disable=unused-argument
async def async_setup_platform(
    hass, config, async_add_entities, discovery_info=None
) -> bool:
    """Set up a sensors to integrate JQ-300."""
    if discovery_info is None:
        return True

    domain_data = hass.data[DOMAIN][discovery_info[CONF_ACCOUNT_ID]]
    account = domain_data[ACCOUNT_CONTROLLER]  # type: JqAccount
    devices = domain_data[CONF_DEVICES]  # type: dict

    _LOGGER.debug("Setup sensors for account %s", account.name_secure)

    try:
        await account.async_update_sensors_or_timeout()
    except CannotConnect:
        return False

    entities = []
    for dev_name, dev_id in devices.items():
        sensors = account.get_sensors(dev_id)
        while not sensors:
            _LOGGER.debug("Sensors list is not ready. Wait for 3 sec...")
            sleep(3)
            sensors = account.get_sensors(dev_id)

        for sensor_id, sensor_state in sensors.items():
            if sensor_id not in SENSORS.keys():
                continue
            ent_name = SENSORS[sensor_id][4] or SENSORS[sensor_id][0]
            entity_id = async_generate_entity_id(
                ENTITY_ID_FORMAT, "_".join((dev_name, ent_name)), hass=hass
            )
            _LOGGER.debug("Initialize %s", entity_id)
            entities.append(
                JqSensor(entity_id, account, dev_id, sensor_id, sensor_state)
            )

    async_add_entities(entities)

    return True


# pylint: disable=too-many-instance-attributes
class JqSensor(Entity):
    """A sensor implementation for JQ device."""

    def __init__(
        self, entity_id, account: JqAccount, device_id, sensor_id, sensor_state
    ):
        """Initialize a sensor."""
        super().__init__()

        self.entity_id = entity_id

        device = account.update_devices()
        if device is None:
            raise exceptions.PlatformNotReady

        self._account = account
        self._device = device.get(device_id, {})
        self._device_id = device_id
        self._unique_id = "{}-{}-{}".format(
            self._account.unique_id, device_id, sensor_id
        )
        self._name = "{} {}".format(self._device.get("pt_name"), SENSORS[sensor_id][0])
        self._sensor_id = sensor_id
        self._state = sensor_state
        self._state_raw = sensor_state
        self._units = self._account.units[sensor_id]
        self._icon = SENSORS[sensor_id][2]
        self._device_class = SENSORS[sensor_id][3]

    async def async_added_to_hass(self):
        """Register callbacks."""
        self.async_on_remove(
            async_dispatcher_connect(
                self.hass, SIGNAL_UPDATE_JQ300, self._update_callback
            )
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._account.device_available(self._device_id)

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def unique_id(self):
        """Return a unique ID."""
        return self._unique_id

    @property
    def device_class(self):
        """Return the class of the sensor."""
        return self._device_class

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        return {
            ATTR_DEVICE_BRAND: self._device.get("brandname"),
            ATTR_DEVICE_MODEL: self._device.get("pt_model"),
            ATTR_DEVICE_ID: self._device.get("deviceid"),
            ATTR_RAW_STATE: self._state_raw,
        }

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def unit_of_measurement(self):
        """Return the units of measurement."""
        return self._units

    @property
    def should_poll(self):
        """Return the polling state."""
        return False

    def update(self):
        """Update the sensor state if it needed."""
        ret = self._account.get_sensors(self._device_id)
        if ret:
            self._state = ret[self._sensor_id]
            self._state_raw = self._account.get_sensors_raw(self._device_id)[
                self._sensor_id
            ]
            _LOGGER.debug(
                "Update state: %s = %s (%s)",
                self.entity_id,
                self._state,
                self._state_raw,
            )
