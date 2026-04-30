"""
Local failure-analysis dashboard (SQLite `analyses` table + JSON under storage/analyses/).

Run the analyzer first so rows exist:
  python analysis/analyzer.py <trace_id>

Then:
  python storage/analysis_viewer.py
  open http://127.0.0.1:8766/

  python storage/analysis_viewer.py --table
"""
from __future__ import annotations

import argparse
import html
import http.server
import json
import os
import sqlite3
import sys
import urllib.parse
from typing import Any, Optional

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)
from storage.serve_local import run_local_http

_DB_PATH = os.path.join(_ROOT, "storage", "index.db")
_ANALYSES_DIR = os.path.join(_ROOT, "storage", "analyses")

# Shared look with trace_viewer (dark panel UI)
_CSS = """
:root {
  --bg: #0c0f14;
  --panel: #141922;
  --border: #252d3a;
  --text: #e6edf3;
  --muted: #8b9cb3;
  --accent: #a371f7;
  --accent2: #58a6ff;
  --ok: #3fb950;
  --warn: #d29922;
  --bad: #f85149;
  --mono: ui-monospace, "SF Mono", Menlo, monospace;
}
* { box-sizing: border-box; }
body {
  margin: 0;
  font-family: system-ui, -apple-system, "Segoe UI", Roboto, sans-serif;
  background: var(--bg);
  color: var(--text);
  line-height: 1.5;
  min-height: 100vh;
}
header {
  padding: 1.25rem 1.5rem;
  border-bottom: 1px solid var(--border);
  background: var(--panel);
}
header h1 { margin: 0; font-size: 1.15rem; font-weight: 600; letter-spacing: -0.02em; }
header p { margin: 0.35rem 0 0; color: var(--muted); font-size: 0.875rem; }
main { padding: 1.25rem 1.5rem; max-width: 960px; margin: 0 auto; }
a { color: var(--accent2); text-decoration: none; }
a:hover { text-decoration: underline; }
table.data {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
  background: var(--panel);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
}
table.data th, table.data td {
  padding: 0.65rem 0.85rem;
  text-align: left;
  border-bottom: 1px solid var(--border);
  vertical-align: top;
}
table.data th {
  color: var(--muted);
  font-weight: 500;
  font-size: 0.75rem;
  text-transform: uppercase;
  letter-spacing: 0.04em;
}
table.data tr:last-child td { border-bottom: none; }
table.data tr:hover td { background: rgba(163, 113, 247, 0.06); }
.mono { font-family: var(--mono); font-size: 0.8rem; }
.pill {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
  background: rgba(163, 113, 247, 0.2);
  color: var(--accent);
}
.pill.root { background: rgba(248, 81, 73, 0.2); color: var(--bad); }
.explain {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.15rem;
  margin: 1rem 0;
  font-size: 0.95rem;
  line-height: 1.65;
  white-space: pre-wrap;
}
.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.1rem;
  margin-bottom: 0.75rem;
}
.card h3 { margin: 0 0 0.35rem; font-size: 0.9rem; }
.card .claim { color: var(--muted); font-size: 0.85rem; margin-bottom: 0.5rem; }
pre {
  margin: 0.35rem 0 0;
  padding: 0.65rem;
  background: var(--bg);
  border-radius: 6px;
  overflow: auto;
  font-size: 0.72rem;
  max-height: 200px;
  border: 1px solid var(--border);
}
.back { margin-bottom: 1rem; display: inline-block; }
.score { font-weight: 600; font-family: var(--mono); }
"""


def _query_index() -> list[tuple]:
    if not os.path.isfile(_DB_PATH):
        return []
    conn = sqlite3.connect(_DB_PATH)
    try:
        cur = conn.execute(
            """
            SELECT trace_id, analyzed_at, failure_type, root_cause_step, file_path
            FROM analyses
            ORDER BY analyzed_at DESC
            """
        )
        return cur.fetchall()
    except sqlite3.OperationalError:
        return []
    finally:
        conn.close()


