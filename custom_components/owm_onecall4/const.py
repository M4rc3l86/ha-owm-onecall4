"""Constants for OpenWeatherMap One Call 4.0."""

from datetime import timedelta

from homeassistant.components.weather import (
    ATTR_CONDITION_CLEAR_NIGHT,
    ATTR_CONDITION_CLOUDY,
    ATTR_CONDITION_EXCEPTIONAL,
    ATTR_CONDITION_FOG,
    ATTR_CONDITION_HAIL,
    ATTR_CONDITION_LIGHTNING,
    ATTR_CONDITION_LIGHTNING_RAINY,
    ATTR_CONDITION_PARTLYCLOUDY,
    ATTR_CONDITION_POURING,
    ATTR_CONDITION_RAINY,
    ATTR_CONDITION_SNOWY,
    ATTR_CONDITION_SNOWY_RAINY,
    ATTR_CONDITION_SUNNY,
    ATTR_CONDITION_WINDY,
    ATTR_CONDITION_WINDY_VARIANT,
)

DOMAIN = "owm_onecall4"
DEFAULT_NAME = "OpenWeatherMap"
ATTRIBUTION = "Data provided by OpenWeatherMap (One Call API 4.0)"
MANUFACTURER = "OpenWeather"

API_BASE = "https://api.openweathermap.org/data/4.0/onecall"

# Each update makes 3 billable calls (current, 1h, 1day).
# 10 minutes -> 432 calls per day, below the 1000 free calls.
UPDATE_INTERVAL = timedelta(minutes=10)

# Maximum records per page, as documented by OpenWeather.
HOURLY_COUNT = 20
DAILY_COUNT = 8

# Weather condition codes, same mapping as the core openweathermap integration.
CONDITION_MAP: dict[str, list[int]] = {
    ATTR_CONDITION_CLOUDY: [803, 804],
    ATTR_CONDITION_FOG: [701, 721, 741],
    ATTR_CONDITION_HAIL: [906],
    ATTR_CONDITION_LIGHTNING: [210, 211, 212, 221],
    ATTR_CONDITION_LIGHTNING_RAINY: [200, 201, 202, 230, 231, 232],
    ATTR_CONDITION_PARTLYCLOUDY: [801, 802],
    ATTR_CONDITION_POURING: [504, 314, 502, 503, 522],
    ATTR_CONDITION_RAINY: [300, 301, 302, 310, 311, 312, 313, 500, 501, 520, 521],
    ATTR_CONDITION_SNOWY: [600, 601, 602, 611, 612, 620, 621, 622],
    ATTR_CONDITION_SNOWY_RAINY: [511, 615, 616],
    ATTR_CONDITION_SUNNY: [800],
    ATTR_CONDITION_WINDY: [905, 951, 952, 953, 954, 955, 956, 957],
    ATTR_CONDITION_WINDY_VARIANT: [958, 959, 960, 961],
    ATTR_CONDITION_EXCEPTIONAL: [711, 731, 751, 761, 762, 771, 900, 901, 962, 903, 904],
}
CONDITION_BY_CODE: dict[int, str] = {
    code: condition for condition, codes in CONDITION_MAP.items() for code in codes
}


def condition_from_weather(weather: list[dict] | None) -> str | None:
    """Map an OpenWeather `weather` list to a Home Assistant condition."""
    if not weather:
        return None
    code = weather[0].get("id")
    icon = weather[0].get("icon") or ""
    if code == 800 and icon.endswith("n"):
        return ATTR_CONDITION_CLEAR_NIGHT
    return CONDITION_BY_CODE.get(code)
