"""Constants for the WeatherParse integration.

WeatherParse for Home Assistant
Copyright (C) 2026 WeatherParse contributors
SPDX-License-Identifier: Apache-2.0
"""

DOMAIN = "weatherparse"

CONF_URL = "url"
CONF_VERIFY_SSL = "verify_ssl"
CONF_SCAN_INTERVAL = "scan_interval"

DEFAULT_SCAN_INTERVAL = 60  # seconds; the Access reports every 5 minutes, the dashboard data changes each minute
MIN_SCAN_INTERVAL = 30

# WeatherParse (and Acuparse 3.x) dashboard JSON
DASHBOARD_PATH = "/api/v1/json/dashboard/"

MANUFACTURER = "AcuRite (via WeatherParse)"
