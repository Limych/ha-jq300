# pylint: disable=protected-access,redefined-outer-name
"""Tests for integration_blueprint api."""
import asyncio
import logging
from unittest.mock import patch

import homeassistant.util.dt as dt_util
import pytest
from asynctest import CoroutineMock
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest import raises
from pytest_homeassistant_custom_component.common import load_fixture
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.jq300.api import (
    BASE_URL_API,
    BASE_URL_DEVICE,
    MSG_BUSY,
    MSG_GENERIC_FAIL,
    MSG_LOGIN_FAIL,
    QUERY_TYPE_API,
    QUERY_TYPE_DEVICE,
    USERAGENT_API,
    USERAGENT_DEVICE,
    Jq300Account,
)


@pytest.fixture
def mock_api(hass: HomeAssistant):
    """Prepare mock API class instance."""
    session = async_get_clientsession(hass)
    return Jq300Account(hass, session, "test@email.com", "test_password", False, False)


async def test_init(mock_api):
    """Test API initialization."""
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

    assert mock_api.unique_id == "test@email.com"
    assert mock_api.name == "test@email.com"
    assert mock_api.name_secure == "te*t@em**l.com"
    assert mock_api.available is False
    assert mock_api.units == expected_units
    assert mock_api._get_useragent(QUERY_TYPE_API) == USERAGENT_API
    assert mock_api._get_useragent(QUERY_TYPE_DEVICE) == USERAGENT_DEVICE
    assert mock_api.devices == {}
    with raises(ValueError):
        _ = mock_api._get_useragent("")
    assert (
        mock_api._add_url_params("http://some/url", {"extra": 1})
        == "http://some/url?uid=-1000&safeToken=anonymous&extra=1"
    )
    assert (
        mock_api._add_url_params("http://some/url", {"extra": 1, "par": 2})
        == "http://some/url?uid=-1000&safeToken=anonymous&extra=1&par=2"
    )
    assert (
        mock_api._get_url(QUERY_TYPE_API, "func")
        == "http://www.youpinyuntai.com:32086/ypyt-api/api/app/func"
    )
    assert (
        mock_api._get_url(QUERY_TYPE_DEVICE, "func")
        == "https://www.youpinyuntai.com:31447/device/func"
    )
    assert (
        mock_api._get_url(QUERY_TYPE_DEVICE, "func", {"extra": 1})
        == "https://www.youpinyuntai.com:31447/device/func?uid=-1000&safeToken=anonymous&extra=1"
    )
    with raises(ValueError):
        _ = mock_api._get_url("", "func")


async def test__get_useragent():
    """Test User-Agent generation."""
    assert Jq300Account._get_useragent(QUERY_TYPE_API) == USERAGENT_API
    assert Jq300Account._get_useragent(QUERY_TYPE_DEVICE) == USERAGENT_DEVICE
    with raises(ValueError):
        Jq300Account._get_useragent("invalid")


async def test__add_url_params(mock_api):
    """Test URL params generation."""
    expected = "http://test/?uid=-1000&safeToken=anonymous"

    assert mock_api._add_url_params("http://test", {}) == expected
    assert (
        mock_api._add_url_params("http://test", {"qwe": "asd"}) == expected + "&qwe=asd"
    )


async def test__get_url(mock_api):
    """Test URL generation."""
    assert mock_api._get_url(QUERY_TYPE_API, "test") == BASE_URL_API + "test"
    assert mock_api._get_url(QUERY_TYPE_DEVICE, "test") == BASE_URL_DEVICE + "test"
    with raises(ValueError):
        mock_api._get_url("invalid", "test")

    assert (
        mock_api._get_url(QUERY_TYPE_API, "test", {"asd": "zxc"})
        == BASE_URL_API + "test?uid=-1000&safeToken=anonymous&asd=zxc"
    )


