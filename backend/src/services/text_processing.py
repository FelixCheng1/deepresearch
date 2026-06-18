"""用于规范化模型生成文本的工具函数。"""

from __future__ import annotations

import re


def strip_tool_calls(text: str) -> str:
    """移除文本中的工具调用标记。"""

    if not text:
        return text

    text = re.sub(r"\[TOOL_CALL:[^\]]+\]", "", text)

    fenced_pattern = re.compile(r"```(?:json)?\s*(.*?)```", re.IGNORECASE | re.DOTALL)

    def replace_fenced(match: re.Match[str]) -> str:
        block = match.group(1)
        lowered = block.lower()
        if "tool_call" in lowered or '"name": "note"' in lowered or '"function"' in lowered:
            return ""
        return match.group(0)

    text = fenced_pattern.sub(replace_fenced, text)

    stripped = text.strip()
    lowered = stripped.lower()
    if lowered.startswith("[") and ("tool_call" in lowered or '"name": "note"' in lowered):
        return ""
    if lowered.startswith("{") and ("tool_call" in lowered or '"name": "note"' in lowered):
        return ""

    return text

