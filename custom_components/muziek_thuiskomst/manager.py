"""Thuiskomst-logica: wanneer, en hoe de muziek naar de speakers gaat."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import datetime, time, timedelta
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_ENTITY_ID,
    STATE_HOME,
    STATE_PLAYING,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, callback
from homeassistant.helpers.event import async_track_state_change_event
from homeassistant.util import dt as dt_util

from .const import (
    CONF_BT_SENSOR,
    CONF_BT_TIMEOUT,
    CONF_CAR_NAME,
    CONF_END,
    CONF_FALLBACK,
    CONF_ONLY_ALONE,
    CONF_PAUSE_MARGIN,
    CONF_PERSON,
    CONF_SET_VOLUME,
    CONF_SOURCE,
    CONF_SPEAKERS,
    CONF_SPOTIFY,
    CONF_START,
    CONF_VOLUME,
    DEFAULTS,
    DOMAIN,
    EVENT_TRANSFERRED,
    STATUS_ERROR,
    STATUS_IDLE,
    STATUS_SKIPPED,
    STATUS_TRANSFERRED,
    STATUS_WAITING_CAR,
)

_LOGGER = logging.getLogger(__name__)

MP = "media_player"
STATE_PAUSED = "paused"

# Wachttijden in seconden (in tests op 0 gezet).
CAR_SETTLE_DELAY = 5
TRANSFER_DELAY = 3
SEEK_DELAY = 2


def _parse_time(value: str) -> time:
    parts = [int(p) for p in str(value).split(":")]
    while len(parts) < 3:
        parts.append(0)
    return time(parts[0], parts[1], parts[2])


def in_window(now: time, start: time, end: time) -> bool:
    """Ligt `now` in het venster? Ondersteunt ook vensters over middernacht."""
    if start == end:
        return True
    if start < end:
        return start <= now < end
    return now >= start or now < end


class ArrivalManager:
    """Regelt de thuiskomst voor één persoon."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.enabled = True
        self.status = STATUS_IDLE
        self.reason: str | None = None
        self.last_transfer: datetime | None = None
        self._listeners: list[Callable[[], None]] = []
        self._unsub: Callable[[], None] | None = None
        self._task: asyncio.Task | None = None

    # ------------------------------------------------------------------ setup
    @property
    def cfg(self) -> dict[str, Any]:
        return {**DEFAULTS, **self.entry.data, **self.entry.options}

    @callback
    def async_start(self) -> None:
        self._unsub = async_track_state_change_event(
            self.hass, [self.cfg[CONF_PERSON]], self._person_changed
        )

    @callback
    def async_stop(self) -> None:
        if self._unsub:
            self._unsub()
            self._unsub = None
        if self._task and not self._task.done():
            self._task.cancel()

    @callback
    def add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    @callback
    def _set(self, status: str, reason: str | None = None) -> None:
        self.status = status
        self.reason = reason
        if status == STATUS_SKIPPED:
            _LOGGER.info("%s: overgeslagen (%s)", self.entry.title, reason)
        for update in list(self._listeners):
            update()

    # --------------------------------------------------------------- triggers
    @callback
    def _person_changed(self, event: Event[EventStateChangedData]) -> None:
        old = event.data["old_state"]
        new = event.data["new_state"]
        if new is None or new.state != STATE_HOME:
            # Weer weg terwijl we op de auto wachtten: afbreken.
            if self._task and not self._task.done():
                self._task.cancel()
            return
        if old is None or old.state in (STATE_HOME, STATE_UNKNOWN, STATE_UNAVAILABLE):
            return
        if not self.enabled:
            self._set(STATUS_SKIPPED, "uitgeschakeld")
            return
        if self._task and not self._task.done():
            return
        self._task = self.entry.async_create_background_task(
            self.hass, self._async_arrival(), f"{DOMAIN}_arrival_{self.entry.entry_id}"
        )

    # ------------------------------------------------------------------ checks
    def _blocking_reason(self) -> str | None:
        """Geeft de reden terug waarom we niet overzetten, of None."""
        cfg = self.cfg
        now = dt_util.now().time()
        if not in_window(now, _parse_time(cfg[CONF_START]), _parse_time(cfg[CONF_END])):
            return f"buiten tijdvenster {cfg[CONF_START][:5]}-{cfg[CONF_END][:5]}"

        if cfg[CONF_ONLY_ALONE]:
            others = [
                st.name
                for st in self.hass.states.async_all("person")
                if st.entity_id != cfg[CONF_PERSON] and st.state == STATE_HOME
            ]
            if others:
                return "al thuis: " + ", ".join(others)

        spotify = self.hass.states.get(cfg[CONF_SPOTIFY])
        if spotify is None:
            return "Spotify-speler niet gevonden"
        if spotify.state == STATE_PLAYING:
            return None
        if spotify.state == STATE_PAUSED:
            margin = timedelta(minutes=cfg[CONF_PAUSE_MARGIN])
            if dt_util.utcnow() - spotify.last_changed <= margin:
                return None
            return f"Spotify al langer dan {cfg[CONF_PAUSE_MARGIN]} min gepauzeerd"
        return "Spotify speelt niet"

    async def _async_refresh_spotify(self) -> None:
        try:
            await self.hass.services.async_call(
                "homeassistant",
                "update_entity",
                {ATTR_ENTITY_ID: self.cfg[CONF_SPOTIFY]},
                blocking=True,
            )
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Verversen Spotify mislukt", exc_info=True)

    def _car_connected(self) -> bool:
        cfg = self.cfg
        state = self.hass.states.get(cfg[CONF_BT_SENSOR])
        if state is None:
            return False
        devices = state.attributes.get("connected_paired_devices") or []
        if isinstance(devices, str):
            devices = [devices]
        car = cfg[CONF_CAR_NAME].strip().lower()
        return any(car in str(dev).lower() for dev in devices)

    async def _async_wait_car_gone(self) -> bool:
        """Wacht tot de auto-Bluetooth weg is. False bij timeout."""
        if not self._car_connected():
            return True
        self._set(STATUS_WAITING_CAR, "muziek speelt nog in de auto")
        done: asyncio.Future[bool] = self.hass.loop.create_future()

        @callback
        def _changed(_event: Event[EventStateChangedData]) -> None:
            if not self._car_connected() and not done.done():
                done.set_result(True)

        unsub = async_track_state_change_event(
            self.hass, [self.cfg[CONF_BT_SENSOR]], _changed
        )
        try:
            async with asyncio.timeout(self.cfg[CONF_BT_TIMEOUT] * 60):
                await done
            return True
        except TimeoutError:
            return False
        finally:
            unsub()

    # --------------------------------------------------------------- arrival
    async def _async_arrival(self) -> None:
        try:
            await self._async_refresh_spotify()
            if reason := self._blocking_reason():
                self._set(STATUS_SKIPPED, reason)
                return

            if self.cfg[CONF_BT_SENSOR] and self.cfg[CONF_CAR_NAME]:
                if not await self._async_wait_car_gone():
                    self._set(STATUS_SKIPPED, "auto bleef verbonden")
                    return
                # Spotify-integratie even de tijd geven om de pauze te zien.
                await asyncio.sleep(CAR_SETTLE_DELAY)
                await self._async_refresh_spotify()
                if reason := self._blocking_reason():
                    self._set(STATUS_SKIPPED, reason)
                    return

            await self.async_transfer("thuiskomst")
        except asyncio.CancelledError:
            self._set(STATUS_SKIPPED, "weer vertrokken")
            raise

    # -------------------------------------------------------------- transfer
    def _resolve_source(self) -> tuple[str, list[str]]:
        cfg = self.cfg
        spotify = self.hass.states.get(cfg[CONF_SPOTIFY])
        sources = list(spotify.attributes.get("source_list") or []) if spotify else []
        source = (cfg[CONF_SOURCE] or "").strip()
        if not source:
            main = self.hass.states.get(cfg[CONF_SPEAKERS][0])
            source = main.name if main else ""
        return source, sources

    async def _call(self, domain: str, service: str, data: dict[str, Any]) -> None:
        await self.hass.services.async_call(domain, service, data, blocking=True)

    async def async_transfer(self, trigger: str = "handmatig") -> None:
        """Zet de muziek over naar de speakers, zonder voorwaarden te checken."""
        cfg = self.cfg
        speakers: list[str] = cfg[CONF_SPEAKERS]
        main = speakers[0]
        spotify_id = cfg[CONF_SPOTIFY]
        try:
            if len(speakers) > 1:
                await self._call(
                    MP, "join", {ATTR_ENTITY_ID: main, "group_members": speakers[1:]}
                )
            if cfg[CONF_SET_VOLUME]:
                await self._call(
                    MP,
                    "volume_set",
                    {ATTR_ENTITY_ID: speakers, "volume_level": cfg[CONF_VOLUME] / 100},
                )

            source, sources = self._resolve_source()
            spotify = self.hass.states.get(spotify_id)
            method = "spotify_connect"
            if source and source in sources:
                await self._call(MP, "select_source", {ATTR_ENTITY_ID: spotify_id, "source": source})
                await asyncio.sleep(TRANSFER_DELAY)
                await self._call(MP, "media_play", {ATTR_ENTITY_ID: spotify_id})
            elif cfg[CONF_FALLBACK] and spotify and spotify.attributes.get("media_content_id"):
                method = "sonos_direct"
                await self._async_play_direct(main, spotify)
            else:
                self._set(
                    STATUS_ERROR,
                    f"'{source}' staat niet in de Spotify-apparatenlijst "
                    f"({', '.join(sources) or 'leeg'})",
                )
                return
        except Exception as err:  # noqa: BLE001
            _LOGGER.exception("Overzetten naar %s mislukt", main)
            self._set(STATUS_ERROR, str(err))
            return

        self.last_transfer = dt_util.utcnow()
        self._set(STATUS_TRANSFERRED, f"{trigger} via {method} naar {source or main}")
        self.hass.bus.async_fire(
            EVENT_TRANSFERRED,
            {
                "person": cfg[CONF_PERSON],
                "speakers": speakers,
                "method": method,
                "trigger": trigger,
            },
        )

    async def _async_play_direct(self, speaker: str, spotify) -> None:
        """Noodroute: laat de Sonos zelf het nummer afspelen en spoel door."""
        attrs = spotify.attributes
        uri = attrs["media_content_id"]
        position = attrs.get("media_position") or 0
        updated = attrs.get("media_position_updated_at")
        if spotify.state == STATE_PLAYING and updated:
            if isinstance(updated, str):
                updated = dt_util.parse_datetime(updated)
            if updated:
                position += (dt_util.utcnow() - updated).total_seconds()

        # Telefoon/auto stoppen, zodat er niet twee keer muziek speelt.
        try:
            await self._call(MP, "media_pause", {ATTR_ENTITY_ID: spotify.entity_id})
        except Exception:  # noqa: BLE001
            _LOGGER.debug("Pauzeren Spotify mislukt", exc_info=True)

        await self._call(
            MP,
            "play_media",
            {
                ATTR_ENTITY_ID: speaker,
                "media_content_id": uri,
                "media_content_type": "music",
                "enqueue": "replace",
            },
        )
        if position > 5:
            await asyncio.sleep(SEEK_DELAY)
            try:
                await self._call(
                    MP, "media_seek", {ATTR_ENTITY_ID: speaker, "seek_position": position}
                )
            except Exception:  # noqa: BLE001
                _LOGGER.debug("Doorspoelen mislukt", exc_info=True)
