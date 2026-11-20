import pytest

from custom_components.muziek_thuiskomst import manager


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    yield


@pytest.fixture(autouse=True)
def no_delays(monkeypatch):
    monkeypatch.setattr(manager, "CAR_SETTLE_DELAY", 0)
    monkeypatch.setattr(manager, "TRANSFER_DELAY", 0)
    monkeypatch.setattr(manager, "SEEK_DELAY", 0)
