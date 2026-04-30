"""
Local trace dashboard (SQLite index + JSON files under storage/traces/).

  python storage/trace_viewer.py
  open http://127.0.0.1:8765/

  python storage/trace_viewer.py --table   # quick terminal listing
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
_DB_PATH = os.path.join(_ROOT, "storage", "index.db")
_TRACES_DIR = os.path.join(_ROOT, "storage", "traces")

_CSS = """
:root {
  --bg: #0c0f14;
  --panel: #141922;
  --border: #252d3a;
  --text: #e6edf3;
  --muted: #8b9cb3;
  --accent: #58a6ff;
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
main { padding: 1.25rem 1.5rem; max-width: 1200px; margin: 0 auto; }
a { color: var(--accent); text-decoration: none; }
a:hover { text-decoration: underline; }
table {
  width: 100%;
  border-collapse: collapse;
  font-size: 0.875rem;
  background: var(--panel);
  border-radius: 10px;
  overflow: hidden;
  border: 1px solid var(--border);
}
th, td { padding: 0.65rem 0.85rem; text-align: left; border-bottom: 1px solid var(--border); }
th { color: var(--muted); font-weight: 500; font-size: 0.75rem; text-transform: uppercase; letter-spacing: 0.04em; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: rgba(88, 166, 255, 0.06); }
.mono { font-family: var(--mono); font-size: 0.8rem; }
.pill {
  display: inline-block;
  padding: 0.15rem 0.5rem;
  border-radius: 999px;
  font-size: 0.75rem;
  font-weight: 500;
}
.pill.success { background: rgba(63, 185, 80, 0.2); color: var(--ok); }
.pill.failure { background: rgba(248, 81, 73, 0.2); color: var(--bad); }
.pill.degraded { background: rgba(210, 153, 34, 0.2); color: var(--warn); }
.pill.running { background: rgba(139, 156, 179, 0.2); color: var(--muted); }
.timeline {
  display: flex;
  flex-direction: column;
  gap: 0.75rem;
}
.card {
  background: var(--panel);
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 1rem 1.1rem;
}
.card h3 { margin: 0 0 0.5rem; font-size: 0.95rem; display: flex; align-items: center; gap: 0.5rem; flex-wrap: wrap; }
.meta { color: var(--muted); font-size: 0.8rem; margin-bottom: 0.5rem; }
details { margin-top: 0.5rem; }
details summary { cursor: pointer; color: var(--accent); font-size: 0.8rem; user-select: none; }
pre {
  margin: 0.5rem 0 0;
  padding: 0.75rem;
  background: var(--bg);
  border-radius: 6px;
  overflow: auto;
  font-size: 0.72rem;
  max-height: 320px;
  border: 1px solid var(--border);
}
.back { margin-bottom: 1rem; display: inline-block; }
"""


def _pill(status: str) -> str:
    s = (status or "").lower()
    cls = s if s in ("success", "failure", "degraded", "running") else "running"
    label = html.escape(status or "unknown")
    return f'<span class="pill {cls}">{label}</span>'


def _query_index() -> list[tuple]:
    if not os.path.isfile(_DB_PATH):
        return []
    conn = sqlite3.connect(_DB_PATH)
    cur = conn.execute(
        """
        SELECT trace_id, timestamp, status, final_score, file_path
        FROM traces
        ORDER BY timestamp DESC
        """
    )
    rows = cur.fetchall()
    conn.close()
    return rows


def _load_trace_json(trace_id: str) -> Optional[dict[str, Any]]:
    path = os.path.join(_TRACES_DIR, f"{trace_id}.json")
    if not os.path.isfile(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _page_shell(title: str, body: str) -> bytes:
    html_doc = f"""<!DOCTYPE html>
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
    return html_doc.encode("utf-8")


class TraceViewerHandler(http.server.BaseHTTPRequestHandler):
    server_version = "TraceViewer/1.0"

    def log_message(self, format: str, *args: Any) -> None:
        # Quieter default logging
        sys.stderr.write("%s - - [%s] %s\n" % (self.address_string(), self.log_date_time_string(), format % args))

    def do_GET(self) -> None:
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path.rstrip("/") or "/"

        if path == "/":
            self._send_index()
        elif path.startswith("/trace/"):
            tid = path.removeprefix("/trace/").strip()
            if not tid or "/" in tid or ".." in tid:
                self._send_error(400, "Bad trace id")
                return
            self._send_detail(tid)
        else:
            self._send_error(404, "Not found")

    def _send(self, code: int, body: bytes, content_type: str = "text/html; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_error(self, code: int, msg: str) -> None:
        body = _page_shell(
            "Error",
            f'<main><p style="color:var(--bad)">{html.escape(msg)}</p><a class="back" href="/">← Back</a></main>',
        )
        self._send(code, body)

    def _send_index(self) -> None:
        rows = _query_index()
        if not rows and not os.path.isfile(_DB_PATH):
            inner = (
                "<p>No index database yet. Run the pipeline once to create "
                "<code class='mono'>storage/index.db</code>.</p>"
            )
        elif not rows:
            inner = "<p>Index exists but has no rows yet.</p>"
        else:
            trs = []
            for trace_id, ts, status, score, file_path in rows:
                score_s = "" if score is None else f"{score:.2f}"
                trs.append(
                    "<tr>"
                    f'<td class="mono"><a href="/trace/{html.escape(trace_id, quote=True)}">{html.escape(trace_id[:8])}…</a></td>'
                    f"<td>{html.escape(ts)}</td>"
                    f"<td>{_pill(status)}</td>"
                    f"<td>{html.escape(score_s)}</td>"
                    f'<td class="mono" style="font-size:0.72rem;color:var(--muted)">{html.escape(os.path.basename(file_path or ""))}</td>'
                    "</tr>"
                )
            inner = f"""
<table>
  <thead><tr><th>Trace</th><th>Time (UTC)</th><th>Status</th><th>Avg confidence</th><th>File</th></tr></thead>
  <tbody>{"".join(trs)}</tbody>
</table>
"""
        body = _page_shell(
            "Traces",
            f"""
<header><h1>Pipeline traces</h1><p>SQLite index · {html.escape(_DB_PATH)}</p></header>
<main>{inner}</main>
""",
        )
        self._send(200, body)

    def _send_detail(self, trace_id: str) -> None:
        data = _load_trace_json(trace_id)
        if data is None:
            self._send_error(404, f"No JSON trace file for id {trace_id}")
            return

        spans_html = []
        for sp in data.get("spans") or []:
            step = html.escape(str(sp.get("step", "")))
            lat = sp.get("latency_ms", 0)
            conf = sp.get("confidence")
            err = sp.get("error")
            conf_s = "" if conf is None else f" · confidence <span class='mono'>{html.escape(str(conf))}</span>"
            err_s = (
                f"<p style='color:var(--bad);margin:0.35rem 0 0;font-size:0.85rem'>{html.escape(str(err))}</p>"
                if err
                else ""
            )
            llm = sp.get("llm_call")
            llm_block = ""
            if llm and isinstance(llm, dict):
                model = html.escape(str(llm.get("model", "")))
                tin = llm.get("tokens_in", "")
                tout = llm.get("tokens_out", "")
                llm_block = f"<p class='meta'>Model {model} · tokens in/out: {tin} / {tout}</p>"
                if llm.get("prompt"):
                    llm_block += (
                        "<details><summary>Prompt</summary><pre>"
                        + html.escape(llm["prompt"][:8000])
                        + ("…" if len(str(llm.get("prompt", ""))) > 8000 else "")
                        + "</pre></details>"
                    )
                if llm.get("raw_response"):
                    rr = str(llm["raw_response"])
                    llm_block += (
                        "<details><summary>Raw response</summary><pre>"
                        + html.escape(rr[:12000])
                        + ("…" if len(rr) > 12000 else "")
                        + "</pre></details>"
                    )

            inp = json.dumps(sp.get("input"), indent=2, default=str)
            out = json.dumps(sp.get("output"), indent=2, default=str)
            spans_html.append(
                f"""
<div class="card">
  <h3>{step} <span class="meta" style="font-weight:400">· {lat:.1f} ms{conf_s}</span></h3>
  {err_s}
  {llm_block}
  <details><summary>Input JSON</summary><pre>{html.escape(inp[:16000])}{"…" if len(inp) > 16000 else ""}</pre></details>
  <details><summary>Output JSON</summary><pre>{html.escape(out[:16000])}{"…" if len(out) > 16000 else ""}</pre></details>
</div>
"""
            )

        fo = data.get("final_output")
        fo_pre = (
            f"<details style='margin-top:1rem'><summary>Final output</summary><pre>{html.escape(json.dumps(fo, indent=2, default=str)[:24000])}</pre></details>"
            if fo is not None
            else ""
        )

        body = _page_shell(
            f"Trace {trace_id[:8]}",
            f"""
<header>
  <a class="back" href="/">← All traces</a>
  <h1 class="mono" style="font-size:1rem">{html.escape(trace_id)}</h1>
  <p style="margin:0.35rem 0 0;color:var(--muted);font-size:0.85rem">
    {html.escape(str(data.get("started_at", "")))} → {html.escape(str(data.get("finished_at", "")))}
    · {_pill(str(data.get("status", "")))}
  </p>
</header>
<main>
  <h2 style="font-size:0.85rem;color:var(--muted);font-weight:600;margin:0 0 0.75rem">Spans</h2>
  <div class="timeline">{"".join(spans_html)}</div>
  {fo_pre}
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
        print("(no rows)")
        return
    w = [36, 28, 12, 8, 40]
    hdr = f"{'trace_id':<{w[0]}} {'timestamp':<{w[1]}} {'status':<{w[2]}} {'score':>{w[3]}} file"
    print(hdr)
    print("-" * len(hdr))
    for trace_id, ts, status, score, fp in rows:
        sc = "" if score is None else f"{score:.2f}"
        fn = os.path.basename(fp or "")
        print(f"{trace_id:<{w[0]}} {ts:<{w[1]}} {status:<{w[2]}} {sc:>{w[3]}} {fn}")


def main() -> None:
    p = argparse.ArgumentParser(description="View pipeline traces")
    p.add_argument("--table", action="store_true", help="Print SQLite index as a text table")
    p.add_argument("--port", type=int, default=8765, help="HTTP port (default 8765)")
    args = p.parse_args()

    if args.table:
        _print_table()
        return

    addr = ("127.0.0.1", args.port)
    with http.server.ThreadingHTTPServer(addr, TraceViewerHandler) as httpd:
        print(f"Trace viewer at http://{addr[0]}:{addr[1]}/  (Ctrl+C to stop)")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nStopped.")


if __name__ == "__main__":
    main()
