#  Copyright (c) 2020-2021, Andrey "Limych" Khrolenok <andrey@khrolenok.ru>
#  Creative Commons BY-NC-SA 4.0 International Public License
#  (see LICENSE.md or https://creativecommons.org/licenses/by-nc-sa/4.0/)

"""
Integration of the JQ-300/200/100 indoor air quality meter.

For more details about this component, please refer to
https://github.com/Limych/ha-jq300
"""

from homeassistant import config_entries

# pylint: disable=unused-import
from .const import DOMAIN


class Jq300FlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Jq300."""

    VERSION = 1
    CONNECTION_CLASS = config_entries.CONN_CLASS_CLOUD_POLL

    def __init__(self):
        """Initialize."""
        self._errors = {}

    async def async_step_import(self, platform_config):
        """Import a config entry.

        Special type of import, we're not actually going to store any data.
        Instead, we're going to rely on the values that are in config file.
        """
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        return self.async_create_entry(title="configuration.yaml", data=platform_config)


#
#     async def async_step_user(self, user_input=None):
#         """Handle a flow initialized by the user."""
#         self._errors = {}
#
#         # Uncomment the next 2 lines if only a single instance of the integration is allowed:
#         # if self._async_current_entries():
#         #     return self.async_abort(reason="single_instance_allowed")     # noqa: E800
#
#         if user_input is not None:
#             valid = await self._test_credentials(
#                 user_input[CONF_USERNAME], user_input[CONF_PASSWORD]
#             )
#             if valid:
#                 return self.async_create_entry(
#                     title=user_input[CONF_USERNAME], data=user_input
#                 )
#
#             self._errors["base"] = "auth"
#
#         return await self._show_config_form(user_input)
#
#     @staticmethod
#     @callback
#     def async_get_options_flow(config_entry):
#         """Get component options flow."""
#         return Jq300OptionsFlowHandler(config_entry)
#
#     async def _show_config_form(self, user_input):  # pylint: disable=unused-argument
#         """Show the configuration form to edit location data."""
#         return self.async_show_form(
#             step_id="user",
#             data_schema=vol.Schema(
#                 {vol.Required(CONF_USERNAME): str, vol.Required(CONF_PASSWORD): str}
#             ),
#             errors=self._errors,
#         )
#
#     async def _test_credentials(self, username, password):
#         """Return true if credentials is valid."""
#         try:
#             session = async_create_clientsession(self.hass)
#             client = JqApiClient(username, password, session)
#             await client.async_get_data()
#             return True
#         except Exception:  # pylint: disable=broad-except
#             pass
#         return False
#
#
# class Jq300OptionsFlowHandler(config_entries.OptionsFlow):
#     """Jq300 config flow options handler."""
#
#     def __init__(self, config_entry):
#         """Initialize HACS options flow."""
#         self.config_entry = config_entry
#         self.options = dict(config_entry.options)
#
#     async def async_step_init(self, user_input=None):  # pylint: disable=unused-argument
#         """Manage the options."""
#         return await self.async_step_user()
#
#     async def async_step_user(self, user_input=None):
#         """Handle a flow initialized by the user."""
#         if user_input is not None:
#             self.options.update(user_input)
#             return await self._update_options()
#
#         return self.async_show_form(
#             step_id="user",
#             data_schema=vol.Schema(
#                 {
#                     vol.Required(x, default=self.options.get(x, True)): bool
#                     for x in sorted(PLATFORMS)
#                 }
#             ),
#         )
#
#     async def _update_options(self):
#         """Update config entry options."""
#         return self.async_create_entry(
#             title=self.config_entry.data.get(CONF_USERNAME), data=self.options
#         )
