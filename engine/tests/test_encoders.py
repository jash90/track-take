import pytest

from tracktake.render import encoders


@pytest.fixture(autouse=True)
def clear_cache():
    encoders._available.cache_clear()
    encoders._encodes.cache_clear()
    yield
    encoders._available.cache_clear()
    encoders._encodes.cache_clear()


def test_forced_family(monkeypatch):
    monkeypatch.setenv("TRACKTAKE_ENCODER", "nvenc")
    assert encoders.video_args("h264", "14M")[:4] == ["-c:v", "h264_nvenc", "-b:v", "14M"]
    assert "hvc1" in encoders.video_args("hevc", "1M")


def test_cpu_fallback_on_linux_without_gpu(monkeypatch):
    monkeypatch.delenv("TRACKTAKE_ENCODER", raising=False)
    monkeypatch.setattr(encoders.platform, "system", lambda: "Linux")
    monkeypatch.setattr(encoders, "_available", lambda: frozenset({"libx264", "libx265", "h264_nvenc"}))
    monkeypatch.setattr(encoders.shutil, "which", lambda name: None)  # no nvidia-smi
    assert encoders.family() == "cpu"
    monkeypatch.setattr(encoders.shutil, "which", lambda name: "/usr/bin/nvidia-smi")
    monkeypatch.setattr(encoders, "_encodes", lambda enc: True)
    assert encoders.family() == "nvenc"
    monkeypatch.setattr(encoders, "_encodes", lambda enc: False)  # listed but the container lacks libnvidia-encode
    assert encoders.family() == "cpu"


def test_bad_override(monkeypatch):
    monkeypatch.setenv("TRACKTAKE_ENCODER", "quantum")
    with pytest.raises(ValueError):
        encoders.family()
