from __future__ import annotations

import os
from collections.abc import Callable
from typing import Any
from urllib.parse import urlparse


def github_proxy_prefix(env: dict[str, str] | None = None) -> str | None:
    e = env if env is not None else os.environ
    raw = (e.get("GITHUB_PROXY") or e.get("GITHUB_RELEASES_PROXY") or "").strip()
    if not raw:
        return None
    return raw.rstrip("/") + "/"


def rewrite_download_url(url: str, env: dict[str, str] | None = None) -> str:
    """Rewrite GitHub URLs through GITHUB_PROXY if set.

    Example:
      GITHUB_PROXY=https://gh-proxy.com/
      https://github.com/org/repo/...
        -> https://gh-proxy.com/https://github.com/org/repo/...
    """
    prefix = github_proxy_prefix(env)
    if not prefix or not url:
        return url
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        return url
    host = (parsed.hostname or "").lower()
    if host not in ("github.com", "raw.githubusercontent.com", "objects.githubusercontent.com"):
        return url
    # already proxied
    if url.startswith(prefix):
        return url
    return f"{prefix}{url}"


def patch_pooch_retrieve() -> Callable[[], None]:
    """Monkey-patch pooch.retrieve to rewrite GitHub URLs. Returns unpatch."""
    import pooch

    original: Callable[..., Any] = pooch.retrieve

    def wrapped(url: str, *args: Any, **kwargs: Any) -> Any:
        return original(rewrite_download_url(url), *args, **kwargs)

    pooch.retrieve = wrapped  # type: ignore[assignment]

    def unpatch() -> None:
        pooch.retrieve = original  # type: ignore[assignment]

    return unpatch
