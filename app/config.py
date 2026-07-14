from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    u2net_home: str = "/models"
    default_model: str = "u2netp"
    max_sessions: int = 4
    max_image_bytes: int = 25 * 1024 * 1024
    max_dimension: int = 4096
    file_ttl_seconds: int = 3600
    max_file_store_items: int = 64
    max_file_store_bytes: int = 256 * 1024 * 1024
    max_concurrent: int = 2
    api_key: str | None = None
    public_base_url: str = "http://localhost:8000"

    @classmethod
    def from_env(cls, env: dict[str, str] | None = None) -> Settings:
        e = env if env is not None else os.environ
        api_key = e.get("API_KEY") or None
        return cls(
            u2net_home=e.get("U2NET_HOME", "/models"),
            default_model=e.get("DEFAULT_MODEL", "u2netp"),
            max_sessions=int(e.get("MAX_SESSIONS", "4")),
            max_image_bytes=int(e.get("MAX_IMAGE_BYTES", str(25 * 1024 * 1024))),
            max_dimension=int(e.get("MAX_DIMENSION", "4096")),
            file_ttl_seconds=int(e.get("FILE_TTL_SECONDS", "3600")),
            max_file_store_items=int(e.get("MAX_FILE_STORE_ITEMS", "64")),
            max_file_store_bytes=int(
                e.get("MAX_FILE_STORE_BYTES", str(256 * 1024 * 1024))
            ),
            max_concurrent=int(e.get("MAX_CONCURRENT", "2")),
            api_key=api_key,
            public_base_url=e.get("PUBLIC_BASE_URL", "http://localhost:8000").rstrip(
                "/"
            ),
        )


settings = Settings.from_env()
