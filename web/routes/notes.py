from __future__ import annotations

from flask import Blueprint, jsonify, request

from services.notes import get_note, load_notes, set_note


notes_bp = Blueprint("notes", __name__, url_prefix="/api/notes")


@notes_bp.get("")
def all_notes():
    return jsonify(load_notes())


@notes_bp.get("/<player_key>")
def player_note(player_key: str):
    return jsonify(
        {
            "player_key": player_key,
            "note": get_note(player_key),
        }
    )


@notes_bp.post("/<player_key>")
def save_player_note(player_key: str):
    payload = request.get_json(silent=True) or {}
    result = set_note(player_key, payload.get("note", ""))
    return jsonify(
        {
            "success": True,
            **result,
        }
    )