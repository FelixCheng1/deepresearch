import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from services.text_processing import strip_tool_calls


def test_strip_tool_call_marker():
    assert strip_tool_calls("前文 [TOOL_CALL:note:{\"action\":\"read\"}] 后文").strip() == "前文  后文"


def test_strip_fenced_json_tool_call_block():
    raw = """```json
[
  {
    "tool_call": {
      "type": "function",
      "function": {"name": "note", "arguments": "{}"}
    }
  }
]
```"""

    assert strip_tool_calls(raw).strip() == ""
