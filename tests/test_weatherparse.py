"""Tests for the WeatherParse integration (network is mocked; no real station is contacted)."""

from __future__ import annotations

import copy
from datetime import timedelta
import json
from pathlib import Path
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import voluptuous as vol

from custom_components.weatherparse.api import (
    WeatherParseConnectionError,
    WeatherParseResponseError,
    dashboard_url,
)
from custom_components.weatherparse.config_flow import normalize_url
from custom_components.weatherparse.const import (
    CONF_SCAN_INTERVAL,
    CONF_URL,
    CONF_VERIFY_SSL,
    DOMAIN,
    MIN_SCAN_INTERVAL,
)
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.setup import async_setup_component

FIXTURE = json.loads((Path(__file__).parent / "dashboard.json").read_text())
URL = "http://192.0.2.10"  # documentation address, never a real station


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


def _data(drop: str | None = None) -> dict:
    data = copy.deepcopy(FIXTURE[0])
    if drop:
        data.pop(drop)
    return data


def test_url_helpers() -> None:
    assert normalize_url("192.0.2.10") == "http://192.0.2.10"
    assert normalize_url(" https://weather.example.com/ ") == "https://weather.example.com"
    assert dashboard_url("http://192.0.2.10/") == "http://192.0.2.10/api/v1/json/dashboard/"


async def test_user_flow_creates_entry(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    with patch("custom_components.weatherparse.config_flow.fetch_dashboard", return_value=_data()), patch(
        "custom_components.weatherparse.coordinator.fetch_dashboard", return_value=_data()
    ):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: "192.0.2.10/"})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "WeatherParse 192.0.2.10"
    assert result["data"] == {CONF_URL: URL, CONF_VERIFY_SSL: False}


async def test_user_flow_with_name(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch("custom_components.weatherparse.config_flow.fetch_dashboard", return_value=_data()), patch(
        "custom_components.weatherparse.coordinator.fetch_dashboard", return_value=_data()
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_URL: URL, CONF_NAME: " Back Yard "}
        )
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Back Yard"
    assert "sensor.back_yard_temperature" in {s.entity_id for s in hass.states.async_all("sensor")}


@pytest.mark.parametrize(
    ("error", "expected"),
    [(WeatherParseConnectionError("down"), "cannot_connect"), (WeatherParseResponseError("html"), "invalid_response")],
)
async def test_user_flow_errors(hass: HomeAssistant, error: Exception, expected: str) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch("custom_components.weatherparse.config_flow.fetch_dashboard", side_effect=error):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected}


async def test_duplicate_is_aborted(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, unique_id=URL, data={CONF_URL: URL}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    with patch("custom_components.weatherparse.config_flow.fetch_dashboard", return_value=_data()):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_URL: URL + "/"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def _setup(hass: HomeAssistant, data: dict) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, unique_id=URL, title="WeatherParse 192.0.2.10", data={CONF_URL: URL, CONF_VERIFY_SSL: False})
    entry.add_to_hass(hass)
    with patch("custom_components.weatherparse.coordinator.fetch_dashboard", return_value=data):
        assert await async_setup_component(hass, DOMAIN, {})
        await hass.async_block_till_done()
    return entry


async def test_sensors_from_real_data(hass: HomeAssistant) -> None:
    await _setup(hass, _data())
    states = {s.entity_id: s for s in hass.states.async_all("sensor")}
    temp = states["sensor.weatherparse_192_0_2_10_temperature"]
    assert float(temp.state) == pytest.approx(26.6, abs=0.05) or float(temp.state) == pytest.approx(79.9, abs=0.1)
    assert states["sensor.weatherparse_192_0_2_10_humidity"].state == "48"
    assert states["sensor.weatherparse_192_0_2_10_wind_direction_compass"].state == "NE"
    # Atlas and lightning sensors exist because the data has those sections
    assert "sensor.weatherparse_192_0_2_10_uv_index" in states
    assert "sensor.weatherparse_192_0_2_10_lightning_strikes_today" in states
    # 1969 means "never": unknown, not a 1969 date
    assert states["sensor.weatherparse_192_0_2_10_last_strike"].state == "unknown"
    # feels like is null in the data: unknown, not 0
    assert states["sensor.weatherparse_192_0_2_10_feels_like"].state == "unknown"


async def test_no_atlas_no_lightning(hass: HomeAssistant) -> None:
    data = _data("atlas")
    data.pop("lightning")
    await _setup(hass, data)
    ids = {s.entity_id for s in hass.states.async_all("sensor")}
    assert "sensor.weatherparse_192_0_2_10_temperature" in ids
    assert not any("uv_index" in i or "lightning" in i or "light" == i.rsplit("_", 1)[-1] for i in ids)


async def test_station_down_marks_unavailable(hass: HomeAssistant) -> None:
    entry = await _setup(hass, _data())
    coordinator = entry.runtime_data
    with patch("custom_components.weatherparse.coordinator.fetch_dashboard", side_effect=WeatherParseConnectionError("down")):
        await coordinator.async_refresh()
        await hass.async_block_till_done()
    assert hass.states.get("sensor.weatherparse_192_0_2_10_temperature").state == "unavailable"


async def test_options_flow_sets_interval(hass: HomeAssistant) -> None:
    entry = await _setup(hass, _data())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"
    with patch("custom_components.weatherparse.coordinator.fetch_dashboard", return_value=_data()):
        result = await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SCAN_INTERVAL: 120})
        await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {CONF_SCAN_INTERVAL: 120}
    # the entry reloads with the new interval
    assert entry.runtime_data.update_interval == timedelta(seconds=120)


async def test_options_flow_rejects_short_interval(hass: HomeAssistant) -> None:
    entry = await _setup(hass, _data())
    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(vol.Invalid):
        await hass.config_entries.options.async_configure(result["flow_id"], {CONF_SCAN_INTERVAL: MIN_SCAN_INTERVAL - 1})
    assert entry.options == {}


async def test_unload(hass: HomeAssistant) -> None:
    entry = await _setup(hass, _data())
    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
