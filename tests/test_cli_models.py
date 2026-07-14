from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.cli import download_model, list_models, main, resolve_session


def test_list_models_marks_installed(models_dir: Path, capsys: pytest.CaptureFixture[str]):
    code = list_models(models_dir)
    assert code == 0
    out = capsys.readouterr().out
    assert "u2netp" in out
    assert "installed" in out
    assert "missing" in out


def test_resolve_session_known():
    cls = resolve_session("u2netp")
    assert cls is not None
    assert cls.name() == "u2netp"


def test_resolve_session_unknown():
    assert resolve_session("not-a-model") is None


def test_download_model_unknown(tmp_path: Path):
    with pytest.raises(SystemExit) as ei:
        download_model("nope", tmp_path)
    assert ei.value.code == 1


def test_download_model_calls_session(tmp_path: Path):
    mock_cls = MagicMock()
    mock_cls.name.return_value = "u2netp"
    with (
        patch("app.cli.resolve_session", return_value=mock_cls),
        patch("app.cli.patch_pooch_retrieve", return_value=lambda: None),
    ):
        download_model("u2netp", tmp_path)
    mock_cls.download_models.assert_called_once()
    assert os.environ["U2NET_HOME"] == str(tmp_path.resolve())


def test_download_sets_absolute_u2net_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import os

    mock_cls = MagicMock()
    monkeypatch.chdir(tmp_path)
    target = Path("models")
    with (
        patch("app.cli.resolve_session", return_value=mock_cls),
        patch("app.cli.patch_pooch_retrieve", return_value=lambda: None),
        patch("app.cli.supported_model_ids", return_value=["u2netp"]),
    ):
        download_model("u2netp", "./models")
    assert Path(os.environ["U2NET_HOME"]).is_absolute()
    assert Path(os.environ["U2NET_HOME"]) == (tmp_path / "models").resolve()


def test_main_list(models_dir: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("U2NET_HOME", str(models_dir))
    assert main(["list"]) == 0


def test_main_pull_requires_target(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("U2NET_HOME", str(tmp_path))
    assert main(["pull"]) == 2


def test_main_pull_all(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setenv("U2NET_HOME", str(tmp_path))
    with patch("app.cli.download_model") as dl:
        assert main(["pull", "--all"]) == 0
        assert dl.call_count > 1
