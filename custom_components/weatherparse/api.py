"""Small client for the WeatherParse dashboard JSON (also works with Acuparse 3.x).

WeatherParse for Home Assistant
Copyright (C) 2026 WeatherParse contributors
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

import asyncio
from typing import Any

import aiohttp

from .const import DASHBOARD_PATH


class WeatherParseError(Exception):
    """The station could not be read."""


class WeatherParseConnectionError(WeatherParseError):
    """Network problem: station unreachable, timeout, TLS."""


class WeatherParseResponseError(WeatherParseError):
    """The station answered, but not with dashboard data."""


def dashboard_url(base_url: str) -> str:
    """Full dashboard URL for a base address such as http://192.0.2.10 or https://weather.example.com/."""
    return base_url.strip().rstrip("/") + DASHBOARD_PATH


async def fetch_dashboard(
    session: aiohttp.ClientSession, base_url: str, timeout: float = 15
) -> dict[str, Any]:
    """Return the dashboard object: {"main": {...}, "atlas": {...}?, "lightning": {...}?}.

    The API returns a one-element list; this returns the element.
    """
    url = dashboard_url(base_url)
    try:
        async with asyncio.timeout(timeout):
            async with session.get(url, headers={"Accept": "application/json"}) as resp:
                if resp.status != 200:
                    raise WeatherParseResponseError(f"HTTP {resp.status} from {url}")
                data = await resp.json(content_type=None)
    except WeatherParseError:
        raise
    except (aiohttp.ClientError, TimeoutError) as err:
        raise WeatherParseConnectionError(f"Cannot reach {url}: {err}") from err
    except ValueError as err:
        raise WeatherParseResponseError(f"{url} did not return JSON") from err

    if isinstance(data, list) and data:
        data = data[0]
    if not isinstance(data, dict) or not isinstance(data.get("main"), dict):
        raise WeatherParseResponseError(f"{url} did not return WeatherParse dashboard data")
    return data
