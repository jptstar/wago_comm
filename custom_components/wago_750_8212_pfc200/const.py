"""Constants for WAGO 750-8212 PFC200."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "wago_750_8212_pfc200"
NAME: Final = "WAGO 750-8212 PFC200"
MANUFACTURER: Final = "WAGO"
MODEL: Final = "750-8212 PFC200"

CONF_UNIT_ID: Final = "unit_id"
CONF_RECONNECT_DELAY: Final = "reconnect_delay"
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_POINTS_REVISION: Final = "points_revision"

CONF_COIL_START: Final = "coil_start"
CONF_COIL_SIZE: Final = "coil_size"
CONF_DISCRETE_START: Final = "discrete_start"
CONF_DISCRETE_SIZE: Final = "discrete_size"
CONF_HOLDING_START: Final = "holding_start"
CONF_HOLDING_SIZE: Final = "holding_size"
CONF_INPUT_START: Final = "input_start"
CONF_INPUT_SIZE: Final = "input_size"

DEFAULT_PORT: Final = 502
DEFAULT_UNIT_ID: Final = 1
DEFAULT_TIMEOUT: Final = 3.0
DEFAULT_RECONNECT_DELAY: Final = 5.0
DEFAULT_SCAN_INTERVAL: Final = 2

DEFAULT_MEMORY: Final = {
    CONF_COIL_START: 0,
    CONF_COIL_SIZE: 48,
    CONF_DISCRETE_START: 50,
    CONF_DISCRETE_SIZE: 8,
    CONF_HOLDING_START: 60,
    CONF_HOLDING_SIZE: 40,
    CONF_INPUT_START: 100,
    CONF_INPUT_SIZE: 3,
}

TABLE_COIL: Final = "coil"
TABLE_DISCRETE: Final = "discrete_input"
TABLE_HOLDING: Final = "holding_register"
TABLE_INPUT: Final = "input_register"
TABLES: Final = (TABLE_COIL, TABLE_DISCRETE, TABLE_HOLDING, TABLE_INPUT)

PLATFORM_SENSOR: Final = "sensor"
PLATFORM_BINARY_SENSOR: Final = "binary_sensor"
PLATFORM_SWITCH: Final = "switch"
PLATFORM_NUMBER: Final = "number"
PLATFORM_BUTTON: Final = "button"
PLATFORM_SELECT: Final = "select"
POINT_PLATFORMS: Final = (
    PLATFORM_SENSOR,
    PLATFORM_BINARY_SENSOR,
    PLATFORM_SWITCH,
    PLATFORM_NUMBER,
    PLATFORM_BUTTON,
    PLATFORM_SELECT,
)

DATA_BOOL: Final = "bool"
DATA_UINT16: Final = "uint16"
DATA_INT16: Final = "int16"
DATA_UINT32: Final = "uint32"
DATA_INT32: Final = "int32"
DATA_FLOAT32: Final = "float32"
DATA_TYPES: Final = (
    DATA_BOOL,
    DATA_UINT16,
    DATA_INT16,
    DATA_UINT32,
    DATA_INT32,
    DATA_FLOAT32,
)

BYTE_BIG: Final = "big"
BYTE_LITTLE: Final = "little"
WORD_BIG: Final = "big"
WORD_LITTLE: Final = "little"

MAX_POINTS: Final = 100
STORAGE_VERSION: Final = 1
STORAGE_KEY_PREFIX: Final = f"{DOMAIN}.points"

PLATFORMS: Final = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.NUMBER,
    Platform.BUTTON,
    Platform.SELECT,
)
