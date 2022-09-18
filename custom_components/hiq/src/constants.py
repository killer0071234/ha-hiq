# dir which is used to resolve all other relative paths
from pathlib import Path

APP_VERSION = "3.1.3"

APP_DIR = Path.cwd()

# path to the main configuration file
CONFIG_FILE = Path("../config.ini")

# path to the data logger configuration file
DATA_LOGGER_CONFIG_FILE = Path("../data_logger.xml")

# how often will system clear plc info table [minutes]
PLC_INFO_CLEAR_PERIOD = 10

# how long an unused entry exists in the plc info table, before it may be removed [minutes]
PLC_INFO_LIFETIME = 10

# abus maximum message size [bytes]
MAX_FRAME_BYTES = 1000

# address that the push service will use to communicate with controllers
PUSH_NAD = 1

# address that the read/write service will use to communicate with controllers
RW_NAD = 2

# address that the autodetect will use to communicate with controllers
AUTODETECT_NAD = 3

# copy log messages also to stdout
LOG_TO_STD_OUT = False

# dbase access data
DB_ENGINE = "mysql"
DATA_LOGGER_SAMPLES_TABLE = "measurements"
DATA_LOGGER_ALARMS_TABLE = "alarms"
RELAYS_TABLE = "relays"
CONTROLLERS_TABLE = "controllers"
ABUS_BROADCAST_PORT = 8442

# How often does system sync db with relay service [minutes]
DB_SYNC_TIMEOUT_MIN = 30
