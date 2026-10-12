import json
import time

import pytest

from tracktake import config, vast
from tracktake.config import VastSettings

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
    monkeypatch.setenv("TRACKTAKE_COMFY_BACKEND", "vast")
    monkeypatch.setenv("TRACKTAKE_VAST_MODELS", "wan22_i2v, zimage")
    s = config.load(cfg)
    assert s.comfy.backend == "vast"
    assert s.comfy_url == "http://127.0.0.1:8189"
    assert s.video_engine == "wan"
    assert s.vast.models == ["wan22_i2v", "zimage"]


def test_gpu_catalog_groups_offers_and_applies_filters():
    import json as _json

    from tracktake import vast
    from tracktake.config import VastSettings

    def offer(i, name, n, dph, ok=True, ram=24564, cc=890, dl=80.0):
        return {"id": i, "gpu_name": name, "num_gpus": n, "dph_total": dph, "gpu_ram": ram, "compute_cap": cc,
                "dlperf": dl * n, "direct_port_count": 2, "reliability2": 0.99 if ok else 0.5, "inet_down": 900,
                "disk_space": 500, "cuda_max_good": 13.0, "inet_down_cost": 0.001}
    raw = [offer(1, "RTX 4090", 1, 0.40), offer(2, "RTX 4090", 8, 3.2), offer(3, "RTX 4090", 1, 0.30, ok=False),
           offer(4, "RTX 5090", 1, 0.55, ram=32607, dl=160.0), offer(5, "Tesla V100", 1, 0.12, ram=32768, cc=700)]
    cat = vast.gpu_catalog(VastSettings(), {"RTX_4090": 1.0}, run=lambda args: _json.dumps(raw))
    by = {g["gpu"]: g for g in cat}
    assert by["RTX_4090"]["matching"] == 2 and by["RTX_4090"]["offers"] == 3
    assert [h["gpus"] for h in by["RTX_4090"]["hosts"]] == [1, 8] and by["RTX_4090"]["speed_measured"]
    assert 1.4 < by["RTX_5090"]["speed"] < 1.6 and not by["RTX_5090"]["speed_measured"]
    assert by["Tesla_V100"]["suitable"] is False and cat[-1]["gpu"] == "Tesla_V100"
