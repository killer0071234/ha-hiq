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
DEVICE_SW_VERSION = "0.4.1"
DEVICE_UNKNOWN = "unknown"

# Model of an expansion module by its card id (cNAD.mmNN_iex_card_id).
# 0 means no module and is never looked up.
IEX_CARD_MODELS: Final = {
    1: "OP-1",
    2: "FC mk1",
    3: "TS",
    4: "8C",
    5: "LC-S",
    6: "LC-D",
    7: "FC mk2",
    8: "SW-L",
    9: "SW-W",
    10: "OP-2",
    11: "Bio-24",
    12: "AiR-12",
    13: "AiV-12",
    14: "AiC-12",
    15: "AoV-12",
    17: "IPU",
    18: "OP-3",
    19: "O2",
    20: "OP-4",
    22: "Bio-8R4",
    23: "SW-W2",
    24: "SW-W3",
    26: "TS-H mk1",
    27: "LC-DC",
    28: "OP-5",
    29: "COM-DMX",
    30: "COM-Abus",
    31: "CR-W2",
    32: "SMB-10",
    34: "COM-PRN",
    35: "GSM-1",
    36: "Bi-24",
    37: "OP-6",
    38: "COM-WXT",
    39: "RC-A",
    40: "GW-MP",
    41: "SW-W3-TIR",
    42: "GW-ENO",
    43: "COM-SAT",
    44: "COM-SAN",
    45: "COM-KAC",
    46: "COM-PMI",
    47: "COM-NOK",
    48: "Bio-20",
    49: "SMB-8",
    50: "HR-2-IQ",
    51: "COM-BON",
    52: "HR-2-IO",
    53: "OC-1-IQ",
    54: "SC-4-IO",
    55: "OP-8",
    56: "COM-MB",
    57: "GW-ENO2",
    58: "COM-PGM",
    59: "FC-2",
    60: "LC-10-IQ",
    61: "LD-V4-IQ",
    62: "LD-D8-IQ",
    63: "BC-5-IQ",
    64: "SC-4-IQ",
    65: "TH-1-IQ",
    66: "TH-2-IQ",
    67: "FC-1-IQ",
    68: "LD-P4-IQ",
    69: "TH-3-IQ",
    # 70, 71 from the variable descriptions of the controller
    70: "TH-1T",
    71: "SC-4T",
    72: "LD-D10-IQ",
    73: "LC-8-IQ",
    116: "Bio-24-PWM",
    137: "RFMSND",
    200: "LC-DC2",
    202: "CR-D",
    203: "TS-S",
    204: "V-COM",
    205: "SW-W4",
    206: "TGP-S",
    207: "FC-3",
    208: "TS-H mk2",
    9999: "TH-X-IQ",
}

LOGGER = logging.getLogger(__package__)
SCAN_INTERVAL = timedelta(seconds=10)
SCAN_INTERVAL_ADDON = timedelta(seconds=5)

DEFAULT_HOST = "85493909-cybroscgiserver"
DEFAULT_PORT = 4000
DEFAULT_NAME = "hiq custom sensor"

# Options

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
ATTR_VARIABLE = "variable"

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

# Schemas
CONF_TAG = "tag"
CONF_INDEX = "index"
