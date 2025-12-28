from hybrid_graphrag_search.settings import Settings


def test_settings_env_override(monkeypatch):
    monkeypatch.setenv("APP_NAME", "test-app")
    monkeypatch.setenv("OPENSEARCH_PORT", "1234")
    settings = Settings()
    assert settings.app_name == "test-app"
    assert settings.opensearch_port == 1234
