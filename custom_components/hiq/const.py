"""Constants for the HIQ-Home integration."""
import logging
from datetime import timedelta
from typing import Final

# Integration domain
DOMAIN = "hiq"

MANUFACTURER = "Robotina D.o.o."
MANUFACTURER_URL = "http://hiq-home.com/"
ATTRIBUTION_PLC = "Data read from HIQ controller"
DEVICE_DESCRIPTION = "HIQ controller"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)

# Options
CONF_IGNORE_GENERAL_ERROR = "ignore_general_error"

# Attributes
AREA_SYSTEM = "System"
AREA_ENERGY = "Energy"
AREA_WEATHER = "Weather"
AREA_LIGHTS = "Lights"
AREA_BLINDS = "Blinds"
ATTR_DESCRIPTION = "description"

# Device classes
DEVICE_CLASS_HIQ_LIVE_OVERRIDE: Final = "hiq__live_override"

# Services
SERVICE_PRESENCE_SIGNAL = "presence_signal"
SERVICE_CHARGE_ON = "charge_on_event"
SERVICE_CHARGE_OFF = "charge_off_event"
SERVICE_HOME = "home_event"
SERVICE_ALARM = "alarm_event"
SERVICE_PRECEDE = "precede_event"
SERVICE_WRITE_TAG = "write_tag"