def _load_analysis_json(trace_id: str) -> Optional[dict[str, Any]]:
    path = os.path.join(_ANALYSES_DIR, f"{trace_id}.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _page_shell(title: str, body: str) -> bytes:
    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8"/>
  <meta name="viewport" content="width=device-width, initial-scale=1"/>
  <title>{html.escape(title)}</title>
  <style>{_CSS}</style>
</head>
<body>
{body}
</body>
</html>"""
    return doc.encode("utf-8")


class AnalysisViewerHandler(http.server.BaseHTTPRequestHandler):
    server_version = "AnalysisViewer/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._send_index()
        elif path.startswith("/analysis/"):
            tid = path.removeprefix("/analysis/").strip()
            if not tid or "/" in tid or ".." in tid:
                self._send_error(400, "Bad trace id")
                return
            self._send_detail(tid)
        else:
            self._send_error(404, "Not found")

    def _send(self, code: int, body: bytes) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, msg: str) -> None:
        body = _page_shell(
            "Error",
            f'<main><p style="color:var(--bad)">{html.escape(msg)}</p>'
            f'<a class="back" href="/">← Back</a></main>',
        )
        self._send(code, body)

    def _send_index(self) -> None:
        rows = _query_index()
        if not rows and not os.path.isfile(_DB_PATH):
            inner = "<p>No database yet. Run the pipeline, then <code class='mono'>python analysis/analyzer.py</code>.</p>"
        elif not rows:
            inner = (
                "<p>No saved analyses yet. Run:</p>"
                "<pre style='max-height:none'>python analysis/analyzer.py &lt;trace_id&gt;</pre>"
                "<p class='meta'>Results are written to <code class='mono'>storage/analyses/</code> and indexed in SQLite.</p>"
            )
        else:
            trs = []
            for trace_id, at, ftype, root_step, fp in rows:
                trs.append(
                    "<tr>"
                    f'<td class="mono"><a href="/analysis/{html.escape(trace_id, quote=True)}">'
                    f"{html.escape(trace_id[:8])}…</a></td>"
                    f"<td>{html.escape(at)}</td>"
                    f"<td><span class='pill'>{html.escape(ftype)}</span></td>"
                    f"<td class='mono'>{html.escape(root_step)}</td>"
                    f'<td class="mono" style="font-size:0.72rem;color:var(--muted)">'
                    f"{html.escape(os.path.basename(fp or ''))}</td>"
                    "</tr>"
                )
            inner = f"""
<table class="data">
  <thead><tr><th>Trace</th><th>Analyzed (UTC)</th><th>Failure type</th><th>Root step</th><th>File</th></tr></thead>
  <tbody>{"".join(trs)}</tbody>
</table>
"""
        body = _page_shell(
            "Analyses",
            f"""
<header>
  <h1>Failure analyses</h1>
  <p>SQLite <span class="mono">analyses</span> · {html.escape(_DB_PATH)} · Trace runs: port 8765</p>
</header>
<main>{inner}</main>
""",
        )
        self._send(200, body)

    def _send_detail(self, trace_id: str) -> None:
        data = _load_analysis_json(trace_id)
        if data is None:
            self._send_error(404, f"No analysis JSON for trace {trace_id}")
            return

        explanation = html.escape(str(data.get("explanation", "")))
        ftype = html.escape(str(data.get("failure_type", "")))
        root = html.escape(str(data.get("root_cause_step", "")))

        score_rows = []
        for s in data.get("step_scores") or []:
            step = html.escape(str(s.get("step", "")))
            qs = s.get("quality_score", "")
            issues = s.get("issues") or []
            iss_txt = html.escape("; ".join(str(i) for i in issues) if issues else "—")
            root_badge = (
                '<span class="pill root">root</span>' if s.get("is_root_cause") else ""
            )
            score_rows.append(
                f"<tr><td class='mono'>{step}</td>"
                f"<td class='score'>{html.escape(str(qs))}</td>"
                f"<td>{iss_txt}</td><td>{root_badge}</td></tr>"
            )

        ev_cards = []
        for ev in data.get("evidence_chain") or []:
            st = html.escape(str(ev.get("step", "")))
            claim = html.escape(str(ev.get("claim", "")))
            inp = html.escape(str(ev.get("input_snippet", "")))
            outp = html.escape(str(ev.get("output_snippet", "")))
            ev_cards.append(
                f"""<div class="card"><h3>{st}</h3>
                <div class="claim">{claim}</div>
                <details><summary>Input snippet</summary><pre>{inp}</pre></details>
                <details><summary>Output snippet</summary><pre>{outp}</pre></details></div>"""
            )

        body = _page_shell(
            f"Analysis {trace_id[:8]}",
            f"""
<header>
  <a class="back" href="/">← All analyses</a>
  <h1 class="mono" style="font-size:1rem">{html.escape(trace_id)}</h1>
  <p style="margin:0.35rem 0 0;color:var(--muted);font-size:0.85rem">
    <span class="pill">{ftype}</span>
    &nbsp;· root step: <span class="mono">{root}</span>
  </p>
</header>
<main>
  <h2 style="font-size:0.85rem;color:var(--muted);font-weight:600;margin:0 0 0.5rem">Explanation</h2>
  <div class="explain">{explanation}</div>

  <h2 style="font-size:0.85rem;color:var(--muted);font-weight:600;margin:1rem 0 0.5rem">Step scores</h2>
  <table class="data">
    <thead><tr><th>Step</th><th>Quality</th><th>Issues</th><th></th></tr></thead>
    <tbody>{"".join(score_rows) or "<tr><td colspan='4' class='meta'>No scores</td></tr>"}</tbody>
  </table>

  <h2 style="font-size:0.85rem;color:var(--muted);font-weight:600;margin:1.25rem 0 0.5rem">Evidence</h2>
  {"".join(ev_cards) if ev_cards else "<p class='meta'>No evidence entries.</p>"}

  <details style="margin-top:1.25rem"><summary class="mono" style="cursor:pointer;color:var(--accent2)">Raw JSON</summary>
  <pre>{html.escape(json.dumps(data, indent=2)[:48000])}</pre></details>
</main>
""",
        )
        self._send(200, body)


def _print_table() -> None:
    rows = _query_index()
    if not os.path.isfile(_DB_PATH):
        print("No database at", _DB_PATH)
        return
    if not rows:
        print("(no analysis rows — run python analysis/analyzer.py <trace_id>)")
        return
    w = [36, 28, 28, 16, 36]
    hdr = f"{'trace_id':<{w[0]}} {'analyzed_at':<{w[1]}} {'failure_type':<{w[2]}} {'root':<{w[3]}} file"
    print(hdr)
    print("-" * len(hdr))
    for trace_id, at, ftype, root_step, fp in rows:
        print(f"{trace_id:<{w[0]}} {at:<{w[1]}} {ftype:<{w[2]}} {root_step:<{w[3]}} {os.path.basename(fp or '')}")


def main() -> None:
    p = argparse.ArgumentParser(description="View saved failure analyses")
    p.add_argument("--table", action="store_true", help="Print analyses index as text")
    p.add_argument("--port", type=int, default=8766, help="HTTP port (default 8766)")
    p.add_argument(
        "--bind",
        default=None,
        metavar="ADDR",
        help="Force bind address (e.g. 127.0.0.1 or 0.0.0.0). Default: try IPv6 :: then 127.0.0.1",
    )
    p.add_argument("--open", action="store_true", help="Open the UI in your default browser")
    args = p.parse_args()
    if args.table:
        _print_table()
        return
    run_local_http(
        AnalysisViewerHandler,
        args.port,
        title="Analysis viewer",
        bind=args.bind,
        open_browser=args.open,
    )


if __name__ == "__main__":
    main()
