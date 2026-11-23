"""Local stdio MCP server backed by the public Open-Meteo APIs."""

from __future__ import annotations

from typing import Any

from mcp.server.fastmcp import FastMCP

try:
    from .http_client import RemoteServiceError, get_json
except ImportError:  # Direct execution: python mcp_tools/weather_server.py
    from http_client import RemoteServiceError, get_json


GEOCODING_ENDPOINT = "https://geocoding-api.open-meteo.com/v1/search"
FORECAST_ENDPOINT = "https://api.open-meteo.com/v1/forecast"

WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snowfall",
    73: "Moderate snowfall",
    75: "Heavy snowfall",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

mcp = FastMCP(
    "Cairnmark Weather",
    instructions="Look up current conditions and forecasts by place name.",
)


def _choice(value: str, allowed: set[str], field_name: str) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        choices = ", ".join(sorted(allowed))
        raise ValueError(f"{field_name} must be one of: {choices}.")
    return normalized


def _location(place: str) -> dict[str, Any]:
    query = place.strip()
    if not query:
        raise ValueError("location is required.")

    payload = get_json(
        GEOCODING_ENDPOINT,
        {
            "name": query,
            "count": 1,
            "language": "en",
            "format": "json",
        },
    )
    results = payload.get("results")
    if not isinstance(results, list) or not results:
        raise ValueError(f"No location was found for {query!r}.")

    result = results[0]
    if not isinstance(result, dict):
        raise RemoteServiceError("The geocoding service returned invalid data.")
    return result


def _location_summary(location: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": location.get("name"),
        "region": location.get("admin1"),
        "country": location.get("country"),
        "latitude": location.get("latitude"),
        "longitude": location.get("longitude"),
        "timezone": location.get("timezone"),
    }


def _coordinates(location: dict[str, Any]) -> tuple[float, float]:
    latitude = location.get("latitude")
    longitude = location.get("longitude")
    if not isinstance(latitude, (int, float)) or not isinstance(
        longitude, (int, float)
    ):
        raise RemoteServiceError("The geocoding service omitted coordinates.")
    return float(latitude), float(longitude)


@mcp.tool()
def get_current_weather(
    location: str,
    temperature_unit: str = "celsius",
    wind_speed_unit: str = "kmh",
) -> dict[str, Any]:
    """Get current weather for a city or other named place."""
    temperature_unit = _choice(
        temperature_unit,
        {"celsius", "fahrenheit"},
        "temperature_unit",
    )
    wind_speed_unit = _choice(
        wind_speed_unit,
        {"kmh", "mph", "ms", "kn"},
        "wind_speed_unit",
    )
    found = _location(location)
    latitude, longitude = _coordinates(found)
    payload = get_json(
        FORECAST_ENDPOINT,
        {
            "latitude": latitude,
            "longitude": longitude,
            "current": (
                "temperature_2m,relative_humidity_2m,apparent_temperature,"
                "precipitation,weather_code,wind_speed_10m"
            ),
            "temperature_unit": temperature_unit,
            "wind_speed_unit": wind_speed_unit,
            "timezone": "auto",
        },
    )
    current = payload.get("current")
    units = payload.get("current_units")
    if not isinstance(current, dict) or not isinstance(units, dict):
        raise RemoteServiceError("Open-Meteo omitted current weather data.")

    weather_code = current.get("weather_code")
    return {
        "location": _location_summary(found),
        "observed_at": current.get("time"),
        "conditions": WEATHER_CODES.get(weather_code, "Unknown"),
        "weather_code": weather_code,
        "temperature": current.get("temperature_2m"),
        "apparent_temperature": current.get("apparent_temperature"),
        "relative_humidity": current.get("relative_humidity_2m"),
        "precipitation": current.get("precipitation"),
        "wind_speed": current.get("wind_speed_10m"),
        "units": {
            "temperature": units.get("temperature_2m"),
            "apparent_temperature": units.get("apparent_temperature"),
            "relative_humidity": units.get("relative_humidity_2m"),
            "precipitation": units.get("precipitation"),
            "wind_speed": units.get("wind_speed_10m"),
        },
        "source": "Open-Meteo",
    }


@mcp.tool()
def get_weather_forecast(
    location: str,
    days: int = 3,
    temperature_unit: str = "celsius",
) -> dict[str, Any]:
    """Get a one-to-seven-day daily forecast for a named place."""
    if not isinstance(days, int) or not 1 <= days <= 7:
        raise ValueError("days must be an integer from 1 through 7.")
    temperature_unit = _choice(
        temperature_unit,
        {"celsius", "fahrenheit"},
        "temperature_unit",
    )
    found = _location(location)
    latitude, longitude = _coordinates(found)
    payload = get_json(
        FORECAST_ENDPOINT,
        {
            "latitude": latitude,
            "longitude": longitude,
            "daily": (
                "weather_code,temperature_2m_max,temperature_2m_min,"
                "precipitation_probability_max,sunrise,sunset"
            ),
            "forecast_days": days,
            "temperature_unit": temperature_unit,
            "timezone": "auto",
        },
    )
    daily = payload.get("daily")
    units = payload.get("daily_units")
    if not isinstance(daily, dict) or not isinstance(units, dict):
        raise RemoteServiceError("Open-Meteo omitted daily forecast data.")

    dates = daily.get("time")
    if not isinstance(dates, list):
        raise RemoteServiceError("Open-Meteo returned invalid forecast dates.")

    forecast = []
    for index, date in enumerate(dates):
        code = _list_value(daily, "weather_code", index)
        forecast.append(
            {
                "date": date,
                "conditions": WEATHER_CODES.get(code, "Unknown"),
                "weather_code": code,
                "temperature_max": _list_value(
                    daily, "temperature_2m_max", index
                ),
                "temperature_min": _list_value(
                    daily, "temperature_2m_min", index
                ),
                "precipitation_probability_max": _list_value(
                    daily, "precipitation_probability_max", index
                ),
                "sunrise": _list_value(daily, "sunrise", index),
                "sunset": _list_value(daily, "sunset", index),
            }
        )

    return {
        "location": _location_summary(found),
        "forecast": forecast,
        "units": {
            "temperature_max": units.get("temperature_2m_max"),
            "temperature_min": units.get("temperature_2m_min"),
            "precipitation_probability_max": units.get(
                "precipitation_probability_max"
            ),
        },
        "source": "Open-Meteo",
    }


def _list_value(data: dict[str, Any], key: str, index: int) -> Any:
    values = data.get(key)
    if not isinstance(values, list) or index >= len(values):
        return None
    return values[index]


if __name__ == "__main__":
    mcp.run(transport="stdio")
