import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from pipeline.llm import complete_json
from tracing.span import Span
from analysis.models import StepScore

JUDGE_SYSTEM = """You are a quality judge for AI document-processing pipeline steps.
Given a pipeline step's name, its input, and its output, evaluate the output quality.

Score the output on a scale of 1–5:
  5 = Perfect, fully correct
  4 = Good, minor issues
  3 = Acceptable, some problems
  2 = Poor, significant problems
  1 = Very poor or completely wrong

Return valid JSON with this exact shape:
{
  "quality_score": <integer 1-5>,
  "issues": ["concise description of each specific problem found, or empty list if none"],
  "is_root_cause": <true if this step's output is clearly incorrect or fabricated, false otherwise>,
  "confidence": <integer 1-5 rating your certainty in this judgment>
}
Return only the JSON object, no explanation."""


def score_step(span: Span, source_text: str) -> StepScore:
    """
    Uses an LLM judge to score the quality of a single pipeline span's output.
    source_text is the original document from the intake span.
    """
    input_summary = json.dumps(span.input, indent=2)[:2000]
    output_summary = json.dumps(span.output, indent=2)[:2000] if span.output else "null (step errored)"

    user_parts = [
        f"Pipeline step: {span.step}",
        f"Original source document:\n{source_text[:3000]}",
        f"Step input:\n{input_summary}",
        f"Step output:\n{output_summary}",
    ]

    result = complete_json(JUDGE_SYSTEM, user_parts)

    return StepScore(
        step=span.step,
        quality_score=int(result.get("quality_score", 3)),
        issues=result.get("issues", []),
        is_root_cause=bool(result.get("is_root_cause", False)),
    )
