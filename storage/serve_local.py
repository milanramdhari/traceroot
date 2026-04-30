"""
Bind a local-only dev HTTP server with sensible fallbacks.

Many browsers resolve ``localhost`` to ``::1`` (IPv6) first; a server that only
listens on ``127.0.0.1`` (IPv4) then shows "connection failed". We try IPv6
``::`` with ``IPV6_V6ONLY=0`` first, then fall back to ``127.0.0.1``.
"""
from __future__ import annotations

import http.server
import socket
import webbrowser
from typing import Type


def run_local_http(
    handler_class: Type[http.server.BaseHTTPRequestHandler],
    port: int,
    *,
    title: str,
    bind: str | None = None,
    open_browser: bool = False,
) -> None:
    httpd: http.server.ThreadingHTTPServer | None = None
    chosen = ""

    if bind:
        try:
            httpd = http.server.ThreadingHTTPServer((bind, port), handler_class)
            chosen = f"{bind}:{port}"
        except OSError as e:
            raise SystemExit(f"Could not bind {bind}:{port} — {e}. Try another --port.") from e
    else:
        class _DualStackIPv6(http.server.ThreadingHTTPServer):
            address_family = socket.AF_INET6

            def server_bind(self) -> None:
                self.socket.setsockopt(socket.IPPROTO_IPV6, socket.IPV6_V6ONLY, 0)
                super().server_bind()

        for factory, addr, label in (
            (_DualStackIPv6, ("::", port), "IPv6 (::, dual-stack)"),
            (http.server.ThreadingHTTPServer, ("127.0.0.1", port), "IPv4 (127.0.0.1)"),
        ):
            try:
                httpd = factory(addr, handler_class)
                chosen = f"{label} port {port}"
                break
            except OSError:
                continue

        if httpd is None:
            raise SystemExit(
                f"Could not bind port {port}. It may be in use — try: --port 8875"
            )

    url = f"http://127.0.0.1:{port}/"
    print()
    print(title)
    print(f"  {url}")
    if "IPv6" in chosen:
        print(f"  http://[::1]:{port}/  (use this if you type localhost and it fails)")
    print(f"  ({chosen})")
    print("  Keep this terminal running while you use the UI (Ctrl+C to stop).")
    print(
        "  Tip: use http:// not https://. Use 127.0.0.1 or [::1] above — "
        "plain 'localhost' can pick the wrong IP on some systems."
    )
    print()
    if open_browser:
        webbrowser.open(url)

    try:
        assert httpd is not None
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nStopped.")
