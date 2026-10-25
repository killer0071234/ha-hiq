"""Constants for the HIQ-Home tests."""

HOST = "192.168.1.10"
PORT = 4000
NAD = 1000
TITLE = f"c{NAD}@{HOST}:{PORT}"
UNIQUE_ID = f"c{NAD}"
# input of the scgi setup form
USER_INPUT = {"host": HOST, "port": PORT, "address": NAD}
# options of a config entry (version 3)
OPTIONS = {**USER_INPUT, "connection": "scgi"}
