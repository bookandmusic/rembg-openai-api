from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings
from app.file_store import FileStore
from tests.conftest import PNG_1X1


@pytest.fixture
def client(models_dir: Path, monkeypatch):
    monkeypatch.setattr(
        main,
        "settings",
        Settings.from_env(
            {"U2NET_HOME": str(models_dir), "MAX_CONCURRENT": "1"}
        ),
    )
    main.service._sessions.clear()
    main.file_store = FileStore(ttl_seconds=3600)
    main._infer_sem = __import__("asyncio").Semaphore(1)
    return TestClient(main.app)


def test_remove_runs_in_thread(client: TestClient):
    b64 = base64.b64encode(PNG_1X1).decode()
    with (
        patch.object(main.service, "remove", return_value=b"out") as rm,
        patch("app.main.asyncio.to_thread", side_effect=lambda f, *a, **k: f(*a, **k)) as tt,
    ):
        r = client.post(
            "/v1/images/edits",
            json={"model": "u2netp", "image": b64},
        )
    assert r.status_code == 200
    tt.assert_called()
    rm.assert_called_once()
