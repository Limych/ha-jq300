"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

import logging

import voluptuous as vol

from .const import DOMAIN, VERSION, ISSUE_URL, SUPPORT_LIB_URL, DATA_JQ300

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    # DOMAIN: cv.schema_with_slug_keys(IAQ_SCHEMA),
}, extra=vol.ALLOW_EXTRA)


def _deslugify(string):
    return string.replace('_', ' ').title()


async def async_setup(hass, config):
    """Set up component."""
    # Print startup message
    _LOGGER.info('Version %s', VERSION)
    _LOGGER.info('If you have ANY issues with this,'
                 ' please report them here: %s', ISSUE_URL)

    # TODO

    return True
