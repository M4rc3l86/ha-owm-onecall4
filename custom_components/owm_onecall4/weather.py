"""Weather entity for OpenWeatherMap One Call 4.0."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from homeassistant.components.weather import (
    Forecast,
    SingleCoordinatorWeatherEntity,
    WeatherEntityFeature,
)
from homeassistant.const import (
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN, MANUFACTURER, condition_from_weather
from .coordinator import OneCallConfigEntry, OneCallCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OneCallConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the weather entity."""
    async_add_entities([OneCallWeather(entry.runtime_data)])


def _iso(timestamp: int) -> str:
    return datetime.fromtimestamp(timestamp, tz=UTC).isoformat()


def _precipitation(record: dict[str, Any]) -> float | None:
    """Sum rain and snow. Hourly uses {"1h": mm}, daily uses a number."""
    total = None
    for key in ("rain", "snow"):
        value = record.get(key)
        if isinstance(value, dict):
            value = value.get("1h")
        if isinstance(value, (int, float)):
            total = (total or 0) + value
    return round(total, 2) if total is not None else None


def _probability(record: dict[str, Any]) -> int | None:
    pop = record.get("pop")
    return round(pop * 100) if isinstance(pop, (int, float)) else None


def _visibility_km(record: dict[str, Any]) -> float | None:
    visibility = record.get("visibility")
    return visibility / 1000 if isinstance(visibility, (int, float)) else None


class OneCallWeather(SingleCoordinatorWeatherEntity[OneCallCoordinator]):
    """Weather entity backed by One Call 4.0."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    _attr_name = None
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_native_pressure_unit = UnitOfPressure.HPA
    _attr_native_wind_speed_unit = UnitOfSpeed.METERS_PER_SECOND
    _attr_native_precipitation_unit = UnitOfPrecipitationDepth.MILLIMETERS
    _attr_native_visibility_unit = UnitOfLength.KILOMETERS
    _attr_supported_features = (
        WeatherEntityFeature.FORECAST_DAILY | WeatherEntityFeature.FORECAST_HOURLY
    )

    def __init__(self, coordinator: OneCallCoordinator) -> None:
        super().__init__(coordinator)
        entry = coordinator.config_entry
        self._attr_unique_id = entry.unique_id or entry.entry_id
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, entry.entry_id)},
            manufacturer=MANUFACTURER,
            name=entry.title,
        )

    @property
    def _current(self) -> dict[str, Any]:
        return self.coordinator.data.current

    @property
    def condition(self) -> str | None:
        return condition_from_weather(self._current.get("weather"))

    @property
    def native_temperature(self) -> float | None:
        return self._current.get("temp")

    @property
    def native_apparent_temperature(self) -> float | None:
        return self._current.get("feels_like")

    @property
    def native_dew_point(self) -> float | None:
        return self._current.get("dew_point")

    @property
    def humidity(self) -> float | None:
        return self._current.get("humidity")

    @property
    def native_pressure(self) -> float | None:
        return self._current.get("pressure")

    @property
    def native_wind_speed(self) -> float | None:
        return self._current.get("wind_speed")

    @property
    def native_wind_gust_speed(self) -> float | None:
        return self._current.get("wind_gust")

    @property
    def wind_bearing(self) -> float | None:
        return self._current.get("wind_deg")

    @property
    def cloud_coverage(self) -> float | None:
        return self._current.get("clouds")

    @property
    def uv_index(self) -> float | None:
        return self._current.get("uvi")

    @property
    def native_visibility(self) -> float | None:
        return _visibility_km(self._current)

    def _async_forecast_hourly(self) -> list[Forecast] | None:
        now = dt_util.utcnow().timestamp()
        return [
            Forecast(
                datetime=_iso(record["dt"]),
                condition=condition_from_weather(record.get("weather")),
                native_temperature=record.get("temp"),
                native_apparent_temperature=record.get("feels_like"),
                native_dew_point=record.get("dew_point"),
                humidity=record.get("humidity"),
                native_pressure=record.get("pressure"),
                native_wind_speed=record.get("wind_speed"),
                native_wind_gust_speed=record.get("wind_gust"),
                wind_bearing=record.get("wind_deg"),
                cloud_coverage=record.get("clouds"),
                uv_index=record.get("uvi"),
                native_precipitation=_precipitation(record),
                precipitation_probability=_probability(record),
            )
            for record in self.coordinator.data.hourly
            if "dt" in record and record["dt"] > now - 3600
        ]

    def _async_forecast_daily(self) -> list[Forecast] | None:
        today = dt_util.start_of_local_day().timestamp()
        forecast: list[Forecast] = []
        for record in self.coordinator.data.daily:
            if "dt" not in record or record["dt"] < today:
                continue
            temp = record.get("temp")
            temp = temp if isinstance(temp, dict) else {}
            feels_like = record.get("feels_like")
            feels_like = feels_like if isinstance(feels_like, dict) else {}
            forecast.append(
                Forecast(
                    datetime=_iso(record["dt"]),
                    condition=condition_from_weather(record.get("weather")),
                    native_temperature=temp.get("max"),
                    native_templow=temp.get("min"),
                    native_apparent_temperature=feels_like.get("day"),
                    native_dew_point=record.get("dew_point"),
                    humidity=record.get("humidity"),
                    native_pressure=record.get("pressure"),
                    native_wind_speed=record.get("wind_speed"),
                    native_wind_gust_speed=record.get("wind_gust"),
                    wind_bearing=record.get("wind_deg"),
                    cloud_coverage=record.get("clouds"),
                    uv_index=record.get("uvi"),
                    native_precipitation=_precipitation(record),
                    precipitation_probability=_probability(record),
                )
            )
        return forecast
