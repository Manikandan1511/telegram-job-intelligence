from fastapi.testclient import TestClient
from backend.app.main import app


def test_public_health_and_first_run_status():
    with TestClient(app) as client:
        assert client.get("/api/health").status_code==200
        result=client.get("/api/auth/status")
        assert result.status_code==200
        assert isinstance(result.json()["account_configured"],bool)


def test_private_api_requires_bearer_token():
    with TestClient(app) as client:
        response=client.get("/api/profile")
        assert response.status_code==401


def test_local_vite_preflight_is_allowed():
    with TestClient(app) as client:
        response=client.options(
            "/api/telegram/start",
            headers={"Origin":"http://127.0.0.1:5173","Access-Control-Request-Method":"POST","Access-Control-Request-Headers":"content-type"},
        )
        assert response.status_code==200
        assert response.headers["access-control-allow-origin"]=="http://127.0.0.1:5173"
