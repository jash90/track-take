from tracktake import presets


def catalog():
    return [
        {"gpu": "RTX_4090", "label": "RTX 4090", "suitable": True, "matching": 40, "speed": 1.0, "speed_measured": True,
         "hosts": [{"gpus": 1, "offers": 10, "min_dph": 0.40}, {"gpus": 8, "offers": 3, "min_dph": 3.2}]},
        {"gpu": "H100_NVL", "label": "H100 NVL", "suitable": True, "matching": 1, "speed": 2.5, "speed_measured": False,
         "hosts": [{"gpus": 1, "offers": 1, "min_dph": 3.06}]},
        {"gpu": "B200", "label": "B200", "suitable": True, "matching": 2, "speed": 3.9, "speed_measured": False,
         "hosts": [{"gpus": 1, "offers": 2, "min_dph": 6.3}]},
        {"gpu": "Tesla_V100", "label": "Tesla V100", "suitable": False, "matching": 9, "speed": 0.4,
         "speed_measured": False, "hosts": [{"gpus": 1, "offers": 9, "min_dph": 0.1}]},
    ]


def test_three_presets_are_sane():
    got = {p["id"]: p for p in presets.presets(catalog(), 45, 55.0, 0.17, 0.05)}
    assert set(got) == {"cheapest", "recommended", "fastest"}
    assert got["cheapest"]["gpu"] == "RTX_4090" and got["cheapest"]["workers"] == 1 and got["cheapest"]["gpus"] == 1
    assert got["fastest"]["minutes"] <= got["recommended"]["minutes"] <= got["cheapest"]["minutes"]
    assert got["fastest"]["usd"] <= max(got["cheapest"]["usd"] * 3, got["cheapest"]["usd"] + 1.5)
    assert all(p["gpu"] != "Tesla_V100" for p in got.values())  # unsuitable cards never offered
    assert got["cheapest"]["max_dph"] >= 0.40  # the chosen host fits under the saved per-GPU limit


def test_no_offers_no_presets():
    assert presets.presets([], 45, 55.0, 0.17, 0.05) == []
