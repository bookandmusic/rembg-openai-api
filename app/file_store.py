from __future__ import annotations

import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass
from threading import Lock


@dataclass
class _Entry:
    data: bytes
    content_type: str
    expires_at: float


class FileStore:
    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_items: int = 64,
        max_bytes: int = 256 * 1024 * 1024,
    ) -> None:
        self._ttl = ttl_seconds
        self._max_items = max_items
        self._max_bytes = max_bytes
        self._items: OrderedDict[str, _Entry] = OrderedDict()
        self._total_bytes = 0
        self._lock = Lock()

    def put(self, data: bytes, content_type: str = "image/png") -> str:
        self.purge()
        file_id = uuid.uuid4().hex
        with self._lock:
            self._items[file_id] = _Entry(
                data=data,
                content_type=content_type,
                expires_at=time.time() + self._ttl,
            )
            self._total_bytes += len(data)
            self._evict_locked()
        return file_id

    def get(self, file_id: str) -> tuple[bytes, str] | None:
        self.purge()
        with self._lock:
            entry = self._items.get(file_id)
            if entry is None:
                return None
            self._items.move_to_end(file_id)
            return entry.data, entry.content_type

    def purge(self) -> None:
        now = time.time()
        with self._lock:
            expired = [k for k, v in self._items.items() if v.expires_at <= now]
            for k in expired:
                self._drop_locked(k)

    def _drop_locked(self, key: str) -> None:
        entry = self._items.pop(key, None)
        if entry is not None:
            self._total_bytes -= len(entry.data)

    def _evict_locked(self) -> None:
        while self._items and (
            len(self._items) > self._max_items or self._total_bytes > self._max_bytes
        ):
            oldest, _ = next(iter(self._items.items()))
            self._drop_locked(oldest)
