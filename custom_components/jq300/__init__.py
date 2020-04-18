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
import requests
import voluptuous as vol
from homeassistant.const import CONF_USERNAME, CONF_PASSWORD, CONF_NAME
from requests import Response, PreparedRequest

from .const import DOMAIN, VERSION, ISSUE_URL, SUPPORT_LIB_URL, DATA_JQ300, \
    QUERY_TYPE_API, QUERY_TYPE_DEVICE, QUERY_METHOD_GET, BASE_URL_API, \
    BASE_URL_DEVICE, USERAGENT_API, USERAGENT_DEVICE, QUERY_TIMEOUT, \
    MSG_GENERIC_FAIL, MSG_LOGIN_FAIL

_LOGGER = logging.getLogger(__name__)

ACCOUNT_SCHEMA = vol.Schema({
    vol.Required(CONF_USERNAME): cv.string,
    vol.Required(CONF_PASSWORD): cv.string,
    vol.Optional(CONF_NAME): cv.string,
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
        name = account_config.get(CONF_NAME, username)

        if username in list(hass.data[DATA_JQ300]):
            _LOGGER.error('Duplicate account! '
                          'Account "%s" is already exists.', username)
            continue

        controller = JqController(hass, name, username, password)
        hass.data[DATA_JQ300][username] = controller
        _LOGGER.info('Connected to account "%s" as %s',
                     controller.name, username)

    if not hass.data[DATA_JQ300]:
        return False

    return True


class JqController:
    """JQ device controller"""

    def __init__(self, hass, name, username, password):
        """Initialize configured device."""
        self.hass = hass
        self.params = {
            'uid': -1000,
            'safeToken': 'anonymous',
        }

        self._name = name
        self._username = username
        self._password = password

        self._available = False
        self._session = requests.session()

        self._login()

    @property
    def unique_id(self):
        """Return a device unique ID."""
        return self._username

    @property
    def name(self):
        """Get custom device name."""
        return self._name

    @property
    def available(self) -> bool:
        """Return True if device is available."""
        # available = self._device.available
        # if self._available != available:
        #     self._available = available
        #     _LOGGER.warning('Device "%s" is %s', self._name,
        #                     'reconnected' if available else 'unavailable')
        return self._available

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

    def query(self, query_type, function: str, method=QUERY_METHOD_GET,
              extra_params=None) -> Optional[Response]:
        """Query data from cloud."""
        url = self._get_url(query_type, function)
        _LOGGER.debug("Querying %s %s", method.upper(), url)

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
            req = self._session.request(method, url, params=params, headers={
                'User-Agent': self._get_useragent(query_type)
            }, timeout=QUERY_TIMEOUT)
            _LOGGER.debug("_query ret %s", req.status_code)

        except Exception as err_msg:
            _LOGGER.error("Error! %s", err_msg)
            raise

        if req.status_code == 200 or req.status_code == 204:
            response = req

        if response is None:  # pragma: no cover
            _LOGGER.debug(MSG_GENERIC_FAIL)
        return response

    def _login(self):
        ret = self.query(QUERY_TYPE_API, 'loginByEmail', extra_params={
            'chr': 'clt',
            'email': self._username,
            'password': self._password,
            'os': 2
        })
        if not ret:
            return

        ret = json.loads(ret.content)

        if ret['code'] == 102:
            _LOGGER.error(MSG_LOGIN_FAIL)
        if ret['code'] != 2000:
            _LOGGER.error(MSG_GENERIC_FAIL)

        self.params['uid'] = ret['uid']
        self.params['safeToken'] = ret['safeToken']
