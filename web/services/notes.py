from __future__ import annotations

import json
from pathlib import Path
from threading import RLock
from typing import Any


NOTES_FILE = Path(__file__).resolve().parents[1] / "data" / "notes.json"

_lock = RLock()


def _ensure_file() -> None:
    NOTES_FILE.parent.mkdir(parents=True, exist_ok=True)
    if not NOTES_FILE.exists():
        NOTES_FILE.write_text("{}", encoding="utf-8")


def load_notes() -> dict[str, str]:
    _ensure_file()
    with _lock:
        try:
            data = json.loads(NOTES_FILE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {}
    if not isinstance(data, dict):
        return {}
    return {
        str(key): str(value or "")
        for key, value in data.items()
    }


def save_notes(notes: dict[str, str]) -> None:
    _ensure_file()
    clean = {
        str(key): str(value or "")
        for key, value in notes.items()
        if str(value or "").strip()
    }
    with _lock:
        NOTES_FILE.write_text(
            json.dumps(clean, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )


def get_note(player_key: int | str | None) -> str:
    if player_key is None:
        return ""
    return load_notes().get(str(player_key), "")


def set_note(player_key: int | str, note: str) -> dict[str, Any]:
    key = str(player_key)
    notes = load_notes()
    text = str(note or "").strip()
    if text:
        notes[key] = text
    else:
        notes.pop(key, None)
    save_notes(notes)
    return {"player_key": key, "note": text}
