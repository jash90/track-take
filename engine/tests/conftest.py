import pytest


@pytest.fixture(autouse=True)
def _isolated_net_history(tmp_path):
    """Offer ranking reads data/net_survey.jsonl; tests use an empty history unless they write one.
    Its own MonkeyPatch, so the shared `monkeypatch` fixture keeps its usual setup/teardown order."""
    from tracktake import nethistory

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(nethistory, "HISTORY", tmp_path / "net_history.jsonl")
        mp.setattr(nethistory, "_CACHE", None)
        yield