async def test__async_query(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker, caplog
):
    """Test HTTP requesting."""
    caplog.set_level(logging.DEBUG)

    expected = {"code": 2000, "test": "test"}

    aioclient_mock.get(BASE_URL_API + "func", json=expected)

    session = async_get_clientsession(hass)
    api = Jq300Account(hass, session, "test@email.com", "test_password", False, False)

    assert await api._async_query(QUERY_TYPE_API, "func") == expected
    assert len(caplog.records) == 2

    for code, msg in {102: MSG_LOGIN_FAIL, 9999: MSG_BUSY, 1: MSG_GENERIC_FAIL}.items():
        caplog.clear()
        aioclient_mock.clear_requests()

        expected["code"] = code
        aioclient_mock.get(BASE_URL_API + "func", json=expected)

        assert await api._async_query(QUERY_TYPE_API, "func") is None
        assert len(caplog.records) == 3
        assert caplog.records[-1].message == msg

    caplog.clear()
    aioclient_mock.clear_requests()

    expected["returnCode"] = 1
    aioclient_mock.get(BASE_URL_DEVICE + "func", json=expected)

    assert await api._async_query(QUERY_TYPE_DEVICE, "func") is None
    assert len(caplog.records) == 3
    assert caplog.records[-1].message == MSG_GENERIC_FAIL


