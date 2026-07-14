from __future__ import annotations

import asyncio
import base64
import io
import json
import os
import time
from typing import Any

from fastapi import Depends, FastAPI, Header, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import Response
from PIL import Image
from pydantic import ValidationError
from starlette.datastructures import UploadFile as StarletteUploadFile

from .config import settings
from .errors import RembgError, rembg_error_handler, validation_error_handler
from .file_store import FileStore
from .image_input import resolve_image_input
from .models_registry import is_model_available, list_available_models
from .rembg_service import RembgService
from .schemas import (
    HealthResponse,
    ImageItem,
    ImagesJsonRequest,
    ImagesResponse,
    ModelsListResponse,
)

ALLOWED_EXTRA = frozenset(
    {
        "alpha_matting",
        "alpha_matting_foreground_threshold",
        "alpha_matting_background_threshold",
        "alpha_matting_erode_size",
        "only_mask",
        "post_process_mask",
        "bgcolor",
        "input_points",
        "input_labels",
    }
)

app = FastAPI(title="rembg-openai-api")
app.add_exception_handler(RembgError, rembg_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
service = RembgService(max_sessions=settings.max_sessions)
file_store = FileStore(
    ttl_seconds=settings.file_ttl_seconds,
    max_items=settings.max_file_store_items,
    max_bytes=settings.max_file_store_bytes,
)
_infer_sem = asyncio.Semaphore(settings.max_concurrent)


def require_api_key(authorization: str | None = Header(default=None)) -> None:
    expected = settings.api_key
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise RembgError(
            "Missing bearer token",
            type="invalid_request_error",
            code="invalid_api_key",
            status=401,
        )
    token = authorization.removeprefix("Bearer ").strip()
    if token != expected:
        raise RembgError(
            "Incorrect API key provided",
            type="invalid_request_error",
            code="invalid_api_key",
            status=401,
        )


def _parse_extra(extra: str | dict[str, Any] | None) -> dict[str, Any]:
    if not extra:
        return {}
    if isinstance(extra, dict):
        parsed = extra
    else:
        try:
            parsed = json.loads(extra)
        except json.JSONDecodeError as e:
            raise RembgError("extra is not valid JSON", param="extra") from e
        if not isinstance(parsed, dict):
            raise RembgError("extra must be a JSON object", param="extra")
    return {k: v for k, v in parsed.items() if k in ALLOWED_EXTRA}


def _check_dimensions(content: bytes) -> None:
    try:
        with Image.open(io.BytesIO(content)) as img:
            w, h = img.size
    except Exception as e:
        raise RembgError(
            "image is not a valid image file",
            status=422,
            param="image",
        ) from e
    if w > settings.max_dimension or h > settings.max_dimension:
        raise RembgError(
            f"image dimension {w}x{h} exceeds max {settings.max_dimension}",
            status=413,
            param="image",
        )


async def _process_bytes(
    content: bytes,
    model: str,
    n: int,
    extra: str | dict[str, Any] | None,
    response_format: str,
) -> ImagesResponse:
    if n != 1:
        raise RembgError("n must be 1", param="n")
    if response_format not in ("b64_json", "url"):
        raise RembgError(
            "response_format must be b64_json or url",
            param="response_format",
        )
    if not is_model_available(model, settings.u2net_home):
        raise RembgError(
            f"model '{model}' not found in mounted models directory",
            type="invalid_request_error",
            code="model_not_found",
            status=404,
            param="model",
        )

    if len(content) == 0:
        raise RembgError("image is empty", param="image")
    if len(content) > settings.max_image_bytes:
        raise RembgError(
            f"image exceeds {settings.max_image_bytes} bytes",
            status=413,
            param="image",
        )
    _check_dimensions(content)

    kwargs = _parse_extra(extra)
    try:
        async with _infer_sem:
            result_bytes = await asyncio.to_thread(
                service.remove, content, model, **kwargs
            )
    except Exception as e:
        raise RembgError(
            str(e) or "model inference failed",
            type="api_error",
            code="api_error",
            status=500,
        ) from e

    if response_format == "url":
        file_id = file_store.put(result_bytes)
        url = f"{settings.public_base_url}/files/{file_id}"
        return ImagesResponse(
            created=int(time.time()),
            data=[ImageItem(url=url)],
        )

    return ImagesResponse(
        created=int(time.time()),
        data=[ImageItem(b64_json=base64.b64encode(result_bytes).decode())],
    )


async def _images_endpoint(request: Request) -> ImagesResponse:
    ctype = (request.headers.get("content-type") or "").lower()
    if "application/json" in ctype:
        try:
            body = await request.json()
        except Exception as e:
            raise RembgError("invalid JSON body", param=None) from e
        if not isinstance(body, dict):
            raise RembgError("body must be a JSON object")
        try:
            req = ImagesJsonRequest.model_validate(body)
        except ValidationError as e:
            raise RembgError(str(e.errors()[0]["msg"]), param="body") from e
        if not req.image:
            raise RembgError("image is required", param="image")
        content = resolve_image_input(req.image)
        return await _process_bytes(
            content,
            req.model or settings.default_model,
            req.n,
            req.extra,
            req.response_format,
        )

    form = await request.form()
    upload = form.get("image")
    if not isinstance(upload, (UploadFile, StarletteUploadFile)):
        raise RembgError("image is required", param="image")
    content = await upload.read()
    model = form.get("model") or settings.default_model
    n_raw = form.get("n", "1")
    try:
        n = int(n_raw)  # type: ignore[arg-type]
    except (TypeError, ValueError) as e:
        raise RembgError("n must be an integer", param="n") from e
    response_format = str(form.get("response_format") or "b64_json")
    extra = form.get("extra")
    extra_s = None if extra is None else str(extra)
    return await _process_bytes(
        content,
        str(model),
        n,
        extra_s,
        response_format,
    )


@app.post("/v1/images/edits", response_model=ImagesResponse)
async def edits(
    request: Request,
    _: None = Depends(require_api_key),
) -> ImagesResponse:
    return await _images_endpoint(request)


@app.post("/v1/images/generations", response_model=ImagesResponse)
async def generations(
    request: Request,
    _: None = Depends(require_api_key),
) -> ImagesResponse:
    return await _images_endpoint(request)


@app.get("/v1/models", response_model=ModelsListResponse)
def models(_: None = Depends(require_api_key)) -> ModelsListResponse:
    return ModelsListResponse(data=list_available_models(settings.u2net_home))


@app.get("/files/{file_id}")
def get_file(file_id: str) -> Response:
    item = file_store.get(file_id)
    if item is None:
        raise RembgError("file not found or expired", status=404, code="not_found")
    data, content_type = item
    return Response(content=data, media_type=content_type)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    path = settings.u2net_home
    return HealthResponse(
        status="ok",
        models_dir=path,
        models_dir_writable=os.path.isdir(path) and os.access(path, os.W_OK),
        available_models_count=len(list_available_models(path)),
        loaded_sessions=service.loaded_count,
    )
