from dataclasses import dataclass, field
from typing import Optional


@dataclass
class StepScore:
    step: str
    quality_score: int      # 1–5, judge's rating of this step's output
    issues: list = field(default_factory=list)   # list[str] of specific problems found
    is_root_cause: bool = False


@dataclass
class Evidence:
    step: str
    claim: str              # human-readable description of the problem
    input_snippet: str      # relevant excerpt from span input
    output_snippet: str     # relevant excerpt from span output


@dataclass
class FailureAnalysis:
    trace_id: str
    root_cause_step: str
    failure_type: str       # see taxonomy in categorizer.py
    explanation: str        # one-paragraph human-readable diagnosis
    evidence_chain: list = field(default_factory=list)  # list[Evidence]
    step_scores: list = field(default_factory=list)     # list[StepScore]


# Failure type taxonomy
FAILURE_TYPES = {
    "extraction_hallucination": "Extracted entities that do not appear in the source document",
    "misclassification": "Document assigned to the wrong type",
    "propagation_error": "A correct step's output was misinterpreted by the next step",
    "prompt_failure": "The LLM ignored or misunderstood its instructions",
    "context_loss": "Important information from earlier steps was dropped",
}
