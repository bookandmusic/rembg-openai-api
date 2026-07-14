from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app import main
from app.config import Settings


@pytest.fixture
def client(models_dir: Path, png_bytes: bytes, monkeypatch):
    monkeypatch.setattr(main, "settings", Settings.from_env({"U2NET_HOME": str(models_dir)}))
    # reset service sessions
    main.service._sessions.clear()
    return TestClient(main.app)


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["available_models_count"] == 1


def test_list_models(client: TestClient):
    r = client.get("/v1/models")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["id"] == "u2netp"


def test_edits_success(client: TestClient, png_bytes: bytes):
    with patch.object(main.service, "remove", return_value=b"result-png") as rm:
        r = client.post(
            "/v1/images/edits",
            files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
            data={"model": "u2netp", "prompt": ""},
        )
    assert r.status_code == 200
    body = r.json()
    assert "created" in body
    assert body["data"][0]["b64_json"]
    rm.assert_called_once()


def test_generations_alias(client: TestClient, png_bytes: bytes):
    with patch.object(main.service, "remove", return_value=b"result-png"):
        r = client.post(
            "/v1/images/generations",
            files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
            data={"model": "u2netp"},
        )
    assert r.status_code == 200
    assert r.json()["data"][0]["b64_json"]


def test_model_not_found(client: TestClient, png_bytes: bytes):
    r = client.post(
        "/v1/images/edits",
        files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
        data={"model": "u2net"},
    )
    assert r.status_code == 404
    err = r.json()["error"]
    assert err["code"] == "model_not_found"
    assert err["param"] == "model"


def test_empty_image(client: TestClient):
    r = client.post(
        "/v1/images/edits",
        files={"image": ("t.png", io.BytesIO(b""), "image/png")},
        data={"model": "u2netp"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["param"] == "image"


def test_n_must_be_one(client: TestClient, png_bytes: bytes):
    r = client.post(
        "/v1/images/edits",
        files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
        data={"model": "u2netp", "n": "2"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["param"] == "n"


def test_extra_invalid_json(client: TestClient, png_bytes: bytes):
    r = client.post(
        "/v1/images/edits",
        files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
        data={"model": "u2netp", "extra": "not-json"},
    )
    assert r.status_code == 400
    assert r.json()["error"]["param"] == "extra"


def test_extra_whitelist(client: TestClient, png_bytes: bytes):
    with patch.object(main.service, "remove", return_value=b"out") as rm:
        r = client.post(
            "/v1/images/edits",
            files={"image": ("t.png", io.BytesIO(png_bytes), "image/png")},
            data={
                "model": "u2netp",
                "extra": '{"only_mask": true, "evil": 1}',
            },
        )
    assert r.status_code == 200
    kwargs = rm.call_args.kwargs
    assert kwargs.get("only_mask") is True
    assert "evil" not in kwargs


def test_image_too_large(client: TestClient, monkeypatch, models_dir: Path):
    monkeypatch.setattr(
        main,
        "settings",
        Settings.from_env({"U2NET_HOME": str(models_dir), "MAX_IMAGE_BYTES": "10"}),
    )
    r = client.post(
        "/v1/images/edits",
        files={"image": ("t.png", io.BytesIO(b"0123456789abcdef"), "image/png")},
        data={"model": "u2netp"},
    )
    assert r.status_code == 413
