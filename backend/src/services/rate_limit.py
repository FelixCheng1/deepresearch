"""Small in-process quota guard for a single-instance public demo."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from threading import Lock
from time import monotonic

from fastapi import HTTPException


class DemoUsageLimiter:
    def __init__(self) -> None:
        self._lock = Lock()
        self._daily: dict[tuple[str, str, str], int] = defaultdict(int)
        self._last_research: dict[str, float] = {}
        self._active_research: set[str] = set()

    @staticmethod
    def _day() -> str:
        return datetime.now(timezone.utc).date().isoformat()

    def start_research(self, user_id: str, *, daily_limit: int, cooldown_seconds: int) -> None:
        with self._lock:
            key = (self._day(), user_id, "research")
            now = monotonic()
            if user_id in self._active_research:
                raise HTTPException(status_code=429, detail="已有研究任务正在运行，请稍后再试")
            if self._daily[key] >= daily_limit:
                raise HTTPException(status_code=429, detail="今日研究次数已用完")
            remaining = cooldown_seconds - (now - self._last_research.get(user_id, -1e9))
            if remaining > 0:
                raise HTTPException(
                    status_code=429,
                    detail=f"请求过于频繁，请在 {int(remaining) + 1} 秒后重试",
                )
            self._daily[key] += 1
            self._last_research[user_id] = now
            self._active_research.add(user_id)

    def finish_research(self, user_id: str) -> None:
        with self._lock:
            self._active_research.discard(user_id)

    def consume_upload(self, user_id: str, *, daily_limit: int) -> None:
        with self._lock:
            key = (self._day(), user_id, "upload")
            if self._daily[key] >= daily_limit:
                raise HTTPException(status_code=429, detail="今日上传次数已用完")
            self._daily[key] += 1
