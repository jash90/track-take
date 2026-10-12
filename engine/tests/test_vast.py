import json
import time

import pytest

from sunomv import config, vast
from sunomv.config import VastSettings

OFFERS = [
    {"id": 1, "gpu_name": "RTX 4090", "dph_total": 0.34, "reliability2": 0.997, "inet_down": 765, "disk_space": 1486,
     "geolocation": "Romania, RO"},
    {"id": 2, "gpu_name": "RTX 4090", "dph_total": 0.55, "reliability2": 0.99, "inet_down": 900, "disk_space": 300,
     "geolocation": "Poland, PL"},
    {"id": 3, "gpu_name": "RTX 4090", "dph_total": 0.95, "reliability2": 0.999, "inet_down": 2000, "disk_space": 500,
     "geolocation": "Germany, DE"},
]


class FakeCli:
    def __init__(self, responses: dict):
        self.responses, self.calls = responses, []

    def __call__(self, args):
        self.calls.append(args)
        return json.dumps(self.responses[args[0]])


@pytest.fixture(autouse=True)
def isolated_state(tmp_path, monkeypatch):
    monkeypatch.setattr(vast, "STATE_DIR", tmp_path)
    monkeypatch.setattr(vast, "STATE_FILE", tmp_path / "vast.json")


def test_search_respects_max_price_and_query():
    cli = FakeCli({"search": OFFERS})
    offers = vast.search_offers(VastSettings(max_dph=0.6), run=cli)
    assert [o.id for o in offers] == [1, 2]
    query = cli.calls[0][2]
    assert "gpu_name=RTX_4090" in query and "disk_space>=120" in query and "verified=true" in query


def test_search_drops_hosts_with_expensive_downloads():
    offers = [dict(OFFERS[0], inet_down_cost=0.039), dict(OFFERS[1], inet_down_cost=0.004)]
    cli = FakeCli({"search": offers})
    found = vast.search_offers(VastSettings(max_dph=0.6), run=cli)
    assert [o.id for o in found] == [2]
    assert found[0].setup_cost(60) == pytest.approx(0.24)
    assert "inet_down_cost<=" in cli.calls[0][2]


def test_create_refuses_expensive_offer():
    offer = vast.Offer.from_raw(OFFERS[2])
    with pytest.raises(vast.VastError):
        vast.create(offer, VastSettings(max_dph=0.6), run=FakeCli({}))


def test_create_saves_state():
    cli = FakeCli({"create": {"success": True, "new_contract": 777}})
    state = vast.create(vast.Offer.from_raw(OFFERS[0]), VastSettings(), run=cli)
    assert state.instance_id == 777
    assert vast.State.load().instance_id == 777
    assert "--ssh" in cli.calls[0] and "--direct" in cli.calls[0]


def test_ssh_endpoint_prefers_direct_port():
    info = {"public_ipaddr": "1.2.3.4 ", "ports": {"22/tcp": [{"HostPort": "40022"}]},
            "ssh_host": "ssh5.vast.ai", "ssh_port": 1234}
    assert vast.ssh_endpoint(info) == ("1.2.3.4", 40022)
    assert vast.ssh_endpoint({"ssh_host": "ssh5.vast.ai", "ssh_port": 1234}) == ("ssh5.vast.ai", 1234)


def test_destroy_removes_state_and_estimates_cost():
    state = vast.State(instance_id=9, dph=0.5, created_at=time.time() - 3600)
    state.save()
    cli = FakeCli({"destroy": {}})
    cost = vast.destroy(state, run=cli)
    assert cli.calls[0][:3] == ["destroy", "instance", "9"]
    assert vast.State.load() is None
    assert cost == pytest.approx(0.5, rel=0.01)


def test_config_env_override(tmp_path, monkeypatch):
    cfg = tmp_path / "s.toml"
    cfg.write_text('[comfy]\nbackend = "local"\n[vast]\ngpu = "RTX_4090"\nlocal_port = 8189\n')
    monkeypatch.setenv("SUNOMV_COMFY_BACKEND", "vast")
    monkeypatch.setenv("SUNOMV_VAST_MODELS", "wan22_i2v, zimage")
    s = config.load(cfg)
    assert s.comfy.backend == "vast"
    assert s.comfy_url == "http://127.0.0.1:8189"
    assert s.video_engine == "wan"
    assert s.vast.models == ["wan22_i2v", "zimage"]
