"""Fixtures for One Call 4.0 tests."""

import time

import pytest

from custom_components.owm_onecall4.const import API_BASE


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Enable custom integrations in all tests."""
    return


def _now() -> int:
    return int(time.time())


CURRENT = {
    "lat": 52.614,
    "lon": 13.1996,
    "timezone": "Europe/Berlin",
    "timezone_offset": 7200,
    "data": [
        {
            "dt": 0,
            "temp": 14.3,
            "feels_like": 13.6,
            "pressure": 1015,
            "humidity": 72,
            "dew_point": 9.3,
            "uvi": 2.1,
            "clouds": 75,
            "visibility": 10000,
            "wind_speed": 4.1,
            "wind_deg": 250,
            "wind_gust": 7.2,
            "weather": [{"id": 803, "main": "Clouds", "description": "Überwiegend bewölkt", "icon": "04d"}],
        }
    ],
}


def hourly() -> dict:
    now = _now()
    return {
        "timezone": "Europe/Berlin",
        "data": [
            {
                "dt": now + i * 3600,
                "temp": 14 + i,
                "feels_like": 13 + i,
                "humidity": 70,
                "pressure": 1015,
                "wind_speed": 3.0,
                "wind_deg": 240,
                "clouds": 20,
                "pop": 0.35,
                "rain": {"1h": 0.4},
                "weather": [{"id": 500, "icon": "10d"}],
            }
            for i in range(3)
        ],
    }


def daily() -> dict:
    now = _now()
    return {
        "timezone": "Europe/Berlin",
        "data": [
            {
                "dt": now + i * 86400,
                "temp": {"min": 8 + i, "max": 17 + i, "day": 15, "night": 9, "eve": 13, "morn": 10},
                "feels_like": {"day": 14},
                "humidity": 65,
                "pressure": 1013,
                "wind_speed": 5.0,
                "wind_deg": 260,
                "clouds": 40,
                "pop": 0.8,
                "rain": 2.5,
                "snow": 0.5,
                "weather": [{"id": 800, "icon": "01d"}],
            }
            for i in range(2)
        ],
    }


def minutely(rain_from: int | None = 10) -> dict:
    """60 minutes, with 1.2 mm/h of rain from minute `rain_from` on."""
    now = _now() // 60 * 60
    return {
        "timezone": "Europe/Berlin",
        "data": [
            {
                "dt": now + i * 60,
                "precipitation": 1.2 if rain_from is not None and i >= rain_from else 0,
            }
            for i in range(60)
        ],
    }


@pytest.fixture
def mock_api(aioclient_mock):
    """Mock all four One Call 4.0 endpoints."""
    aioclient_mock.get(f"{API_BASE}/current", json=CURRENT)
    aioclient_mock.get(f"{API_BASE}/timeline/1h", json=hourly())
    aioclient_mock.get(f"{API_BASE}/timeline/1day", json=daily())
    aioclient_mock.get(f"{API_BASE}/timeline/1min", json=minutely())
    return aioclient_mock
