from dataclasses import dataclass, field
from typing import Optional


@dataclass
class LLMCall:
    model: str
    prompt: str         # full content sent to the model
    raw_response: str   # raw text before JSON parsing
    tokens_in: int
    tokens_out: int


@dataclass
class Span:
    step: str           # "intake" | "extraction" | "classification" | "summarization"
    started_at: str     # ISO 8601 timestamp
    latency_ms: float = 0.0
    input: dict = field(default_factory=dict)
    output: Optional[dict] = None
    llm_call: Optional[LLMCall] = None  # None for steps with no LLM call
    confidence: Optional[float] = None  # model self-reported confidence (scale varies by step)
    error: Optional[str] = None
