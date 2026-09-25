"""Small async client for the OpenWeather One Call API 4.0."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any

import aiohttp

from .const import API_BASE, DAILY_COUNT, HOURLY_COUNT

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


class OneCallError(Exception):
    """Generic API error."""


class OneCallAuthError(OneCallError):
    """The key is invalid or has no One Call 4.0 subscription."""


@dataclass
class OneCallData:
    """Result of one update."""

    current: dict[str, Any]
    hourly: list[dict[str, Any]]
    daily: list[dict[str, Any]]
    timezone: str | None


class OneCallClient:
    """Client for the /data/4.0/onecall endpoints."""

    def __init__(
        self,
        session: aiohttp.ClientSession,
        api_key: str,
        latitude: float,
        longitude: float,
        language: str = "en",
    ) -> None:
        self._session = session
        self._api_key = api_key
        self._latitude = latitude
        self._longitude = longitude
        self._language = language

    async def _get(self, path: str, **extra: Any) -> dict[str, Any]:
        params = {
            "lat": self._latitude,
            "lon": self._longitude,
            "units": "metric",
            "lang": self._language,
            "appid": self._api_key,
            **extra,
        }
        try:
            async with self._session.get(
                f"{API_BASE}/{path}", params=params, timeout=REQUEST_TIMEOUT
            ) as resp:
                try:
                    body = await resp.json(content_type=None)
                except ValueError:
                    body = {}
                if resp.status == 401:
                    raise OneCallAuthError(body.get("message", "Unauthorized"))
                if resp.status != 200:
                    raise OneCallError(
                        f"HTTP {resp.status}: {body.get('message', 'unknown error')}"
                    )
        except (aiohttp.ClientError, TimeoutError) as err:
            raise OneCallError(f"Connection error: {err}") from err
        if not isinstance(body, dict) or not isinstance(body.get("data"), list):
            raise OneCallError("Unexpected response format")
        return body

    async def async_get_current(self) -> dict[str, Any]:
        """Fetch only the current weather (1 call). Used to validate the key."""
        return await self._get("current")

    async def async_get_all(self) -> OneCallData:
        """Fetch current, hourly and daily data (3 calls)."""
        current, hourly, daily = await asyncio.gather(
            self._get("current"),
            self._get("timeline/1h", cnt=HOURLY_COUNT),
            self._get("timeline/1day", cnt=DAILY_COUNT),
        )
        if not current["data"]:
            raise OneCallError("No current weather in response")
        return OneCallData(
            current=current["data"][0],
            hourly=hourly["data"],
            daily=daily["data"],
            timezone=current.get("timezone"),
        )
