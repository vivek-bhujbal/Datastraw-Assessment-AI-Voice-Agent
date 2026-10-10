from fastapi.testclient import TestClient

from app.config import Settings
import app.main as main


def test_saved_key_is_read_without_restarting(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=\n", encoding="utf-8")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setattr(main, "get_settings", lambda: Settings(_env_file=env))

    with TestClient(main.app) as client:
        assert client.get("/health").json()["provider_configured"] is False
        env.write_text("GEMINI_API_KEY=test-only-not-a-real-key\n", encoding="utf-8")
        assert client.get("/health").json()["provider_configured"] is True
        env.write_text("GEMINI_API_KEY=your-gemini-api-key\n", encoding="utf-8")
        assert client.get("/health").json()["provider_configured"] is False


def test_env_file_with_windows_bom(monkeypatch, tmp_path):
    env = tmp_path / ".env"
    env.write_text("GEMINI_API_KEY=test-only-not-a-real-key\n", encoding="utf-8-sig")
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    assert Settings(_env_file=env).ready is True

