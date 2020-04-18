"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

import logging

from homeassistant.const import CONF_NAME

from .const import DATA_JQ300

_LOGGER = logging.getLogger(__name__)


# pylint: disable=w0613
async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up a sensors to integrate JQ-300."""
    if discovery_info is None:
        return

    object_id = discovery_info[CONF_NAME]
    controller = hass.data[DATA_JQ300][object_id]

    sensors = []
    # TODO
    # for sensor_type in discovery_info[CONF_SENSORS]:
    #     _LOGGER.debug('Initialize sensor %s for controller %s', sensor_type,
    #                   object_id)
    #     sensors.append(IaqukSensor(hass, controller, sensor_type))

    async_add_entities(sensors, True)
