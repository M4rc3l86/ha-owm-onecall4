"""Sensors for OpenWeatherMap One Call 4.0."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import EntityCategory, UnitOfPrecipitationDepth, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import ATTRIBUTION, DOMAIN
from .coordinator import OneCallConfigEntry, OneCallCoordinator


def _upcoming_minutes(coordinator: OneCallCoordinator) -> list[dict[str, Any]]:
    """Minutely records from the current minute on (data can be 3 minutes old)."""
    now = dt_util.utcnow().timestamp()
    return [
        record
        for record in coordinator.data.minutely
        if "dt" in record and record["dt"] > now - 60
    ]


def _rain_next_hour(coordinator: OneCallCoordinator) -> float | None:
    """Total mm in the next hour. Each minute gives a rate in mm/h."""
    minutes = _upcoming_minutes(coordinator)
    if not minutes:
        return None
    return round(sum(r.get("precipitation") or 0 for r in minutes) / 60, 2)


def _rain_starts_in(coordinator: OneCallCoordinator) -> int | None:
    """Minutes until the first minute with rain. None if no rain is expected."""
    now = dt_util.utcnow().timestamp()
    for record in _upcoming_minutes(coordinator):
        if (record.get("precipitation") or 0) > 0:
            return max(0, round((record["dt"] - now) / 60))
    return None


def _rain_forecast(coordinator: OneCallCoordinator) -> dict[str, Any]:
    return {
        "forecast": [
            {
                "datetime": datetime.fromtimestamp(r["dt"], tz=UTC).isoformat(),
                "precipitation": r.get("precipitation") or 0,
            }
            for r in _upcoming_minutes(coordinator)
        ]
    }


@dataclass(frozen=True, kw_only=True)
class OneCallSensorDescription(SensorEntityDescription):
    """Sensor description with a value function."""

    value_fn: Callable[[OneCallCoordinator], Any]
    attributes_fn: Callable[[OneCallCoordinator], dict[str, Any]] | None = None
    needs_minutely: bool = False


SENSORS: tuple[OneCallSensorDescription, ...] = (
    OneCallSensorDescription(
        key="rain_next_hour",
        translation_key="rain_next_hour",
        device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=1,
        value_fn=_rain_next_hour,
        attributes_fn=_rain_forecast,
        needs_minutely=True,
    ),
    OneCallSensorDescription(
        key="rain_starts_in",
        translation_key="rain_starts_in",
        device_class=SensorDeviceClass.DURATION,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        value_fn=_rain_starts_in,
        needs_minutely=True,
    ),
    OneCallSensorDescription(
        key="api_calls_today",
        translation_key="api_calls_today",
        entity_category=EntityCategory.DIAGNOSTIC,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda coordinator: coordinator.calls_today,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: OneCallConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    coordinator = entry.runtime_data
    async_add_entities(OneCallSensor(coordinator, description) for description in SENSORS)


class OneCallSensor(CoordinatorEntity[OneCallCoordinator], SensorEntity):
    """A sensor backed by the One Call 4.0 coordinator."""

    entity_description: OneCallSensorDescription
    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True
    # The minute list changes every 3 minutes. Do not store it in the history.
    _unrecorded_attributes = frozenset({"forecast"})

    def __init__(
        self, coordinator: OneCallCoordinator, description: OneCallSensorDescription
    ) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(identifiers={(DOMAIN, entry.entry_id)})

    @property
    def available(self) -> bool:
        if self.entity_description.needs_minutely and not self.coordinator.data.minutely:
            return False
        return super().available

    @property
    def native_value(self) -> Any:
        return self.entity_description.value_fn(self.coordinator)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attributes_fn is None:
            return None
        return self.entity_description.attributes_fn(self.coordinator)
