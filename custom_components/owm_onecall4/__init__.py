"""OpenWeatherMap One Call API 4.0 integration."""

from __future__ import annotations

from homeassistant.const import (
    CONF_API_KEY,
    CONF_LATITUDE,
    CONF_LONGITUDE,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import OneCallClient
from .coordinator import OneCallConfigEntry, OneCallCoordinator

PLATFORMS = [Platform.WEATHER]


async def async_setup_entry(hass: HomeAssistant, entry: OneCallConfigEntry) -> bool:
    """Set up One Call 4.0 from a config entry."""
    client = OneCallClient(
        async_get_clientsession(hass),
        entry.data[CONF_API_KEY],
        entry.data[CONF_LATITUDE],
        entry.data[CONF_LONGITUDE],
        hass.config.language,
    )
    coordinator = OneCallCoordinator(hass, entry, client)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OneCallConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
