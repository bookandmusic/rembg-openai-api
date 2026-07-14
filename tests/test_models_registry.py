from pathlib import Path

from app.models_registry import (
    is_model_available,
    list_available_models,
    model_files,
    supported_model_ids,
)


def test_supported_excludes_custom():
    ids = supported_model_ids()
    assert "u2netp" in ids
    assert "sam" in ids
    assert all(not i.endswith("_custom") for i in ids)


def test_model_files_default():
    assert model_files("u2netp") == ["u2netp.onnx"]
    assert model_files("not-a-model") is None
    assert model_files("u2net_custom") is None


def test_empty_dir(tmp_path: Path):
    assert list_available_models(tmp_path) == []


def test_missing_dir(tmp_path: Path):
    assert list_available_models(tmp_path / "nope") == []


def test_lists_only_present_models(models_dir: Path):
    models = list_available_models(models_dir)
    ids = [m.id for m in models]
    assert ids == ["u2netp"]
    assert models[0].owned_by == "rembg"
    assert models[0].requires_prompt is False


def test_sam_requires_both_files(tmp_path: Path):
    enc, dec = model_files("sam")
    (tmp_path / enc).write_bytes(b"x")
    assert is_model_available("sam", tmp_path) is False
    (tmp_path / dec).write_bytes(b"x")
    assert is_model_available("sam", tmp_path) is True
    models = list_available_models(tmp_path)
    assert any(m.id == "sam" and m.requires_prompt for m in models)


def test_unknown_model():
    assert is_model_available("not-a-model", "/tmp") is False
