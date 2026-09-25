# OpenWeatherMap One Call 4.0 for Home Assistant

Custom integration that provides a `weather` entity from the
[OpenWeather One Call API 4.0](https://openweathermap.org/api/one-call-4-desciption).
The core `openweathermap` integration only supports One Call 3.0
([home-assistant/core#174333](https://github.com/home-assistant/core/issues/174333)).

## Features

- Current weather (temperature, feels like, humidity, pressure, wind, gusts, clouds, UV, visibility, dew point)
- Hourly forecast (next 20 hours)
- Daily forecast (8 days)

## API usage

Every 10 minutes the integration makes 3 calls
(`/onecall/current`, `/onecall/timeline/1h`, `/onecall/timeline/1day`).
That is 432 calls per day, below the 1000 free daily calls of the
"One Call by Call" plan. Set a daily call limit of 1000 in your
OpenWeather account to avoid charges.

## Installation (HACS)

1. HACS → ⋮ → Custom repositories → add this repository as type "Integration".
2. Download "OpenWeatherMap One Call 4.0" and restart Home Assistant.
3. Settings → Devices & services → Add integration → "OpenWeatherMap One Call 4.0".
