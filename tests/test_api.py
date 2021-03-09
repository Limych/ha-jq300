# pylint: disable=protected-access
"""Tests for integration_blueprint api."""

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest import raises

from custom_components.jq300.api import (
    QUERY_TYPE_API,
    QUERY_TYPE_DEVICE,
    USERAGENT_API,
    USERAGENT_DEVICE,
    Jq300Account,
)


async def test_init(hass: HomeAssistant):
    """Test API initialization."""
    session = async_get_clientsession(hass)
    api = Jq300Account(hass, session, "test@email.com", "test_password", False, False)

    expected_units = {
        1: None,
        4: "°C",
        5: "%",
        6: "µg/m³",
        7: "mg/m³",
        8: "mg/m³",
        9: "ppm",
    }

    assert isinstance(USERAGENT_API, str) and len(USERAGENT_API) > 20
    assert isinstance(USERAGENT_DEVICE, str) and len(USERAGENT_DEVICE) > 20

    assert api.unique_id == "test@email.com"
    assert api.name == "test@email.com"
    assert api.name_secure == "te*t@em**l.com"
    assert api.available is False
    assert api.units == expected_units
    assert api._get_useragent(QUERY_TYPE_API) == USERAGENT_API
    assert api._get_useragent(QUERY_TYPE_DEVICE) == USERAGENT_DEVICE
    with raises(ValueError):
        _ = api._get_useragent("")
    assert (
        api._add_url_params("http://some/url", {"extra": 1})
        == "http://some/url?uid=-1000&safeToken=anonymous&extra=1"
    )
    assert (
        api._add_url_params("http://some/url", {"extra": 1, "par": 2})
        == "http://some/url?uid=-1000&safeToken=anonymous&extra=1&par=2"
    )
    assert (
        api._get_url(QUERY_TYPE_API, "func")
        == "http://www.youpinyuntai.com:32086/ypyt-api/api/app/func"
    )
    assert (
        api._get_url(QUERY_TYPE_DEVICE, "func")
        == "https://www.youpinyuntai.com:31447/device/func"
    )
    assert (
        api._get_url(QUERY_TYPE_DEVICE, "func", {"extra": 1})
        == "https://www.youpinyuntai.com:31447/device/func?uid=-1000&safeToken=anonymous&extra=1"
    )
    with raises(ValueError):
        _ = api._get_url("", "func")


# async def test__async_query(hass: HomeAssistant, aioclient_mock, caplog):
#     """Test HTTP requesting."""
#     session = async_get_clientsession(hass)
#     api = Jq300Account(hass, session, "test@email.com", "test_password", False, False)
#
#     aioclient_mock.get(
#         api._get_url(QUERY_TYPE_API, "func"), json={"test": "test"}
#     )
#     assert await api._async_query(QUERY_TYPE_API, "func") == {"test": "test"}
