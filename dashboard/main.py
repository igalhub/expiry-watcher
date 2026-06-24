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

_SEVERITY_BADGE = {
    "healthy":  "badge-ok",
    "warning":  "badge-wa",
    "critical": "badge-cr",
    "expired":  "badge-cr",
}
_SEVERITY_COUNT_CLASS = {
    "healthy":  "cnt-ok",
    "warning":  "cnt-wa",
    "critical": "cnt-cr",
    "expired":  "cnt-cr",
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
        <div class="stale-banner">
          <i class="ti ti-alert-circle" aria-hidden="true"></i>
          Data is stale — checker may not be running
        </div>"""

    stale_border_cls = " stale-border" if stale else ""

    cards = ""
    for sev, cls in _SEVERITY_COUNT_CLASS.items():
        cards += f"""
        <div class="card">
          <div class="card-label">{sev}</div>
          <div class="card-count {cls}">{counts[sev]}</div>
        </div>"""

    rows = ""
    for item in items:
        sev = item.get("severity") or "unknown"
        badge_cls = _SEVERITY_BADGE.get(sev, "badge-un")
        icon = _SEVERITY_ICON.get(sev, "ti-help-circle")
        sev_cls = _SEVERITY_COUNT_CLASS.get(sev, "cnt-un")
        dr = item["days_remaining"]
        if dr is None:
            days_html = '<span class="text-muted">—</span>'
        elif dr < 0:
            days_html = f'<span class="text-muted" style="font-size:12px">−{abs(dr)}</span>'
        elif dr <= 7:
            days_html = f'<span class="{sev_cls}" style="font-weight:500">{dr}</span>'
        else:
            days_html = f'<span>{dr}</span>'

        checked_at = _format_time(item.get("checked_at", ""))
        error = item.get("error") or ""
        error_html = f' <span class="badge badge-cr" title="{error}" style="font-size:11px">⚠ error</span>' if error else ""

        rows += f"""
        <tr>
          <td style="font-family:monospace;font-size:12px;">{item["name"]}</td>
          <td><span class="type-badge">{item["type"]}</span></td>
          <td>
            <span class="badge {badge_cls}">
              <i class="ti {icon}" aria-hidden="true"></i>{sev}
            </span>{error_html}
          </td>
          <td style="font-variant-numeric:tabular-nums;">{days_html}</td>
          <td class="text-muted" style="font-size:12px;">{checked_at}</td>
        </tr>"""

    return f"""<!DOCTYPE html>
<html lang="en" class="dark">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Expiry Watcher</title>
  <link rel="stylesheet"
        href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@3.19.0/dist/tabler-icons.min.css">
  <style>
    /* ── Theme variables ─────────────────────────────────────── */
    html.dark {{
      --page-bg:     #1a1a1a;
      --card-bg:     #2a2a2a;
      --th-bg:       #222222;
      --hover-bg:    #222222;
      --border:      #3a3a3a;
      --text:        #e0e0e0;
      --muted:       #888888;
      --badge-cr-bg: #501313; --badge-cr-fg: #F7C1C1;
      --badge-wa-bg: #412402; --badge-wa-fg: #FAC775;
      --badge-ok-bg: #04342C; --badge-ok-fg: #9FE1CB;
      --badge-un-bg: #2C2C2A; --badge-un-fg: #B4B2A9;
      --cnt-ok: #9FE1CB; --cnt-wa: #FAC775; --cnt-cr: #F7C1C1; --cnt-un: #B4B2A9;
      --stale-bg: #501313; --stale-fg: #F7C1C1;
    }}
    html.light {{
      --page-bg:     #f8f9fa;
      --card-bg:     #ffffff;
      --th-bg:       #f8f9fa;
      --hover-bg:    #fafafa;
      --border:      #e5e5e5;
      --text:        #1a1a1a;
      --muted:       #888888;
      --badge-cr-bg: #FCEBEB; --badge-cr-fg: #A32D2D;
      --badge-wa-bg: #FAEEDA; --badge-wa-fg: #854F0B;
      --badge-ok-bg: #E1F5EE; --badge-ok-fg: #0F6E56;
      --badge-un-bg: #F1EFE8; --badge-un-fg: #5F5E5A;
      --cnt-ok: #5DCAA5; --cnt-wa: #EF9F27; --cnt-cr: #F09595; --cnt-un: #888780;
      --stale-bg: #FCEBEB; --stale-fg: #A32D2D;
    }}

    /* ── Base ────────────────────────────────────────────────── */
    *, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{
      font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--page-bg);
      color: var(--text);
      min-height: 100vh;
      transition: background-color 0.15s ease, color 0.15s ease;
    }}
    #root {{
      max-width: 1100px;
      margin: auto;
      padding: 24px;
    }}

    /* ── Stale banner ────────────────────────────────────────── */
    .stale-banner {{
      background: var(--stale-bg);
      color: var(--stale-fg);
      padding: 10px 16px;
      border-radius: 8px;
      font-size: 13px;
      margin-bottom: 16px;
      display: flex;
      align-items: center;
      gap: 8px;
    }}

    /* ── Header ──────────────────────────────────────────────── */
    .header {{
      display: flex;
      align-items: center;
      justify-content: space-between;
      margin-bottom: 20px;
    }}
    .header h1 {{
      font-size: 20px;
      font-weight: 500;
      display: flex;
      align-items: center;
      gap: 8px;
      color: var(--text);
    }}
    .header-right {{
      display: flex;
      align-items: center;
      gap: 16px;
    }}
    .meta {{ font-size: 12px; color: var(--muted); }}

    /* ── Summary cards ───────────────────────────────────────── */
    .cards {{
      display: grid;
      grid-template-columns: repeat(4, 1fr);
      gap: 10px;
      margin-bottom: 20px;
    }}
    .card {{
      background: var(--card-bg);
      border: 1px solid var(--border);
      border-radius: 8px;
      padding: 12px 16px;
      transition: background-color 0.15s ease;
    }}
    .card-label {{
      font-size: 11px;
      text-transform: uppercase;
      letter-spacing: 0.06em;
      margin-bottom: 6px;
      color: var(--muted);
    }}
    .card-count {{ font-size: 24px; font-weight: 500; }}

    /* ── Count colours ───────────────────────────────────────── */
    .cnt-ok {{ color: var(--cnt-ok); }}
    .cnt-wa {{ color: var(--cnt-wa); }}
    .cnt-cr {{ color: var(--cnt-cr); }}
    .cnt-un {{ color: var(--cnt-un); }}

    /* ── Table wrapper ───────────────────────────────────────── */
    .wrapper {{
      border: 1px solid var(--border);
      border-radius: 12px;
      overflow: hidden;
    }}
    .wrapper.stale-border {{ border: 3px solid var(--badge-cr-fg); }}

    /* ── Table ───────────────────────────────────────────────── */
    table {{ width: 100%; border-collapse: collapse; font-size: 13px; }}
    th {{
      font-size: 11px;
      font-weight: 500;
      color: var(--muted);
      text-transform: uppercase;
      letter-spacing: 0.06em;
      padding: 8px 12px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      background: var(--th-bg);
    }}
    td {{
      padding: 10px 12px;
      border-bottom: 1px solid var(--border);
      vertical-align: middle;
      color: var(--text);
    }}
    tr:last-child td {{ border-bottom: none; }}
    tr:hover td {{ background: var(--hover-bg); }}

    /* ── Asset type badge ────────────────────────────────────── */
    .type-badge {{
      font-size: 11px;
      color: var(--muted);
      background: var(--th-bg);
      padding: 2px 7px;
      border-radius: 4px;
      border: 1px solid var(--border);
    }}

    /* ── Severity badge classes ──────────────────────────────── */
    .badge {{
      display: inline-flex;
      align-items: center;
      gap: 4px;
      padding: 3px 8px;
      font-size: 11px;
      font-weight: 500;
      border-radius: 50rem;
    }}
    html.dark  .badge-cr {{ background: #501313 !important; color: #F7C1C1 !important; }}
    html.dark  .badge-wa {{ background: #412402 !important; color: #FAC775 !important; }}
    html.dark  .badge-ok {{ background: #04342C !important; color: #9FE1CB !important; }}
    html.dark  .badge-un {{ background: #2C2C2A !important; color: #B4B2A9 !important; }}
    html.light .badge-cr {{ background: #FCEBEB !important; color: #A32D2D !important; }}
    html.light .badge-wa {{ background: #FAEEDA !important; color: #854F0B !important; }}
    html.light .badge-ok {{ background: #E1F5EE !important; color: #0F6E56 !important; }}
    html.light .badge-un {{ background: #F1EFE8 !important; color: #5F5E5A !important; }}

    /* ── Text utilities ──────────────────────────────────────── */
    .text-muted {{ color: var(--muted) !important; }}

    /* ── Theme toggle button ─────────────────────────────────── */
    #theme-toggle {{
      background: transparent;
      border: 1px solid var(--text);
      color: var(--text);
      border-radius: 6px;
      padding: 6px 14px;
      cursor: pointer;
      font-size: 0.875rem;
      line-height: 1.5;
      display: inline-flex;
      align-items: center;
      gap: 6px;
      transition: background 0.15s;
    }}
    #theme-toggle:hover {{ background: var(--hover-bg); }}
  </style>
</head>
<body>
<div id="root">
  {stale_banner}
  <div class="header">
    <h1>
      <i class="ti ti-shield-check" aria-hidden="true"
         style="font-size:20px;color:var(--cnt-ok)"></i>
      Expiry Watcher
    </h1>
    <div class="header-right">
      <span class="meta">Last checked: <strong>{age}</strong></span>
      <button id="theme-toggle">
        <i id="toggle-icon" class="ti ti-moon"></i>
        <span id="toggle-label">Dark</span>
      </button>
    </div>
  </div>

  <div class="cards">{cards}</div>

  <div class="wrapper{stale_border_cls}">
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
</div>
<script>
  (function () {{
    var html  = document.documentElement;
    var icon  = document.getElementById('toggle-icon');
    var label = document.getElementById('toggle-label');
    var btn   = document.getElementById('theme-toggle');
    var saved = localStorage.getItem('ew-theme') || 'dark';

    function apply(theme) {{
      html.classList.remove('dark', 'light');
      html.classList.add(theme);
      icon.className = theme === 'dark' ? 'ti ti-moon' : 'ti ti-sun';
      label.textContent = theme === 'dark' ? 'Dark' : 'Light';
    }}

    apply(saved);

    btn.addEventListener('click', function () {{
      var next = html.classList.contains('dark') ? 'light' : 'dark';
      localStorage.setItem('ew-theme', next);
      apply(next);
    }});
  }})();
</script>
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
