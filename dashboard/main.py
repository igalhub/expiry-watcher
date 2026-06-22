import os
from datetime import datetime, timezone
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse

from checker.db import get_last_checked, read_results

app = FastAPI()

_DB_PATH = os.environ.get("EXPIRY_WATCHER_DB", "results.db")
_CHECK_INTERVAL_HOURS = int(os.environ.get("EXPIRY_WATCHER_CHECK_INTERVAL_HOURS", "6"))
_STALE_THRESHOLD_HOURS = _CHECK_INTERVAL_HOURS * 2

_SEVERITY_COLOR = {
    "healthy":  "#2d6a4f",
    "warning":  "#e9c46a",
    "critical": "#e76f51",
    "expired":  "#9b2226",
}


def _db_exists() -> bool:
    return Path(_DB_PATH).exists()


def _is_stale(last_checked: datetime | None) -> bool:
    if last_checked is None:
        return True
    age_hours = (datetime.now(timezone.utc) - last_checked).total_seconds() / 3600
    return age_hours > _STALE_THRESHOLD_HOURS


def _format_age(last_checked: datetime | None) -> str:
    if last_checked is None:
        return "never"
    minutes = int((datetime.now(timezone.utc) - last_checked).total_seconds() / 60)
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    hours = minutes // 60
    return f"{hours} hour{'s' if hours != 1 else ''} ago"


def _render_html(items: list[dict], age: str, stale: bool) -> str:
    stale_banner = (
        '<div class="stale-banner">Data is stale — checker may not be running</div>'
        if stale else ""
    )
    border_style = "border: 3px solid #e63946;" if stale else "border: 3px solid transparent;"

    rows = ""
    for item in items:
        sev = item.get("severity") or "unknown"
        color = _SEVERITY_COLOR.get(sev, "#adb5bd")
        dr = item["days_remaining"]
        rows += (
            f'<tr class="severity-{sev}">'
            f'<td>{item["name"]}</td>'
            f'<td>{item["type"]}</td>'
            f'<td style="color:{color};font-weight:bold">{sev}</td>'
            f'<td>{dr if dr is not None else "—"}</td>'
            f'<td>{item.get("checked_at", "")}</td>'
            f'<td>{item.get("error") or ""}</td>'
            f"</tr>"
        )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Expiry Watcher</title>
  <style>
    body{{font-family:sans-serif;padding:20px;max-width:1100px;margin:auto}}
    .stale-banner{{background:#e63946;color:#fff;padding:12px 16px;margin-bottom:16px;border-radius:4px;font-weight:bold}}
    .header{{padding:12px 16px;margin-bottom:16px;border-radius:4px;{border_style}}}
    table{{border-collapse:collapse;width:100%}}
    th,td{{padding:8px 12px;text-align:left;border-bottom:1px solid #ddd}}
    th{{background:#f8f9fa;font-weight:600}}
  </style>
</head>
<body>
  {stale_banner}
  <div class="header">
    <h1>Expiry Watcher</h1>
    <p>Last checked: <strong>{age}</strong></p>
  </div>
  <table>
    <thead><tr><th>Name</th><th>Type</th><th>Severity</th><th>Days Remaining</th><th>Checked At</th><th>Error</th></tr></thead>
    <tbody>{rows}</tbody>
  </table>
</body>
</html>"""


@app.get("/status")
def status():
    if not _db_exists():
        return {"items": [], "last_checked": None, "stale": True}
    items = read_results(_DB_PATH)
    last_checked = get_last_checked(_DB_PATH)
    return {
        "items": items,
        "last_checked": last_checked.isoformat() if last_checked else None,
        "stale": _is_stale(last_checked),
    }


@app.get("/", response_class=HTMLResponse)
def index():
    if not _db_exists():
        return HTMLResponse(content=_render_html([], "never", stale=True))
    items = read_results(_DB_PATH)
    last_checked = get_last_checked(_DB_PATH)
    return HTMLResponse(content=_render_html(
        items, _format_age(last_checked), _is_stale(last_checked)
    ))
