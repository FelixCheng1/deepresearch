"""用于研究任务和报告笔记的文件型存储。"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any


class NoteStore:
    """支持创建、读取、更新的小型笔记存储。"""

    def __init__(self, workspace: str) -> None:
        self.workspace = Path(workspace)
        self.workspace.mkdir(parents=True, exist_ok=True)

    def run(self, payload: dict[str, Any]) -> str:
        """执行笔记动作，并返回给人看的结果文本。"""

        action = str(payload.get("action") or "").lower()
        if action == "create":
            return self.create(payload)
        if action == "read":
            return self.read(str(payload.get("note_id") or ""))
        if action == "update":
            return self.update(payload)
        return f"❌ 不支持的笔记动作：{action}"

    def create(self, payload: dict[str, Any]) -> str:
        note_id = str(payload.get("note_id") or uuid.uuid4().hex)
        self._write(note_id, payload)
        return f"✅ 笔记已创建。ID: {note_id}"

    def read(self, note_id: str) -> str:
        path = self._path(note_id)
        if not note_id or not path.exists():
            return f"❌ 未找到笔记。ID: {note_id}"
        return path.read_text(encoding="utf-8")

    def update(self, payload: dict[str, Any]) -> str:
        note_id = str(payload.get("note_id") or "")
        if not note_id:
            return "❌ 缺少 note_id"
        self._write(note_id, payload)
        return f"✅ 笔记已更新。ID: {note_id}"

    def path_for(self, note_id: str) -> str:
        return str(self._path(note_id))

    def _path(self, note_id: str) -> Path:
        return self.workspace / f"{note_id}.md"

    def _write(self, note_id: str, payload: dict[str, Any]) -> None:
        title = str(payload.get("title") or note_id)
        note_type = str(payload.get("note_type") or "note")
        tags = payload.get("tags") or []
        content = str(payload.get("content") or "")

        text = (
            f"# {title}\n\n"
            f"- note_id: {note_id}\n"
            f"- note_type: {note_type}\n"
            f"- tags: {', '.join(map(str, tags))}\n\n"
            f"{content.strip()}\n"
        )
        self._path(note_id).write_text(text, encoding="utf-8")
