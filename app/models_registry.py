from __future__ import annotations

from pathlib import Path

from rembg.sessions import sessions, sessions_names

from .schemas import ModelObject

# sam default files from rembg SamSession.download_models (sam_quant=False)
_SAM_FILES = (
    "sam_vit_b_01ec64.encoder.onnx",
    "sam_vit_b_01ec64.decoder.onnx",
)

REQUIRES_PROMPT: frozenset[str] = frozenset({"sam"})


def supported_model_ids() -> list[str]:
    """Built-in rembg models, excluding *_custom (need local path kwargs)."""
    return [n for n in sessions_names if not n.endswith("_custom")]


def model_files(model_id: str) -> list[str] | None:
    if model_id not in sessions:
        return None
    if model_id.endswith("_custom"):
        return None
    if model_id == "sam":
        return list(_SAM_FILES)
    # rembg download_models saves as {name()}.onnx for standard sessions
    return [f"{model_id}.onnx"]


def list_available_models(models_dir: str | Path) -> list[ModelObject]:
    root = Path(models_dir)
    if not root.is_dir():
        return []
    result: list[ModelObject] = []
    for model_id in supported_model_ids():
        if is_model_available(model_id, root):
            result.append(
                ModelObject(
                    id=model_id,
                    requires_prompt=model_id in REQUIRES_PROMPT,
                )
            )
    return result


def is_model_available(model_id: str, models_dir: str | Path) -> bool:
    files = model_files(model_id)
    if not files:
        return False
    root = Path(models_dir)
    return all((root / f).is_file() for f in files)
