"""Small async client for the OpenWeather One Call API 4.0."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import aiohttp

from .const import API_BASE, DAILY_COUNT, HOURLY_COUNT, HOURLY_PAGES

REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=20)


class OneCallError(Exception):
    """Generic API error."""


class OneCallAuthError(OneCallError):
    """The key is invalid or has no One Call 4.0 subscription."""


@dataclass
class OneCallData:
    """Result of one update."""

    current: dict[str, Any] = field(default_factory=dict)
    hourly: list[dict[str, Any]] = field(default_factory=list)
    daily: list[dict[str, Any]] = field(default_factory=list)
    minutely: list[dict[str, Any]] = field(default_factory=list)
    timezone: str | None = None


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
        """Fetch the current weather (1 call)."""
        return await self._get("current")

    async def async_get_hourly(self) -> list[dict[str, Any]]:
        """Fetch HOURLY_PAGES pages of the hourly timeline (1 call per page)."""
        records: list[dict[str, Any]] = []
        start: int | None = None
        for _ in range(HOURLY_PAGES):
            extra: dict[str, Any] = {"cnt": HOURLY_COUNT}
            if start is not None:
                extra["start"] = start
            page = (await self._get("timeline/1h", **extra))["data"]
            records.extend(page)
            if len(page) < HOURLY_COUNT or "dt" not in page[-1]:
                break
            start = page[-1]["dt"] + 3600
        return records

    async def async_get_daily(self) -> list[dict[str, Any]]:
        """Fetch the daily timeline (1 call)."""
        return (await self._get("timeline/1day", cnt=DAILY_COUNT))["data"]

    async def async_get_minutely(self) -> list[dict[str, Any]]:
        """Fetch the precipitation for the next 60 minutes (1 call)."""
        return (await self._get("timeline/1min"))["data"]
