"""Config flow: ask for the WeatherParse address, check it answers, then create the entry.

WeatherParse for Home Assistant
Copyright (C) 2026 WeatherParse contributors
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

import voluptuous as vol

from homeassistant.config_entries import ConfigFlow, ConfigFlowResult, OptionsFlow
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import WeatherParseConnectionError, WeatherParseResponseError, fetch_dashboard
from .const import (
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from .coordinator import WeatherParseConfigEntry


def normalize_url(url: str) -> str:
    """http://host/ style base address; adds http:// when no scheme was typed."""
    url = url.strip()
    if "://" not in url:
        url = "http://" + url
    parsed = urlparse(url)
    return f"{parsed.scheme}://{parsed.netloc}{parsed.path.rstrip('/')}"


class WeatherParseConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for WeatherParse."""

    VERSION = 1

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            url = normalize_url(user_input[CONF_URL])
            verify_ssl = user_input.get(CONF_VERIFY_SSL, False)
            await self.async_set_unique_id(url)
            self._abort_if_unique_id_configured()
            session = async_get_clientsession(self.hass, verify_ssl=verify_ssl)
            try:
                await fetch_dashboard(session, url)
            except WeatherParseConnectionError:
                errors["base"] = "cannot_connect"
            except WeatherParseResponseError:
                errors["base"] = "invalid_response"
            else:
                # The name becomes the device name and so the start of every entity ID
                # (My WeatherParse Station -> sensor.my_weatherparse_station_temperature); without one, WeatherParse plus the host
                name = (user_input.get(CONF_NAME) or "").strip()
                return self.async_create_entry(
                    title=name or f"WeatherParse {urlparse(url).netloc or url}",
                    data={CONF_URL: url, CONF_VERIFY_SSL: verify_ssl},
                )

        schema = vol.Schema(
            {
                vol.Required(CONF_URL, default=(user_input or {}).get(CONF_URL, "http://")): str,
                vol.Optional(CONF_VERIFY_SSL, default=(user_input or {}).get(CONF_VERIFY_SSL, False)): bool,
                vol.Optional(CONF_NAME, default=(user_input or {}).get(CONF_NAME, "")): str,
            }
        )
        return self.async_show_form(step_id="user", data_schema=schema, errors=errors)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: WeatherParseConfigEntry) -> OptionsFlow:
        return WeatherParseOptionsFlow()


class WeatherParseOptionsFlow(OptionsFlow):
    """Polling interval."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(data=user_input)
        current = self.config_entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL)
        schema = vol.Schema(
            {
                vol.Required(CONF_SCAN_INTERVAL, default=current): vol.All(
                    vol.Coerce(int), vol.Range(min=MIN_SCAN_INTERVAL, max=3600)
                )
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