async def test_async_connect(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Test (Re)Connect to account and return connection status."""
    login_json = load_fixture("loginByEmail.json")

    aioclient_mock.get(BASE_URL_API + "loginByEmail", text=login_json)

    session = async_get_clientsession(hass)
    api = Jq300Account(hass, session, "test@email.com", "test_password", False, False)

    with patch.object(api, "_mqtt_connect"):
        assert len(aioclient_mock.mock_calls) == 0

        assert await api.async_connect()
        assert len(aioclient_mock.mock_calls) == 1

        assert await api.async_connect()
        assert len(aioclient_mock.mock_calls) == 1

        assert await api.async_connect(True)
        assert len(aioclient_mock.mock_calls) == 2


async def test_async_update_devices(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test update available devices from cloud."""
    devices_json = load_fixture("deviceManager.json")

    aioclient_mock.get(BASE_URL_API + "deviceManager", text=devices_json)

    session = async_get_clientsession(hass)
    api = Jq300Account(hass, session, "test@email.com", "test_password", False, False)

    api.params["uid"] = 123

    expected = {
        43133: {
            "circleid": "972f9d2757bc22e416581187",
            "pt_name": "Bedroom",
            "pt_model": "JQ_300",
            "brandname": "\u54c1\u4f18",
            "logo": "mocle.png",
            "onlinestat": 1,
            "flag": 1,
            "id": 76184,
            "deviceid": 43133,
            "devstatus": 6,
            "deviceToken": "26E84E117417B97BA417",
            "status": 1,
            "href": "/resource/page/hcho/indexPm25.html",
            "pic": "20161026101634psgscf591477448194",
            "weburl": "http://market.cmbchina.com/ccard/xyksq/xyksq.html?WT.srch=1&WT.mc_id=N3700BD1057Z074200BZ",
            "updtime": "1477448195",
            "repairstatus": None,
        }
    }

    assert aioclient_mock.call_count == 0
    assert api._sensors == {}

    res = await api.async_update_devices()
    #
    assert res[43133][""] > 0
    res[43133].pop("")
    assert res[43133]["onlinets"] > 0
    res[43133].pop("onlinets")
    #
    assert res == expected

    assert aioclient_mock.call_count == 1

    res = await api.async_update_devices()
    assert res == expected

    assert aioclient_mock.call_count == 1

    res = await api.async_update_devices(True)
    #
    assert res[43133][""] > 0
    res[43133].pop("")
    assert res[43133]["onlinets"] > 0
    res[43133].pop("onlinets")
    #
    assert res == expected

    assert aioclient_mock.call_count == 2

    assert api._sensors == {43133: {}}


async def test__get_devices_mqtt_topics(mock_api):
    """Test _get_devices_mqtt_topics."""
    mock_api._devices = {123: {"deviceToken": "qwe"}}

    assert mock_api._get_devices_mqtt_topics([123]) == ["qwe"]
    assert mock_api._get_devices_mqtt_topics([234]) == []


async def test_active_devices(mock_api):
    """Test active devices getter and setter."""
    mock_api._devices = {123: {"deviceToken": "qwe"}, 234: {"deviceToken": "asd"}}

    with patch.object(mock_api, "_mqtt_unsubscribe"), patch.object(
        mock_api, "_mqtt_subscribe"
    ):
        assert mock_api.active_devices == []
        assert mock_api._mqtt_subscribe.call_count == 0
        assert mock_api._mqtt_unsubscribe.call_count == 0

        mock_api.active_devices = [123]

        assert mock_api.active_devices == [123]
        assert mock_api._mqtt_subscribe.call_count == 1
        assert mock_api._mqtt_unsubscribe.call_count == 0

        mock_api.active_devices = [234]

        assert mock_api.active_devices == [234]
        assert mock_api._mqtt_subscribe.call_count == 2
        assert mock_api._mqtt_unsubscribe.call_count == 1


async def test__extract_sensors_data(mock_api):
    """Test _extract_sensors_data."""
    data = [
        {"content": "2700", "dptId": 1, "seq": 8},
        {"content": "421", "dptId": 1, "seq": 9},
    ]

    assert mock_api._sensors == {}
    assert mock_api._sensors_raw == {}

    mock_api._sensors.setdefault(123, {})

    mock_api._extract_sensors_data(123, 234, data)

    assert mock_api._sensors == {123: {234: {8: 2700.0, 9: 421}}}
    assert mock_api._sensors_raw == {123: {8: 2700.0, 9: 421}}


async def test_get_sensors_raw(mock_api):
    """Test get raw values of states of available sensors for device."""
    assert mock_api._sensors_raw == {}

    mock_api._sensors_raw = {123: "qwe"}

    assert mock_api.get_sensors_raw(123) == "qwe"
    assert mock_api.get_sensors_raw(234) is None


async def test_get_sensors(mock_api):
    """Test states of available sensors for device."""
    assert mock_api._sensors == {}

    ts_now = int(dt_util.now().timestamp())

    mock_api._sensors_raw = {123: {8: 456, 9: 567}}
    mock_api._sensors = {123: {ts_now - 1: {8: 234, 9: 345}, ts_now: {8: 456, 9: 567}}}

    assert mock_api.get_sensors(123) == {8: 345.0, 9: 456}
    assert mock_api.get_sensors(234) is None


async def test_async_update_sensors(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test update current states of all active devices for account."""
    sensors_json = load_fixture("deviceSensors.json")

    aioclient_mock.get(BASE_URL_DEVICE + "list", text=sensors_json)

    session = async_get_clientsession(hass)
    api = Jq300Account(hass, session, "test@email.com", "test_password", False, False)

    assert aioclient_mock.call_count == 0
    assert api._sensors_raw == {}

    api._active_devices = [123]
    api._devices = {123: {"deviceToken": "qwe"}}
    api._sensors.setdefault(123, {})

    ts_now = int(dt_util.now().timestamp())
    expected_data = {1: 0, 4: 25, 5: 37, 6: 39, 7: 0.023, 8: 0.521, 9: 421}

    await api.async_update_sensors()

    assert aioclient_mock.call_count == 1
    assert api._sensors == {123: {ts_now: expected_data}}
    assert api._sensors_raw == {123: expected_data}

    await api.async_update_sensors()

    assert aioclient_mock.call_count == 1


async def test_async_update_sensors_pass(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
):
    """Test update current states of all active devices for account."""
    sensors_json = load_fixture("deviceSensors.json")

    aioclient_mock.get(BASE_URL_DEVICE + "list", text=sensors_json)

    session = async_get_clientsession(hass)
    api = Jq300Account(hass, session, "test@email.com", "test_password", False, False)

    assert aioclient_mock.call_count == 0
    assert api._sensors_raw == {}

    api._active_devices = [123]
    api._sensors_raw = {123: "qwe"}

    await api.async_update_sensors()

    assert aioclient_mock.call_count == 0


async def test_async_update_sensors_or_timeout(mock_api, caplog):
    """Test update current states of all active devices for account."""
    caplog.set_level(logging.DEBUG)

    with patch.object(mock_api, "async_update_sensors", side_effect=CoroutineMock()):
        assert mock_api.async_update_sensors.call_count == 0

        caplog.clear()
        await mock_api.async_update_sensors_or_timeout()

        assert mock_api.async_update_sensors.call_count == 1
        assert len(caplog.records) == 1

        caplog.clear()
        mock_api.async_update_sensors.side_effect = asyncio.TimeoutError

        with raises(asyncio.TimeoutError):
            await mock_api.async_update_sensors_or_timeout()

        assert mock_api.async_update_sensors.call_count == 2
        assert len(caplog.records) == 2
