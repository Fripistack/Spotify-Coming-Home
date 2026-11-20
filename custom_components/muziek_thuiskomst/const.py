"""Constanten voor Muziek Thuiskomst."""

from homeassistant.const import Platform

DOMAIN = "muziek_thuiskomst"
PLATFORMS = [Platform.SWITCH, Platform.SENSOR, Platform.BUTTON]

CONF_PERSON = "person"
CONF_SPOTIFY = "spotify"
CONF_SPEAKERS = "speakers"
CONF_SOURCE = "spotify_source"
CONF_SET_VOLUME = "set_volume"
CONF_VOLUME = "volume"
CONF_ONLY_ALONE = "only_alone"
CONF_START = "start_time"
CONF_END = "end_time"
CONF_PAUSE_MARGIN = "pause_margin"
CONF_BT_SENSOR = "bt_sensor"
CONF_CAR_NAME = "car_name"
CONF_BT_TIMEOUT = "bt_timeout"
CONF_FALLBACK = "sonos_fallback"

DEFAULTS = {
    CONF_SOURCE: "",
    CONF_SET_VOLUME: True,
    CONF_VOLUME: 25,
    CONF_ONLY_ALONE: True,
    CONF_START: "07:00:00",
    CONF_END: "23:00:00",
    CONF_PAUSE_MARGIN: 10,
    CONF_BT_SENSOR: "",
    CONF_CAR_NAME: "",
    CONF_BT_TIMEOUT: 10,
    CONF_FALLBACK: True,
}

STATUS_IDLE = "idle"
STATUS_WAITING_CAR = "waiting_car"
STATUS_TRANSFERRED = "transferred"
STATUS_SKIPPED = "skipped"
STATUS_ERROR = "error"
STATUSES = [
    STATUS_IDLE,
    STATUS_WAITING_CAR,
    STATUS_TRANSFERRED,
    STATUS_SKIPPED,
    STATUS_ERROR,
]

EVENT_TRANSFERRED = f"{DOMAIN}_overgezet"
