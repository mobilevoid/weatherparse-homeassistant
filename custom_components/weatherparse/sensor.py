"""WeatherParse sensors.

WeatherParse for Home Assistant
Copyright (C) 2026 WeatherParse contributors
SPDX-License-Identifier: Apache-2.0
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.const import (
    DEGREE,
    LIGHT_LUX,
    PERCENTAGE,
    UV_INDEX,
    UnitOfLength,
    UnitOfPrecipitationDepth,
    UnitOfPressure,
    UnitOfSpeed,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.util import dt as dt_util

from .const import DOMAIN, MANUFACTURER
from .coordinator import WeatherParseConfigEntry, WeatherParseCoordinator

# Timestamps before this mean "never" (WeatherParse/Acuparse can report the Unix epoch for an empty value)
_NEVER_BEFORE = datetime(2000, 1, 1, tzinfo=dt_util.UTC)


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _integer(value: Any) -> int | None:
    number = _number(value)
    return None if number is None else int(round(number))


def _timestamp(value: Any) -> datetime | None:
    if not value:
        return None
    parsed = dt_util.parse_datetime(str(value))
    if parsed is None or parsed < _NEVER_BEFORE:
        return None
    return parsed


def _text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None


@dataclass(frozen=True, kw_only=True)
class WeatherParseSensorDescription(SensorEntityDescription):
    """One field of one section ("main", "atlas", "lightning") of the dashboard JSON."""

    section: str
    field: str
    convert: Callable[[Any], Any] = _number


SENSORS: tuple[WeatherParseSensorDescription, ...] = (
    # main: Iris/Atlas core readings (metric fields; Home Assistant converts to the user's units)
    WeatherParseSensorDescription(key="temperature", translation_key="temperature", section="main", field="tempC",
        device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1),
    WeatherParseSensorDescription(key="feels_like", translation_key="feels_like", section="main", field="feelsC",
        device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1),
    WeatherParseSensorDescription(key="dew_point", translation_key="dew_point", section="main", field="dewptC",
        device_class=SensorDeviceClass.TEMPERATURE, native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=1),
    WeatherParseSensorDescription(key="temperature_high", translation_key="temperature_high", section="main",
        field="tempC_high", device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS, suggested_display_precision=1),
    WeatherParseSensorDescription(key="temperature_low", translation_key="temperature_low", section="main",
        field="tempC_low", device_class=SensorDeviceClass.TEMPERATURE,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS, suggested_display_precision=1),
    WeatherParseSensorDescription(key="humidity", translation_key="humidity", section="main", field="relH", convert=_integer,
        device_class=SensorDeviceClass.HUMIDITY, native_unit_of_measurement=PERCENTAGE,
        state_class=SensorStateClass.MEASUREMENT),
    WeatherParseSensorDescription(key="wind_speed", translation_key="wind_speed", section="main", field="windSpeedKMH",
        device_class=SensorDeviceClass.WIND_SPEED, native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT),
    WeatherParseSensorDescription(key="wind_gust", translation_key="wind_gust", section="main", field="windGustKMH",
        device_class=SensorDeviceClass.WIND_SPEED, native_unit_of_measurement=UnitOfSpeed.KILOMETERS_PER_HOUR,
        state_class=SensorStateClass.MEASUREMENT),
    WeatherParseSensorDescription(key="wind_direction", translation_key="wind_direction", section="main", field="windDEG",
        native_unit_of_measurement=DEGREE, state_class=SensorStateClass.MEASUREMENT_ANGLE,
        device_class=SensorDeviceClass.WIND_DIRECTION),
    WeatherParseSensorDescription(key="wind_direction_cardinal", translation_key="wind_direction_cardinal", section="main",
        field="windDIR", convert=_text),
    WeatherParseSensorDescription(key="pressure", translation_key="pressure", section="main", field="pressure_kPa",
        device_class=SensorDeviceClass.ATMOSPHERIC_PRESSURE, native_unit_of_measurement=UnitOfPressure.KPA,
        state_class=SensorStateClass.MEASUREMENT, suggested_display_precision=2),
    WeatherParseSensorDescription(key="rain_today", translation_key="rain_today", section="main",
        field="rainTotalMM_today", device_class=SensorDeviceClass.PRECIPITATION,
        native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS, state_class=SensorStateClass.TOTAL_INCREASING,
        suggested_display_precision=1),
    WeatherParseSensorDescription(key="rain", translation_key="rain", section="main", field="rainMM",
        device_class=SensorDeviceClass.PRECIPITATION, native_unit_of_measurement=UnitOfPrecipitationDepth.MILLIMETERS,
        suggested_display_precision=1),
    WeatherParseSensorDescription(key="last_updated", translation_key="last_updated", section="main",
        field="lastUpdated", convert=_timestamp, device_class=SensorDeviceClass.TIMESTAMP),
    # atlas: Atlas only
    WeatherParseSensorDescription(key="uv_index", translation_key="uv_index", section="atlas", field="uvIndex", convert=_integer,
        native_unit_of_measurement=UV_INDEX, state_class=SensorStateClass.MEASUREMENT),
    WeatherParseSensorDescription(key="illuminance", translation_key="illuminance", section="atlas",
        field="lightIntensity", device_class=SensorDeviceClass.ILLUMINANCE,
        native_unit_of_measurement=LIGHT_LUX, state_class=SensorStateClass.MEASUREMENT),
    # lightning: Atlas or tower lightning detector
    WeatherParseSensorDescription(key="lightning_strikes_today", translation_key="lightning_strikes_today",
        section="lightning", field="dailystrikes", convert=_integer, state_class=SensorStateClass.TOTAL_INCREASING),
    WeatherParseSensorDescription(key="lightning_distance", translation_key="lightning_distance", section="lightning",
        field="last_strike_distance_KM", device_class=SensorDeviceClass.DISTANCE,
        native_unit_of_measurement=UnitOfLength.KILOMETERS),
    WeatherParseSensorDescription(key="lightning_last_strike", translation_key="lightning_last_strike", section="lightning",
        field="last_strike_ts", convert=_timestamp, device_class=SensorDeviceClass.TIMESTAMP),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: WeatherParseConfigEntry, async_add_entities: AddConfigEntryEntitiesCallback
) -> None:
    """Add a sensor for every reading the station provides (Atlas and lightning sensors only when present)."""
    coordinator = entry.runtime_data
    data = coordinator.data or {}
    async_add_entities(
        WeatherParseSensor(coordinator, description)
        for description in SENSORS
        if isinstance(data.get(description.section), dict) and description.field in data[description.section]
    )


class WeatherParseSensor(CoordinatorEntity[WeatherParseCoordinator], SensorEntity):
    """One reading from the station."""

    _attr_has_entity_name = True
    entity_description: WeatherParseSensorDescription

    def __init__(self, coordinator: WeatherParseCoordinator, description: WeatherParseSensorDescription) -> None:
        super().__init__(coordinator)
        self.entity_description = description
        entry = coordinator.config_entry
        self._attr_unique_id = f"{entry.unique_id or entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.unique_id or entry.entry_id)},
            name=entry.title,
            manufacturer=MANUFACTURER,
            model="Iris/Atlas weather station",
            configuration_url=coordinator.url,
        )

    @property
    def native_value(self) -> Any:
        section = (self.coordinator.data or {}).get(self.entity_description.section)
        if not isinstance(section, dict):
            return None
        return self.entity_description.convert(section.get(self.entity_description.field))

    @property
    def available(self) -> bool:
        return super().available and isinstance((self.coordinator.data or {}).get(self.entity_description.section), dict)
