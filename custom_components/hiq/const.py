"""Constants for the HIQ-Home integration."""

import logging
from datetime import timedelta
from typing import Final

from cybro.abus import SocketDef

# Integration domain
DOMAIN = "hiq"

MANUFACTURER = "Robotina D.o.o."
MANUFACTURER_URL = "http://hiq-home.com/"
DOCS_URL = "https://github.com/killer0071234/ha-hiq#through-the-cybroscgiserver"
ATTRIBUTION_PLC = "Data read from HIQ controller"
DEVICE_DESCRIPTION = "HIQ controller"
DEVICE_HW_VERSION = "2/3"
DEVICE_SW_VERSION = "0.7.1"
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
SCAN_INTERVAL_DIRECT = timedelta(seconds=5)
# A-bus broadcast scan for new controllers
SCAN_INTERVAL_DISCOVERY = timedelta(minutes=15)

# the HIQ program sets cNAD.program_id to this value (docs/abus-notes.md)
HIQ_PROGRAM_ID = "3"

# scenes of lights and blinds (SC-4-IQ), cNAD.scene_status[0..31]
SCENE_COUNT = 32

# socket 1 of the HIQ program, "HIQ-to-HIQ sync" (tasks/sockets-plan.md):
# messages of a direct controller, received on UDP port 8442
HIQ_SOCKET = SocketDef(
    1,
    bits=("socket_req",),
    ints=(
        "socket_command",
        "socket_argument_0",
        "socket_argument_1",
        "socket_argument_2",
        "socket_argument_3",
    ),
    longs=("socket_from", "socket_to"),
)
# socket_command of a button input event: argument 0 is the input number
# (0..79: lc00..lc07, 100..139: ld00..ld03), argument 1 the event type
SOCKET_INPUT_EVENT = 0
INPUT_EVENT_TYPES = ["short_press", "short_release", "long_press", "long_release"]
# every socket message refreshes the values, not before this delay [s]
SOCKET_REFRESH_DELAY = 1.0

# how the controller is reached
CONF_CONNECTION = "connection"
CONNECTION_SCGI = "scgi"
CONNECTION_DIRECT = "direct"

# repair issue: the A-bus port is used by another program
ISSUE_PORT_IN_USE = "port_in_use"

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
