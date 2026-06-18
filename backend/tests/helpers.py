from pathlib import Path
from uuid import uuid4


def make_notes_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / "notes" / f"test-{uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path
