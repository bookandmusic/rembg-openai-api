from __future__ import annotations

import base64
from pathlib import Path

import pytest

# 1x1 red PNG
PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


@pytest.fixture
def png_bytes() -> bytes:
    return PNG_1X1


@pytest.fixture
def models_dir(tmp_path: Path) -> Path:
    d = tmp_path / "models"
    d.mkdir()
    (d / "u2netp.onnx").write_bytes(b"fake-onnx")
    return d
