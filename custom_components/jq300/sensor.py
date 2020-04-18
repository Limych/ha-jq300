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

import logging

from homeassistant.const import CONF_NAME, CONF_USERNAME, CONF_DEVICE_ID
from homeassistant.helpers.entity import Entity

from custom_components.jq300 import JqController
from .const import DATA_JQ300, SENSOR_IDS, ATTR_DEVICE_ID

_LOGGER = logging.getLogger(__name__)


# pylint: disable=w0613
async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a sensors to integrate JQ-300."""
    if discovery_info is None:
        return

    account_id = discovery_info[CONF_USERNAME]
    device_id = discovery_info[CONF_DEVICE_ID]

    controller = hass.data[DATA_JQ300][account_id]  # type: JqController
    device = controller.get_devices_list()[device_id]
    sensors_data = controller.get_sensors(device_id)

    sensors = []
    for sensor_id, sensor_value in sensors_data:
        _LOGGER.debug('Initialize sensor %s for device %s for account %s',
                      SENSOR_IDS[sensor_id], device['pt_name'], account_id)
        sensors.append(JqSensor(hass, controller, sensor_id, sensor_value))

    async_add_entities(sensors, True)


class JqSensor(Entity):
    """A sensor implementation for JQ device"""

    def __init__(self, hass, controller, sensor_id, sensor_state):
        """Initialize a sensor"""
        super().__init__()

        self._controller = controller  # type: JqController
        self._sensor_id = sensor_id
        self._name = "{0} {1}".format(
            controller.name, SENSOR_IDS.get(sensor_id)[0])
        self._state = sensor_state
        self._units = SENSOR_IDS.get(sensor_id)[1]
        self._icon = 'mdi:{}'.format(SENSOR_IDS.get(sensor_id)[2])
        self._unique_id = '{}-{}'.format(self._controller.unique_id, sensor_id)
        self._device_class = SENSOR_IDS.get(sensor_id)[3]

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._controller.available

    # todo
    # @property
    # @Throttle(timedelta(seconds=5))
    # def available(self) -> bool:
    #     """Return True if device is available."""
    #     # available = self._device.available
    #     # if self._available != available:
    #     #     self._available = available
    #     #     _LOGGER.warning('Device "%s" is %s', self._name,
    #     #                     'reconnected' if available else 'unavailable')
    #     return self._available

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
        attrs = {
            ATTR_DEVICE_ID: self._controller.unique_id,
        }
        return attrs

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
        return True

    def update(self):
        """Update the sensor state if it needed."""
        ret = self._controller.get_sensors(self._sensor_id)
        if ret:
            self._state = ret[self._sensor_id]
