"""Graphs are checked against the node schemas of the pinned ComfyUI commit (the local install, also used on Vast)."""

import json
from pathlib import Path

import pytest

from tracktake.comfy.graphs import ZIMAGE_CUDA, qwen_edit, wan_i2v, zimage

SCHEMA = json.loads((Path(__file__).parent / "fixtures" / "comfy_nodes_0df64eb.json").read_text())["nodes"]


def check(graph: dict) -> None:
    for node_id, node in graph.items():
        schema = SCHEMA[node["class_type"]]
        inputs = node["inputs"]
        known = set(schema["required"]) | set(schema["optional"])
        for key, value in inputs.items():
            base = key.split(".")[0]  # dynamic inputs such as images.image_1
            assert base in known, f"{node_id}: {node['class_type']} has no input {key!r}"
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                src, slot = value
                assert src in graph, f"{node_id}.{key} links to missing node {src!r}"
                assert slot < SCHEMA[graph[src]["class_type"]]["outputs"], f"{node_id}.{key} uses bad output {slot}"
        missing = [r for r in schema["required"] if r not in inputs and not any(k.startswith(r + ".") for k in inputs)]
        assert not missing, f"{node_id}: {node['class_type']} misses {missing}"


@pytest.mark.parametrize(
    "graph",
    [
        zimage("a coat by a door", seed=1),
        zimage("a coat by a door", seed=1, init_image="in.png", denoise=0.5),
        zimage("a coat by a door", seed=1, m=ZIMAGE_CUDA),
        qwen_edit("same style", ["cover.png", "pose.png"], seed=2),
        wan_i2v("she turns her head", "key.png", seed=3),
        wan_i2v("she walks to the window", "key.png", seed=3, end_image="next.png"),
    ],
    ids=["zimage", "zimage_i2i", "zimage_cuda", "qwen_edit", "wan_i2v", "wan_flf"],
)
def test_graph_matches_pinned_comfyui(graph):
    check(graph)


def test_wan_length_must_be_4k_plus_1():
    with pytest.raises(ValueError):
        wan_i2v("x", "k.png", seed=0, length=48)


def test_wan_splits_steps_between_experts():
    g = wan_i2v("x", "k.png", seed=5)
    assert (g["s_hi"]["inputs"]["start_at_step"], g["s_hi"]["inputs"]["end_at_step"]) == (0, 2)
    assert g["s_lo"]["inputs"]["start_at_step"] == 2
    assert g["s_lo"]["inputs"]["latent_image"] == ["s_hi", 0]
    assert g["s_hi"]["inputs"]["noise_seed"] == 5
