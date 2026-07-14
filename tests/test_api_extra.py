from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import main
from app.config import Settings
from app.file_store import FileStore


@pytest.fixture
def client_no_auth(models_dir: Path, monkeypatch):
    monkeypatch.setattr(
        main,
        "settings",
        Settings.from_env({"U2NET_HOME": str(models_dir)}),
    )
    main.service._sessions.clear()
    main.file_store = FileStore(ttl_seconds=3600)
    return TestClient(main.app)


@pytest.fixture
def client_auth(models_dir: Path, monkeypatch):
    monkeypatch.setattr(
        main,
        "settings",
        Settings.from_env(
            {
                "U2NET_HOME": str(models_dir),
                "API_KEY": "sk-secret",
                "PUBLIC_BASE_URL": "http://test",
            }
        ),
    )
    main.service._sessions.clear()
    main.file_store = FileStore(ttl_seconds=3600)
    return TestClient(main.app)


def test_auth_required_missing(client_auth: TestClient, png_bytes: bytes):
    r = client_auth.post(
        "/v1/images/edits",
        files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
        data={"model": "u2netp"},
    )
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "invalid_api_key"


def test_auth_required_wrong(client_auth: TestClient, png_bytes: bytes):
    r = client_auth.post(
        "/v1/images/edits",
        headers={"Authorization": "Bearer wrong"},
        files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
        data={"model": "u2netp"},
    )
    assert r.status_code == 401


def test_auth_ok(client_auth: TestClient, png_bytes: bytes):
    with patch.object(main.service, "remove", return_value=b"out"):
        r = client_auth.post(
            "/v1/images/edits",
            headers={"Authorization": "Bearer sk-secret"},
            files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
            data={"model": "u2netp"},
        )
    assert r.status_code == 200


def test_models_require_auth(client_auth: TestClient):
    assert client_auth.get("/v1/models").status_code == 401
    r = client_auth.get(
        "/v1/models", headers={"Authorization": "Bearer sk-secret"}
    )
    assert r.status_code == 200


def test_health_no_auth(client_auth: TestClient):
    assert client_auth.get("/health").status_code == 200


def test_response_format_url(client_no_auth: TestClient, png_bytes: bytes):
    with patch.object(main.service, "remove", return_value=b"result-png"):
        r = client_no_auth.post(
            "/v1/images/edits",
            files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
            data={"model": "u2netp", "response_format": "url"},
        )
    assert r.status_code == 200
    url = r.json()["data"][0]["url"]
    assert url.startswith("http://localhost:8000/files/")
    file_id = url.rsplit("/", 1)[-1]
    fr = client_no_auth.get(f"/files/{file_id}")
    assert fr.status_code == 200
    assert fr.content == b"result-png"
    assert fr.headers["content-type"].startswith("image/png")


def test_file_not_found(client_no_auth: TestClient):
    r = client_no_auth.get("/files/does-not-exist")
    assert r.status_code == 404


def test_invalid_response_format(client_no_auth: TestClient, png_bytes: bytes):
    r = client_no_auth.post(
        "/v1/images/edits",
        files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
        data={"model": "u2netp", "response_format": "gif"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["param"] == "response_format"


def test_dimension_limit(models_dir: Path, monkeypatch):
    monkeypatch.setattr(
        main,
        "settings",
        Settings.from_env(
            {"U2NET_HOME": str(models_dir), "MAX_DIMENSION": "2"}
        ),
    )
    main.service._sessions.clear()
    client = TestClient(main.app)
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="red").save(buf, format="PNG")
    r = client.post(
        "/v1/images/edits",
        files={"image": ("t.png", io.BytesIO(buf.getvalue()), "image/png")},
        data={"model": "u2netp"},
    )
    assert r.status_code == 413


def test_invalid_image_bytes(client_no_auth: TestClient):
    r = client_no_auth.post(
        "/v1/images/edits",
        files={"image": ("t.png", io.BytesIO(b"not-an-image"), "image/png")},
        data={"model": "u2netp"},
    )
    assert r.status_code == 422
