import os
from typing import Optional, Tuple

from pypdf import PdfReader

from tracing.tracer import instrument


def _read_pdf(path: str) -> str:
    reader = PdfReader(path)
    parts = []
    for page in reader.pages:
        parts.append(page.extract_text() or "")
    return "\n\n".join(parts).strip()


def _read_file(path: str) -> Tuple[str, Optional[str]]:
    ext = os.path.splitext(path)[1].lower()
    if ext == ".pdf":
        raw_text = _read_pdf(path)
        return raw_text, path
    with open(path, "r", encoding="utf-8") as f:
        return f.read(), path


@instrument("intake")
def ingest(source: str) -> dict:
    """
    Step 1 — Intake.
    Accepts a raw text string, a markdown string, or a file path.
    Returns normalized document dict for downstream steps.
    """
    if len(source) < 4096 and os.path.isfile(source):
        raw_text, path = _read_file(source)
        fmt = _detect_format(path, raw_text)
    else:
        raw_text = source
        fmt = _detect_format(None, raw_text)
        path = None

    return {
        "raw_text": raw_text.strip(),
        "format": fmt,
        "char_count": len(raw_text.strip()),
        "source_path": path,
    }


def _detect_format(path: Optional[str], text: str) -> str:
    if path:
        ext = os.path.splitext(path)[1].lower()
        if ext in (".md", ".markdown"):
            return "markdown"
        if ext == ".pdf":
            return "pdf"
    if any(line.startswith("#") for line in text.splitlines()):
        return "markdown"
    return "text"
