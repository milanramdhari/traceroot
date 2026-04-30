from dataclasses import dataclass, field
from typing import Optional

from tracing.span import Span


@dataclass
class Trace:
    trace_id: str
    started_at: str
    finished_at: Optional[str] = None
    spans: list = field(default_factory=list)   # list[Span]
    final_output: Optional[dict] = None
    status: str = "running"     # "running" | "success" | "failure" | "degraded"
