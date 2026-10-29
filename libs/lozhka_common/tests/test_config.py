from lozhka_common.config import Settings


def test_defaults_and_env_override(monkeypatch):
    assert Settings().env == "local"
    monkeypatch.setenv("LOZHKA_ENV", "staging")
    assert Settings().env == "staging"
