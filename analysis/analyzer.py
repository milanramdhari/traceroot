import json
import os
import sqlite3
import sys
from dataclasses import asdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.llm import complete_json
from tracing.span import Span, LLMCall
from tracing.trace import Trace
from analysis.models import FailureAnalysis, Evidence, StepScore
from analysis.judge import score_step
from analysis.categorizer import categorize
from storage.store import save_analysis

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_TRACES_DIR = os.path.join(_ROOT, "storage", "traces")
_DB_PATH = os.path.join(_ROOT, "storage", "index.db")

EXPLANATION_SYSTEM = """You are a root cause analyst for AI pipeline failures.

Write a VERY SHORT diagnosis: only what matters, no intro, no conclusion fluff, no repetition.
Use plain language. Cite concrete facts from the evidence (step names, scores, field values) when relevant.

Format the "explanation" value as bullet points:
- Each bullet = ONE tight line (aim under ~90 characters per line).
- Use 3 to 5 bullets total, no more.
- Cover only: (1) what failed, (2) where it started (step), (3) how downstream was affected — nothing else.

Return valid JSON only:
{
  "explanation": "- First bullet\\n- Second bullet\\n- Third bullet",
  "confidence": <integer 1-5, your confidence in this diagnosis>
}"""


def _load_trace(trace_id: str) -> Trace:
    path = os.path.join(_TRACES_DIR, f"{trace_id}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Trace not found: {path}")
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    spans = []
    for s in data.get("spans", []):
        llm_raw = s.get("llm_call")
        llm_call = LLMCall(**llm_raw) if llm_raw else None
        spans.append(Span(
            step=s["step"],
            started_at=s["started_at"],
            latency_ms=s.get("latency_ms", 0.0),
            input=s.get("input", {}),
            output=s.get("output"),
            llm_call=llm_call,
            confidence=s.get("confidence"),
            error=s.get("error"),
        ))

    return Trace(
        trace_id=data["trace_id"],
        started_at=data["started_at"],
        finished_at=data.get("finished_at"),
        spans=spans,
        final_output=data.get("final_output"),
        status=data.get("status", "unknown"),
    )


def _get_source_text(spans: list) -> str:
    intake = next((s for s in spans if s.step == "intake"), None)
    if intake and intake.output:
        return intake.output.get("raw_text", "")
    return ""


def _build_evidence(span: Span, score: StepScore) -> Evidence:
    input_snippet = json.dumps(span.input, indent=2)[:500]
    output_snippet = json.dumps(span.output, indent=2)[:500] if span.output else "null"
    claim = "; ".join(score.issues) if score.issues else f"Quality score {score.quality_score}/5"
    return Evidence(
        step=span.step,
        claim=claim,
        input_snippet=input_snippet,
        output_snippet=output_snippet,
    )


def analyze_trace_obj(trace: Trace) -> FailureAnalysis:
    spans = trace.spans
    source_text = _get_source_text(spans)

    # Score each span in reverse order (backward trace walk)
    step_scores = []
    for span in reversed(spans):
        score = score_step(span, source_text)
        step_scores.append(score)

    # Root cause: first span (from back) with quality ≤ 2, else lowest scorer
    root_score = next((s for s in step_scores if s.quality_score <= 2), None)
    if root_score is None:
        root_score = min(step_scores, key=lambda s: s.quality_score)
    root_score.is_root_cause = True
    root_cause_step = root_score.step

    # Categorize failure
    failure_type = categorize(root_cause_step, root_score.issues, step_scores, spans)

    # Build evidence chain for all spans with issues, root cause first
    evidence_chain = []
    root_span = next((s for s in spans if s.step == root_cause_step), None)
    if root_span:
        evidence_chain.append(_build_evidence(root_span, root_score))
    for score in step_scores:
        if score.step != root_cause_step and score.issues:
            span = next((s for s in spans if s.step == score.step), None)
            if span:
                evidence_chain.append(_build_evidence(span, score))

    # Generate human-readable explanation
    scores_summary = [
        {"step": s.step, "quality_score": s.quality_score, "issues": s.issues}
        for s in step_scores
    ]
    explanation_result = complete_json(
        EXPLANATION_SYSTEM,
        [
            f"Trace ID: {trace.trace_id}",
            f"Root cause step: {root_cause_step}",
            f"Failure type: {failure_type}",
            f"Step scores:\n{json.dumps(scores_summary, indent=2)}",
            f"Root cause issues: {root_score.issues}",
        ],
    )
    explanation = explanation_result.get("explanation", "Unable to generate explanation.")

    return FailureAnalysis(
        trace_id=trace.trace_id,
        root_cause_step=root_cause_step,
        failure_type=failure_type,
        explanation=explanation,
        evidence_chain=evidence_chain,
        step_scores=step_scores,
    )


def analyze_trace(trace_id: str) -> FailureAnalysis:
    trace = _load_trace(trace_id)
    return analyze_trace_obj(trace)


def _latest_trace_id() -> str:
    conn = sqlite3.connect(_DB_PATH)
    row = conn.execute(
        "SELECT trace_id FROM traces ORDER BY timestamp DESC LIMIT 1"
    ).fetchone()
    conn.close()
    if not row:
        raise RuntimeError("No traces found in index.db")
    return row[0]


if __name__ == "__main__":
    trace_id = sys.argv[1] if len(sys.argv) > 1 else _latest_trace_id()
    print(f"Analyzing trace: {trace_id}\n")
    result = analyze_trace(trace_id)
    out_path = save_analysis(asdict(result))
    print(f"[analysis] saved={out_path}\n")
    print(json.dumps(asdict(result), indent=2))
