from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType

from custom_components.muziek_thuiskomst.const import DOMAIN


async def test_full_flow(hass):
    hass.states.async_set("person.frits", "not_home", {"friendly_name": "Frits"})
    hass.states.async_set("media_player.spotify_frits", "playing", {"source_list": ["Woonkamer", "Keuken"]})
    hass.states.async_set("media_player.woonkamer", "idle")

    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert r["step_id"] == "user"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"person": "person.frits", "spotify": "media_player.spotify_frits"}
    )
    assert r["step_id"] == "speakers"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"speakers": ["media_player.woonkamer"], "spotify_source": "Woonkamer",
         "set_volume": True, "volume": 30, "sonos_fallback": True},
    )
    assert r["step_id"] == "logic"
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"only_alone": True, "start_time": "07:00:00", "end_time": "23:00:00",
         "pause_margin": 10, "bt_sensor": "sensor.tel_bt", "bt_timeout": 10},
    )
    assert r["type"] == FlowResultType.FORM
    assert r["errors"] == {"car_name": "car_name_required"}
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"],
        {"only_alone": True, "start_time": "07:00:00", "end_time": "23:00:00",
         "pause_margin": 10, "bt_sensor": "sensor.tel_bt", "car_name": "Skoda", "bt_timeout": 10},
    )
    assert r["type"] == FlowResultType.CREATE_ENTRY
    assert r["title"] == "Frits"
    assert r["data"]["volume"] == 30
    await hass.async_block_till_done()
    assert hass.states.get("switch.muziek_thuiskomst_frits_automatisch_overzetten") or \
        hass.states.get("switch.muziek_thuiskomst_frits_automatic_transfer")

    # options: speakers aanpassen
    entry = hass.config_entries.async_entries(DOMAIN)[0]
    r = await hass.config_entries.options.async_init(entry.entry_id)
    assert r["type"] == FlowResultType.MENU
    r = await hass.config_entries.options.async_configure(r["flow_id"], {"next_step_id": "speakers"})
    r = await hass.config_entries.options.async_configure(
        r["flow_id"],
        {"speakers": ["media_player.woonkamer", "media_player.keuken"], "spotify_source": "Woonkamer",
         "set_volume": False, "volume": 30, "sonos_fallback": True},
    )
    assert r["type"] == FlowResultType.CREATE_ENTRY
    await hass.async_block_till_done()
    assert entry.runtime_data.cfg["speakers"] == ["media_player.woonkamer", "media_player.keuken"]
    assert entry.runtime_data.cfg["car_name"] == "Skoda"

    # dubbele persoon
    r = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    r = await hass.config_entries.flow.async_configure(
        r["flow_id"], {"person": "person.frits", "spotify": "media_player.spotify_frits"}
    )
    assert r["type"] == FlowResultType.ABORT
