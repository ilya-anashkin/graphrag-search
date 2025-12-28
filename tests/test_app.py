from unittest.mock import MagicMock

from fastapi.testclient import TestClient

from hybrid_graphrag_search import main


def test_health_endpoint(monkeypatch):
    os_client = MagicMock()
    os_client.ping.return_value = True
    neo_driver = MagicMock()
    neo_driver.verify_connectivity.return_value = True

    monkeypatch.setattr(main.deps, "get_opensearch_client", lambda settings: os_client)
    monkeypatch.setattr(main.deps, "get_graph_driver", lambda settings: neo_driver)

    app = main.create_app()
    client = TestClient(app)
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
