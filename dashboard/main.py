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

_SEVERITY_BG = {
    "healthy":  "#E1F5EE",
    "warning":  "#FAEEDA",
    "critical": "#FAECE7",
    "expired":  "#FCEBEB",
}
_SEVERITY_FG = {
    "healthy":  "#0F6E56",
    "warning":  "#854F0B",
    "critical": "#993C1D",
    "expired":  "#A32D2D",
}
_SEVERITY_ICON = {
    "healthy":  "ti-circle-check",
    "warning":  "ti-alert-triangle",
    "critical": "ti-alert-triangle",
    "expired":  "ti-alert-circle",
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


def _format_time(iso: str) -> str:
    try:
        dt = datetime.fromisoformat(iso)
        return dt.strftime("%H:%M UTC")
    except Exception:
        return iso


def _severity_counts(items: list[dict]) -> dict:
    counts = {"healthy": 0, "warning": 0, "critical": 0, "expired": 0}
    for item in items:
        sev = item.get("severity") or ""
        if sev in counts:
            counts[sev] += 1
    return counts


def _render_html(items: list[dict], age: str, stale: bool) -> str:
    counts = _severity_counts(items)

    stale_banner = ""
    if stale:
        stale_banner = """
        <div style="background:#FCEBEB;color:#A32D2D;padding:10px 16px;
                    border-radius:8px;font-size:13px;margin-bottom:16px;
                    display:flex;align-items:center;gap:8px;">
          <i class="ti ti-alert-circle" aria-hidden="true"></i>
          Data is stale — checker may not be running
        </div>"""

    card_colors = {
        "healthy":  ("#E1F5EE", "#0F6E56"),
        "warning":  ("#FAEEDA", "#854F0B"),
        "critical": ("#FAECE7", "#993C1D"),
        "expired":  ("#FCEBEB", "#A32D2D"),
    }
    cards = ""
    for sev, (bg, fg) in card_colors.items():
        cards += f"""
        <div style="background:{bg};border-radius:8px;padding:12px 16px;">
          <div style="font-size:11px;color:{fg};text-transform:uppercase;
                      letter-spacing:0.06em;margin-bottom:6px;">{sev}</div>
          <div style="font-size:24px;font-weight:500;color:{fg};">{counts[sev]}</div>
        </div>"""

    rows = ""
    for item in items:
        sev = item.get("severity") or "unknown"
        bg = _SEVERITY_BG.get(sev, "#f1f1f1")
        fg = _SEVERITY_FG.get(sev, "#666")
        icon = _SEVERITY_ICON.get(sev, "ti-help-circle")
        dr = item["days_remaining"]
        if dr is None:
            days_html = '<span style="color:#888">—</span>'
        elif dr < 0:
            days_html = f'<span style="color:#888;font-size:12px">−{abs(dr)}</span>'
        elif dr <= 7:
            days_html = f'<span style="color:{fg};font-weight:500">{dr}</span>'
        else:
            days_html = f'<span>{dr}</span>'

        checked_at = _format_time(item.get("checked_at", ""))
        error = item.get("error") or ""
        error_html = f'<span style="color:#A32D2D;font-size:11px" title="{error}">⚠ error</span>' if error else ""

        rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:12px;">{item["name"]}</td>
          <td>
            <span style="font-size:11px;color:#666;background:#f1f1f1;
                         padding:2px 7px;border-radius:4px;
                         border:0.5px solid #ddd;">{item["type"]}</span>
          </td>
          <td>
            <span style="display:inline-flex;align-items:center;gap:4px;
                         padding:3px 8px;border-radius:20px;font-size:11px;
                         font-weight:500;background:{bg};color:{fg};">
              <i class="ti {icon}" aria-hidden="true"></i>{sev}
            </span>
            {error_html}
          </td>
          <td style="font-variant-numeric:tabular-nums;">{days_html}</td>
          <td style="color:#888;font-size:12px;">{checked_at}</td>
        </tr>"""

    border_style = "border:3px solid #FCEBEB;" if stale else "border:3px solid transparent;"

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Expiry Watcher</title>
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
          padding:24px;max-width:1100px;margin:auto;color:#1a1a1a;background:#fff}}
    .header{{display:flex;align-items:center;justify-content:space-between;margin-bottom:20px}}
    .header h1{{font-size:20px;font-weight:500;display:flex;align-items:center;gap:8px}}
    .header .meta{{font-size:12px;color:#888}}
    .cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px;margin-bottom:20px}}
    table{{width:100%;border-collapse:collapse;font-size:13px}}
    th{{font-size:11px;font-weight:500;color:#888;text-transform:uppercase;
        letter-spacing:0.06em;padding:8px 12px;
        border-bottom:0.5px solid #e5e5e5;text-align:left}}
    td{{padding:10px 12px;border-bottom:0.5px solid #f0f0f0;vertical-align:middle}}
    tr:last-child td{{border-bottom:none}}
    tr:hover td{{background:#fafafa}}
    .wrapper{{border:0.5px solid #e5e5e5;border-radius:12px;overflow:hidden;{border_style}}}
  </style>
</head>
<body>
  {stale_banner}
  <div class="header">
    <h1>
      <i class="ti ti-shield-check" aria-hidden="true"
         style="font-size:20px;color:#0F6E56"></i>
      Expiry Watcher
    </h1>
    <span class="meta">Last checked: <strong>{age}</strong></span>
  </div>

  <div class="cards">{cards}</div>

  <div class="wrapper">
    <table>
      <thead>
        <tr>
          <th>Name</th>
          <th>Type</th>
          <th>Severity</th>
          <th>Days remaining</th>
          <th>Last checked</th>
        </tr>
      </thead>
      <tbody>{rows}</tbody>
    </table>
  </div>
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
