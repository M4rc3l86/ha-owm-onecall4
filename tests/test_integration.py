"""Tests for the One Call 4.0 integration."""

from datetime import timedelta

from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_KEY, CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)
from yarl import URL

from custom_components.owm_onecall4.const import API_BASE, DAILY_CALL_LIMIT, DOMAIN

from .conftest import CURRENT, daily, hourly, minutely

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


async def test_rain_sensors(hass: HomeAssistant, mock_api) -> None:
    await _setup(hass)
    # 50 minutes at 1.2 mm/h -> 1.0 mm in the next hour.
    state = hass.states.get("sensor.openweathermap_rain_next_hour")
    assert float(state.state) == 1.0
    assert len(state.attributes["forecast"]) == 60
    assert int(hass.states.get("sensor.openweathermap_rain_starts_in").state) in (9, 10)
    # current 1 + daily 1 + hourly 3 (counted per page) + minutely 1.
    assert hass.states.get("sensor.openweathermap_api_calls_today").state == "6"


async def test_no_rain_expected(hass: HomeAssistant, aioclient_mock) -> None:
    aioclient_mock.get(f"{API_BASE}/current", json=CURRENT)
    aioclient_mock.get(f"{API_BASE}/timeline/1h", json=hourly())
    aioclient_mock.get(f"{API_BASE}/timeline/1day", json=daily())
    aioclient_mock.get(f"{API_BASE}/timeline/1min", json=minutely(rain_from=None))
    await _setup(hass)
    assert float(hass.states.get("sensor.openweathermap_rain_next_hour").state) == 0
    assert hass.states.get("sensor.openweathermap_rain_starts_in").state == "unknown"


def _paths(aioclient_mock) -> list[str]:
    return [
        URL(str(call[1])).path.rsplit("/onecall/", 1)[1]
        for call in aioclient_mock.mock_calls
    ]


async def test_each_part_has_its_own_interval(
    hass: HomeAssistant, mock_api, freezer
) -> None:
    await _setup(hass)
    assert sorted(_paths(mock_api)) == [
        "current",
        "timeline/1day",
        "timeline/1h",
        "timeline/1min",
    ]

    mock_api.mock_calls.clear()
    freezer.tick(timedelta(minutes=3))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _paths(mock_api) == ["timeline/1min"]

    mock_api.mock_calls.clear()
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert _paths(mock_api) == ["current"]


async def test_daily_limit_stops_fetching(
    hass: HomeAssistant, mock_api, freezer
) -> None:
    entry = await _setup(hass)
    entry.runtime_data.calls_today = DAILY_CALL_LIMIT
    mock_api.mock_calls.clear()
    for _ in range(35):
        freezer.tick(timedelta(minutes=1))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert mock_api.mock_calls == []
    # The old data stays available.
    assert hass.states.get("weather.openweathermap").state == "cloudy"


async def test_call_counter_survives_restart(
    hass: HomeAssistant, mock_api, hass_storage
) -> None:
    entry = MockConfigEntry(
        domain=DOMAIN, title="OpenWeatherMap", data=USER_INPUT, unique_id="52.614-13.1996"
    )
    entry.add_to_hass(hass)
    hass_storage[f"{DOMAIN}.{entry.entry_id}"] = {
        "version": 1,
        "key": f"{DOMAIN}.{entry.entry_id}",
        "data": {"day": dt_util.now().date().isoformat(), "calls": 500},
    }
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.runtime_data.calls_today == 506


async def test_hourly_uses_three_pages(hass: HomeAssistant, aioclient_mock) -> None:
    full_page = hourly()
    first = full_page["data"][0]
    full_page["data"] = [dict(first, dt=first["dt"] + i * 3600) for i in range(20)]
    aioclient_mock.get(f"{API_BASE}/current", json=CURRENT)
    aioclient_mock.get(f"{API_BASE}/timeline/1h", json=full_page)
    aioclient_mock.get(f"{API_BASE}/timeline/1day", json=daily())
    aioclient_mock.get(f"{API_BASE}/timeline/1min", json=minutely())
    await _setup(hass)
    hourly_urls = [
        URL(str(call[1])) for call in aioclient_mock.mock_calls if "1h" in str(call[1])
    ]
    assert len(hourly_urls) == 3
    assert "start" not in hourly_urls[0].query
    assert int(hourly_urls[1].query["start"]) == full_page["data"][-1]["dt"] + 3600
