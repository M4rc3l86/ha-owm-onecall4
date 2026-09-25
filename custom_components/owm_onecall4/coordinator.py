"""Data update coordinator for OpenWeatherMap One Call 4.0."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import OneCallAuthError, OneCallClient, OneCallData, OneCallError
from .const import (
    CURRENT_INTERVAL,
    DAILY_CALL_LIMIT,
    DAILY_INTERVAL,
    DOMAIN,
    HOURLY_INTERVAL,
    HOURLY_PAGES,
    MINUTELY_INTERVAL,
    RETRY_INTERVAL,
    TICK_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1
SAVE_DELAY = 60

type OneCallConfigEntry = ConfigEntry[OneCallCoordinator]


class OneCallCoordinator(DataUpdateCoordinator[OneCallData]):
    """Tick every minute and fetch each part of the data when it is due.

    Every call is counted per local day. At DAILY_CALL_LIMIT calls the
    coordinator stops fetching until midnight and keeps the last data.
    """

    config_entry: OneCallConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: OneCallConfigEntry, client: OneCallClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=TICK_INTERVAL,
        )
        self.client = client
        self._result = OneCallData()
        self._next_fetch: dict[str, datetime] = {}
        self._store: Store[dict[str, Any]] = Store(
            hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}"
        )
        self._calls_day = ""
        self.calls_today = 0
        self._limit_logged = False
        # name -> (interval, calls per fetch, fetch function)
        self._parts: dict[
            str, tuple[timedelta, int, Callable[[], Awaitable[Any]]]
        ] = {
            "current": (CURRENT_INTERVAL, 1, client.async_get_current),
            "daily": (DAILY_INTERVAL, 1, client.async_get_daily),
            "hourly": (HOURLY_INTERVAL, HOURLY_PAGES, client.async_get_hourly),
            "minutely": (MINUTELY_INTERVAL, 1, client.async_get_minutely),
        }

    async def async_load_call_counter(self) -> None:
        """Restore today's call count, so restarts do not reset the limit."""
        stored = await self._store.async_load() or {}
        self._calls_day = stored.get("day", "")
        self.calls_today = stored.get("calls", 0)
        self._roll_day()

    async def async_save_call_counter(self) -> None:
        """Write the call count now (used on unload)."""
        await self._store.async_save(self._counter_data())

    def _counter_data(self) -> dict[str, Any]:
        return {"day": self._calls_day, "calls": self.calls_today}

    def _roll_day(self) -> None:
        today = dt_util.now().date().isoformat()
        if today != self._calls_day:
            self._calls_day = today
            self.calls_today = 0
            self._limit_logged = False

    def _apply(self, name: str, result: Any) -> None:
        if name == "current":
            if not result["data"]:
                raise OneCallError("No current weather in response")
            self._result.current = result["data"][0]
            self._result.timezone = result.get("timezone")
        else:
            setattr(self._result, name, result)

    async def _async_update_data(self) -> OneCallData:
        now = dt_util.utcnow()
        self._roll_day()
        errors: list[str] = []
        fetched = False

        for name, (interval, cost, fetch) in self._parts.items():
            if name in self._next_fetch and now < self._next_fetch[name]:
                continue
            if self.calls_today + cost > DAILY_CALL_LIMIT:
                if not self._limit_logged:
                    _LOGGER.warning(
                        "Daily limit of %s calls reached, no new data until midnight",
                        DAILY_CALL_LIMIT,
                    )
                    self._limit_logged = True
                continue
            # Set the next time first, so errors do not cause fast retries.
            self._next_fetch[name] = now + interval
            self.calls_today += cost
            fetched = True
            try:
                self._apply(name, await fetch())
            except OneCallAuthError as err:
                raise UpdateFailed(
                    f"API key rejected (One Call 4.0 subscription missing?): {err}"
                ) from err
            except OneCallError as err:
                errors.append(f"{name}: {err}")
                # Do not wait a full interval (up to 60 min) without data.
                self._next_fetch[name] = now + min(interval, RETRY_INTERVAL)

        if fetched:
            self._store.async_delay_save(self._counter_data, SAVE_DELAY)
        if not self._result.current:
            raise UpdateFailed("; ".join(errors) or "No current weather yet")
        if errors:
            # Keep the older data of the failed parts.
            _LOGGER.warning("Update failed for %s", "; ".join(errors))
        return self._result
