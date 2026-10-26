"""Polls the WeatherParse station.

WeatherParse for Home Assistant
Copyright (C) 2026 WeatherParse contributors
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from datetime import timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import WeatherParseError, fetch_dashboard
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)

_LOGGER = logging.getLogger(__name__)

type WeatherParseConfigEntry = ConfigEntry[WeatherParseCoordinator]


class WeatherParseCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """Fetches the dashboard JSON on a fixed interval."""

    config_entry: WeatherParseConfigEntry

    def __init__(self, hass: HomeAssistant, entry: WeatherParseConfigEntry) -> None:
        interval = max(
            MIN_SCAN_INTERVAL,
            int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)),
        )
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name=DOMAIN,
            update_interval=timedelta(seconds=interval),
        )
        self.url: str = entry.data[CONF_URL]
        self._session = async_get_clientsession(hass, verify_ssl=entry.data.get(CONF_VERIFY_SSL, True))

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await fetch_dashboard(self._session, self.url)
        except WeatherParseError as err:
            raise UpdateFailed(str(err)) from err
