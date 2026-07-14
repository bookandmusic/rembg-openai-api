from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ImageItem(BaseModel):
    b64_json: str | None = None
    url: str | None = None


class ImagesResponse(BaseModel):
    created: int
    data: list[ImageItem]


class ImagesJsonRequest(BaseModel):
    image: str | None = None
    model: str | None = None
    prompt: str = ""
    n: int = 1
    response_format: str = "b64_json"
    extra: dict[str, Any] | None = None


class ModelObject(BaseModel):
    id: str
    object: str = "model"
    owned_by: str = "rembg"
    requires_prompt: bool = False


class ModelsListResponse(BaseModel):
    object: str = "list"
    data: list[ModelObject] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    models_dir: str
    models_dir_writable: bool
    available_models_count: int
    loaded_sessions: int
