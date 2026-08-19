from __future__ import annotations

from io import BytesIO
from datetime import datetime

from flask import Blueprint, request, send_file

from services.excel_export import build_dashboard_export


export_bp = Blueprint("export", __name__, url_prefix="/api/export")


def _int_arg(name: str, default: int) -> int:
    try:
        return int(request.args.get(name, default))
    except (TypeError, ValueError):
        return default


@export_bp.get("/dashboard.xlsx")
def dashboard_excel():
    season = _int_arg("season", 0)
    days = _int_arg("days", 38)

    workbook = build_dashboard_export(
        season=season or None,
        days=days,
        role=request.args.get("role") or None,
        team=request.args.get("team") or None,
        search=request.args.get("search") or None,
        sort=request.args.get("sort") or "FVM",
    )

    output = BytesIO()
    workbook.save(output)
    output.seek(0)

    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    name = f"Fantastat_dashboard_{stamp}.xlsx"

    return send_file(
        output,
        as_attachment=True,
        download_name=name,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
