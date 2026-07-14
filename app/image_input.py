from __future__ import annotations

import base64
import binascii
from urllib.error import URLError
from urllib.request import Request, urlopen

from .config import settings
from .errors import RembgError

_URL_TIMEOUT = 30


def resolve_image_input(image: str) -> bytes:
    s = (image or "").strip()
    if not s:
        raise RembgError("image is empty", param="image")

    if s.startswith(("http://", "https://")):
        return _fetch_url(s)

    if s.startswith("data:"):
        if ";base64," not in s:
            raise RembgError(
                "image data URL must be base64",
                param="image",
            )
        s = s.split(";base64,", 1)[1]

    try:
        raw = base64.b64decode(s, validate=False)
    except (binascii.Error, ValueError) as e:
        raise RembgError(
            "image is not valid base64",
            param="image",
        ) from e

    if not raw:
        raise RembgError("image is empty", param="image")
    return raw


def _fetch_url(url: str) -> bytes:
    req = Request(url, headers={"User-Agent": "rembg-openai-api"})
    try:
        with urlopen(req, timeout=_URL_TIMEOUT) as resp:
            data = resp.read(settings.max_image_bytes + 1)
    except URLError as e:
        raise RembgError(
            f"failed to fetch image url: {e.reason}",
            param="image",
            status=400,
        ) from e
    except TimeoutError as e:
        raise RembgError(
            "image url fetch timed out",
            param="image",
            status=400,
        ) from e
    if len(data) > settings.max_image_bytes:
        raise RembgError(
            f"image exceeds {settings.max_image_bytes} bytes",
            status=413,
            param="image",
        )
    if not data:
        raise RembgError("image is empty", param="image")
    return data
