# OpenWeatherMap One Call 4.0 for Home Assistant

Custom integration that provides a `weather` entity from the
[OpenWeather One Call API 4.0](https://openweathermap.org/api/one-call-4-desciption).
The core `openweathermap` integration only supports One Call 3.0
([home-assistant/core#174333](https://github.com/home-assistant/core/issues/174333)).

## Features

- Current weather (temperature, feels like, humidity, pressure, wind, gusts, clouds, UV, visibility, dew point)
- Hourly forecast (next 60 hours)
- Daily forecast (8 days)
- Rain nowcast sensors from the minute timeline:
  - `Rain next hour` (mm, the minute list is in the `forecast` attribute)
  - `Rain starts in` (minutes, `unknown` if no rain is expected)
- `API calls today` diagnostic sensor

## API usage

Each part of the data has its own interval:

| Endpoint | Interval | Calls per day |
|---|---|---|
| `/onecall/timeline/1min` | 3 min | 480 |
| `/onecall/current` | 5 min | 288 |
| `/onecall/timeline/1h` (3 pages) | 30 min | 144 |
| `/onecall/timeline/1day` | 60 min | 24 |
| **Total** | | **936** |

That is below the 1000 free daily calls of the "One Call by Call" plan.
The integration counts its calls per local day (also across restarts)
and stops fetching at 980 calls until midnight. Also set a daily call
limit of 1000 in your OpenWeather account to avoid charges.

## Installation (HACS)

1. HACS → ⋮ → Custom repositories → add this repository as type "Integration".
2. Download "OpenWeatherMap One Call 4.0" and restart Home Assistant.
3. Settings → Devices & services → Add integration → "OpenWeatherMap One Call 4.0".
