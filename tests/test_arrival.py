import asyncio
from datetime import timedelta
from unittest.mock import patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_mock_service
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from custom_components.muziek_thuiskomst.const import DEFAULTS, DOMAIN

NOON = dt_util.now().replace(hour=12, minute=0, second=0, microsecond=0)


def _data(**kw):
    d = dict(DEFAULTS)
    d.update(person="person.frits", spotify="media_player.spotify_frits",
             speakers=["media_player.woonkamer", "media_player.keuken"], spotify_source="Woonkamer")
    d.update(kw)
    return d


@pytest.fixture
async def calls(hass):
    for comp in ("homeassistant", "person", "media_player"):
        assert await async_setup_component(hass, comp, {})
    return {
        "select_source": async_mock_service(hass, "media_player", "select_source"),
        "media_play": async_mock_service(hass, "media_player", "media_play"),
        "media_pause": async_mock_service(hass, "media_player", "media_pause"),
        "join": async_mock_service(hass, "media_player", "join"),
        "volume_set": async_mock_service(hass, "media_player", "volume_set"),
        "play_media": async_mock_service(hass, "media_player", "play_media"),
        "media_seek": async_mock_service(hass, "media_player", "media_seek"),
        "update": async_mock_service(hass, "homeassistant", "update_entity"),
    }


async def _setup(hass, **kw):
    hass.states.async_set("person.frits", "not_home", {"friendly_name": "Frits"})
    hass.states.async_set("person.vriendin", "not_home", {"friendly_name": "Vriendin"})
    hass.states.async_set("media_player.woonkamer", "idle", {"friendly_name": "Woonkamer"})
    hass.states.async_set(
        "media_player.spotify_frits", "playing",
        {"source_list": ["Woonkamer", "Telefoon"], "media_content_id": "spotify:track:abc",
         "media_position": 60, "media_position_updated_at": dt_util.utcnow()},
    )
    entry = MockConfigEntry(domain=DOMAIN, data=_data(**kw), unique_id="person.frits", title="Frits")
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return entry


async def _settle(hass):
    for _ in range(20):
        await asyncio.sleep(0)
        await hass.async_block_till_done()


async def _arrive(hass):
    with patch("custom_components.muziek_thuiskomst.manager.dt_util.now", return_value=NOON):
        hass.states.async_set("person.frits", "home", {"friendly_name": "Frits"})
        await _settle(hass)


async def test_transfer_when_alone(hass, calls):
    entry = await _setup(hass)
    await _arrive(hass)
    m = entry.runtime_data
    assert m.status == "transferred", m.reason
    assert calls["select_source"][0].data["source"] == "Woonkamer"
    assert calls["join"][0].data["group_members"] == ["media_player.keuken"]
    assert calls["volume_set"][0].data["volume_level"] == 0.25
    assert len(calls["media_play"]) == 1


async def test_skip_when_partner_home(hass, calls):
    entry = await _setup(hass)
    hass.states.async_set("person.vriendin", "home", {"friendly_name": "Vriendin"})
    await _arrive(hass)
    assert entry.runtime_data.status == "skipped"
    assert "Vriendin" in entry.runtime_data.reason
    assert not calls["select_source"]


async def test_partner_home_allowed_when_option_off(hass, calls):
    entry = await _setup(hass, only_alone=False)
    hass.states.async_set("person.vriendin", "home", {"friendly_name": "Vriendin"})
    await _arrive(hass)
    assert entry.runtime_data.status == "transferred"


async def test_skip_outside_window(hass, calls):
    entry = await _setup(hass)
    with patch("custom_components.muziek_thuiskomst.manager.dt_util.now",
               return_value=NOON.replace(hour=2)):
        hass.states.async_set("person.frits", "home")
        await hass.async_block_till_done()
    assert entry.runtime_data.status == "skipped"
    assert not calls["select_source"]


async def test_paused_long_ago_skips(hass, calls):
    entry = await _setup(hass)
    hass.states.async_set("media_player.spotify_frits", "paused", {"source_list": ["Woonkamer"]})
    st = hass.states.get("media_player.spotify_frits")
    with patch("custom_components.muziek_thuiskomst.manager.dt_util.utcnow",
               return_value=st.last_changed + timedelta(minutes=30)):
        await _arrive(hass)
    assert entry.runtime_data.status == "skipped"


async def test_disabled_switch(hass, calls):
    entry = await _setup(hass)
    entry.runtime_data.enabled = False
    await _arrive(hass)
    assert entry.runtime_data.status == "skipped"
    assert not calls["select_source"]


async def test_waits_for_car(hass, calls):
    hass.states.async_set("sensor.tel_bt", "1", {"connected_paired_devices": ["AA:BB (Skoda Octavia)"]})
    entry = await _setup(hass, bt_sensor="sensor.tel_bt", car_name="skoda")
    await _arrive(hass)
    assert entry.runtime_data.status == "waiting_car"
    assert not calls["select_source"]
    with patch("custom_components.muziek_thuiskomst.manager.dt_util.now", return_value=NOON):
        hass.states.async_set("sensor.tel_bt", "0", {"connected_paired_devices": []})
        hass.states.async_set("media_player.spotify_frits", "paused", {"source_list": ["Woonkamer"]})
        await _settle(hass)
    assert entry.runtime_data.status == "transferred", entry.runtime_data.reason
    assert len(calls["select_source"]) == 1


async def test_leave_again_while_waiting(hass, calls):
    hass.states.async_set("sensor.tel_bt", "1", {"connected_paired_devices": ["Skoda"]})
    entry = await _setup(hass, bt_sensor="sensor.tel_bt", car_name="Skoda")
    await _arrive(hass)
    hass.states.async_set("person.frits", "not_home")
    await _settle(hass)
    assert entry.runtime_data.status == "skipped"
    assert entry.runtime_data.reason == "weer vertrokken"


async def test_fallback_direct_sonos(hass, calls):
    entry = await _setup(hass, spotify_source="Niet bestaand")
    await _arrive(hass)
    assert entry.runtime_data.status == "transferred"
    assert not calls["select_source"]
    assert calls["play_media"][0].data["media_content_id"] == "spotify:track:abc"
    assert calls["media_seek"][0].data["seek_position"] >= 60
    assert len(calls["media_pause"]) == 1


async def test_error_without_fallback(hass, calls):
    entry = await _setup(hass, spotify_source="Niet bestaand", sonos_fallback=False)
    await _arrive(hass)
    assert entry.runtime_data.status == "error"


async def test_button_and_entities(hass, calls):
    entry = await _setup(hass)
    states = [s.entity_id for s in hass.states.async_all() if "muziek" in s.entity_id]
    button = next(s for s in states if s.startswith("button."))
    await hass.services.async_call("button", "press", {"entity_id": button}, blocking=True)
    assert entry.runtime_data.status == "transferred"
    status = next(s for s in states if s.startswith("sensor.") and s.endswith("status"))
    assert hass.states.get(status).state == "transferred"
    assert await hass.config_entries.async_unload(entry.entry_id)
