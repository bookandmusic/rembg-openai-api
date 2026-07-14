from __future__ import annotations

import base64
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings
from app.file_store import FileStore
from app.image_input import resolve_image_input
from app.errors import RembgError
from tests.conftest import PNG_1X1


@pytest.fixture
def client(models_dir: Path, monkeypatch):
    monkeypatch.setattr(
        main,
        "settings",
        Settings.from_env({"U2NET_HOME": str(models_dir)}),
    )
    main.service._sessions.clear()
    main.file_store = FileStore(ttl_seconds=3600)
    return TestClient(main.app)


def test_resolve_raw_base64():
    b64 = base64.b64encode(PNG_1X1).decode()
    assert resolve_image_input(b64) == PNG_1X1


def test_resolve_data_url():
    b64 = base64.b64encode(PNG_1X1).decode()
    assert resolve_image_input(f"data:image/png;base64,{b64}") == PNG_1X1


def test_resolve_url():
    with patch("app.image_input.urlopen") as m:
        resp = MagicMock()
        resp.read.return_value = PNG_1X1
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = None
        m.return_value = resp
        assert resolve_image_input("https://example.com/a.png") == PNG_1X1


def test_resolve_invalid_base64():
    with pytest.raises(RembgError) as ei:
        resolve_image_input("!!!not-base64!!!")
    assert ei.value.param == "image"


def test_json_edits_base64(client: TestClient):
    b64 = base64.b64encode(PNG_1X1).decode()
    with patch.object(main.service, "remove", return_value=b"result-png") as rm:
        r = client.post(
            "/v1/images/edits",
            json={
                "model": "u2netp",
                "image": b64,
                "response_format": "b64_json",
            },
        )
    assert r.status_code == 200
    assert r.json()["data"][0]["b64_json"]
    rm.assert_called_once()
    assert rm.call_args.args[0] == PNG_1X1


def test_json_edits_default_response_format(client: TestClient):
    b64 = base64.b64encode(PNG_1X1).decode()
    with patch.object(main.service, "remove", return_value=b"out"):
        r = client.post(
            "/v1/images/edits",
            json={"model": "u2netp", "image": b64},
        )
    assert r.status_code == 200
    assert r.json()["data"][0]["b64_json"]


def test_json_edits_url_image(client: TestClient):
    with (
        patch("app.image_input.urlopen") as m,
        patch.object(main.service, "remove", return_value=b"out") as rm,
    ):
        resp = MagicMock()
        resp.read.return_value = PNG_1X1
        resp.__enter__.return_value = resp
        resp.__exit__.return_value = None
        m.return_value = resp
        r = client.post(
            "/v1/images/edits",
            json={"model": "u2netp", "image": "https://cdn.example/x.png"},
        )
    assert r.status_code == 200
    assert rm.call_args.args[0] == PNG_1X1


def test_json_generations_base64(client: TestClient):
    b64 = base64.b64encode(PNG_1X1).decode()
    with patch.object(main.service, "remove", return_value=b"out"):
        r = client.post(
            "/v1/images/generations",
            json={"model": "u2netp", "image": b64},
        )
    assert r.status_code == 200
    assert r.json()["data"][0]["b64_json"]


def test_json_missing_image(client: TestClient):
    r = client.post("/v1/images/edits", json={"model": "u2netp"})
    assert r.status_code == 400
    assert r.json()["error"]["param"] == "image"
