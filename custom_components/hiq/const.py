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
DEVICE_HW_VERSION = "2/3"
DEVICE_SW_VERSION = "0.2.0"

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)
SCAN_INTERVAL_ADDON = timedelta(seconds=5)

DEFAULT_HOST = "85493909-cybroscgiserver"
DEFAULT_PORT = 4000

# Options
CONF_IGNORE_GENERAL_ERROR = "ignore_general_error"

# Attributes
AREA_SYSTEM = "System"
AREA_ENERGY = "Energy"
AREA_WEATHER = "Weather"
AREA_LIGHTS = "Lights"
AREA_BLINDS = "Blinds"
AREA_CLIMATE = "Climate"
ATTR_DESCRIPTION = "description"
ATTR_FLOOR_TEMP = "Floor temperature"
ATTR_SETPOINT_IDLE = "Setpoint idle"
ATTR_SETPOINT_ACTIVE = "Setpoint active"
ATTR_SETPOINT_OFFSET = "Setpoint offset"
ATTR_FAN_OPTIONS = "fan_options"

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
