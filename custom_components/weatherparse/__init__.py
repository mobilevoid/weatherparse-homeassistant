"""WeatherParse: AcuRite weather station data from a WeatherParse (or Acuparse 3.x) server.

WeatherParse for Home Assistant
Copyright (C) 2026 WeatherParse contributors
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant

from .coordinator import WeatherParseConfigEntry, WeatherParseCoordinator

PLATFORMS: list[Platform] = [Platform.SENSOR]


async def async_setup_entry(hass: HomeAssistant, entry: WeatherParseConfigEntry) -> bool:
    """Set up WeatherParse from a config entry."""
    coordinator = WeatherParseCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_reload_on_options))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: WeatherParseConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def _async_reload_on_options(hass: HomeAssistant, entry: WeatherParseConfigEntry) -> None:
    """Apply a new polling interval."""
    await hass.config_entries.async_reload(entry.entry_id)
