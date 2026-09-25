"""Data update coordinator for OpenWeatherMap One Call 4.0."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import OneCallAuthError, OneCallClient, OneCallData, OneCallError
from .const import DOMAIN, UPDATE_INTERVAL

_LOGGER = logging.getLogger(__name__)

type OneCallConfigEntry = ConfigEntry[OneCallCoordinator]


class OneCallCoordinator(DataUpdateCoordinator[OneCallData]):
    """Fetch data from One Call 4.0 every UPDATE_INTERVAL."""

    config_entry: OneCallConfigEntry

    def __init__(
        self, hass: HomeAssistant, entry: OneCallConfigEntry, client: OneCallClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
        )
        self.client = client

    async def _async_update_data(self) -> OneCallData:
        try:
            return await self.client.async_get_all()
        except OneCallAuthError as err:
            raise UpdateFailed(
                f"API key rejected (One Call 4.0 subscription missing?): {err}"
            ) from err
        except OneCallError as err:
            raise UpdateFailed(str(err)) from err
