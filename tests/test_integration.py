"""Tests for the One Call 4.0 integration."""

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.owm_onecall4.const import API_BASE, DOMAIN

USER_INPUT = {
    CONF_NAME: "OpenWeatherMap",
    CONF_API_KEY: "test-key",
    CONF_LATITUDE: 52.614,
    CONF_LONGITUDE: 13.1996,
}


async def test_config_flow_success(hass: HomeAssistant, mock_api) -> None:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenWeatherMap"
    # The key is sent as appid on the 4.0 path.
    url = str(mock_api.mock_calls[0][1])
    assert "/data/4.0/onecall/current" in url
    assert "appid=test-key" in url


async def test_config_flow_invalid_auth(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(
        f"{API_BASE}/current",
        status=401,
        json={"cod": 401, "message": "requires a separate subscription"},
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(result["flow_id"], USER_INPUT)
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def _setup(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN, title="OpenWeatherMap", data=USER_INPUT, unique_id="52.614-13.1996"
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def test_weather_entity(hass: HomeAssistant, mock_api) -> None:
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.LOADED

    state = hass.states.get("weather.openweathermap")
    assert state is not None
    assert state.state == "cloudy"
    assert state.attributes["temperature"] == 14.3
    assert state.attributes["humidity"] == 72
    assert state.attributes["pressure"] == 1015
    assert state.attributes["wind_bearing"] == 250
    assert state.attributes["visibility"] == 10.0
    # 4.1 m/s -> 14.76 km/h (HA converts to the metric default).
    assert state.attributes["wind_speed"] == 14.76

    hourly = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": "weather.openweathermap", "type": "hourly"},
        blocking=True,
        return_response=True,
    )
    hourly = hourly["weather.openweathermap"]["forecast"]
    assert len(hourly) == 3
    assert hourly[0]["condition"] == "rainy"
    assert hourly[0]["precipitation"] == 0.4
    assert hourly[0]["precipitation_probability"] == 35

    daily = await hass.services.async_call(
        "weather",
        "get_forecasts",
        {"entity_id": "weather.openweathermap", "type": "daily"},
        blocking=True,
        return_response=True,
    )
    daily = daily["weather.openweathermap"]["forecast"]
    assert len(daily) == 2
    assert daily[0]["temperature"] == 17
    assert daily[0]["templow"] == 8
    assert daily[0]["precipitation"] == 3.0
    assert daily[0]["precipitation_probability"] == 80
    assert daily[0]["condition"] == "sunny"

    assert await hass.config_entries.async_unload(entry.entry_id)


async def test_setup_retry_on_auth_error(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{API_BASE}/current", status=401, json={"cod": 401, "message": "no"})
    aioclient_mock.get(f"{API_BASE}/timeline/1h", status=401, json={"cod": 401})
    aioclient_mock.get(f"{API_BASE}/timeline/1day", status=401, json={"cod": 401})
    entry = await _setup(hass)
    assert entry.state is ConfigEntryState.SETUP_RETRY
