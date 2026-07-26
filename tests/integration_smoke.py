"""Local HTTP smoke test with no external notification calls."""

from __future__ import annotations

import os
import shutil
import sys
from datetime import datetime
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
DATA_DIR = ROOT / ".runtime-test"
if DATA_DIR.exists():
    shutil.rmtree(DATA_DIR)

os.environ["DATA_DIR"] = str(DATA_DIR)
os.environ["APP_SECRET"] = "integration-test-secret"
os.environ["ADMIN_PASSWORD"] = "integration-test-password"
os.environ["PUBLIC_BASE_URL"] = "http://testserver"
os.environ["CHECK_INTERVAL_SECONDS"] = "3600"
os.environ["PUSHPLUS_TOKEN"] = ""
os.environ["QQ_SMTP_USER"] = ""
os.environ["QQ_SMTP_AUTH_CODE"] = ""
os.environ["QQ_EMAIL_TO"] = ""

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app, database, settings  # noqa: E402
from app.security import create_token  # noqa: E402


def run() -> None:
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json()["status"] == "ok"

        response = client.get("/", follow_redirects=False)
        assert response.status_code == 303
        assert response.headers["location"] == "/login"

        response = client.post(
            "/login",
            data={"password": "wrong"},
            follow_redirects=False,
        )
        assert response.status_code == 401

        response = client.post(
            "/login",
            data={"password": "integration-test-password"},
            follow_redirects=False,
        )
        assert response.status_code == 303
        response = client.get("/")
        assert response.status_code == 200
        assert "2027-01-22" in response.text

        state = database.get_state()
        token = create_token(
            settings.app_secret,
            "confirm",
            expires_in_seconds=60,
            extra={"cycle": state["cycle_started_at"]},
        )
        response = client.get(f"/confirm/{token}")
        assert response.status_code == 200

        today = datetime.now(settings.timezone).date().isoformat()
        response = client.post(
            f"/confirm/{token}",
            data={"sent_date": today},
        )
        assert response.status_code == 200
        assert "本轮保号已完成" in response.text

        response = client.get(f"/confirm/{token}")
        assert response.status_code == 400

    shutil.rmtree(DATA_DIR)
    print("integration smoke test: OK")


if __name__ == "__main__":
    run()
