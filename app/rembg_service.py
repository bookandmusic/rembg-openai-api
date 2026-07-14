from __future__ import annotations

from collections import OrderedDict
from threading import Lock
from typing import Any

from rembg import new_session, remove


class RembgService:
    def __init__(self, max_sessions: int = 4) -> None:
        self._sessions: OrderedDict[str, Any] = OrderedDict()
        self._lock = Lock()
        self._max = max_sessions

    @property
    def loaded_count(self) -> int:
        return len(self._sessions)

    def get_session(self, model: str) -> Any:
        with self._lock:
            if model in self._sessions:
                self._sessions.move_to_end(model)
                return self._sessions[model]
            session = new_session(model)
            self._sessions[model] = session
            while len(self._sessions) > self._max:
                self._sessions.popitem(last=False)
            return session

    def remove(self, image: bytes, model: str, **extra: Any) -> bytes:
        session = self.get_session(model)
        result = remove(image, session=session, **extra)
        if isinstance(result, bytes):
            return result
        # rembg may return PIL Image depending on input/path; force bytes
        from io import BytesIO

        buf = BytesIO()
        result.save(buf, format="PNG")
        return buf.getvalue()
