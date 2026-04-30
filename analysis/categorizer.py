from analysis.models import StepScore
from tracing.span import Span


def categorize(root_cause_step: str, issues: list, step_scores: list, spans: list) -> str:
    """
    Maps (root_cause_step, issues, scores) to a failure taxonomy type.
    Checked in priority order.
    """
    issues_text = " ".join(issues).lower()

    # 1. Extraction hallucination: entities not present in source
    if root_cause_step == "extraction" and any(
        kw in issues_text for kw in ("not in source", "fabricat", "hallucin", "doesn't exist", "not found", "invented")
    ):
        return "extraction_hallucination"

    # 2. Misclassification: wrong document type
    if root_cause_step == "classification":
        return "misclassification"

    # 3. Context loss: summarization dropped important content
    if root_cause_step == "summarization" and any(
        kw in issues_text for kw in ("dropped", "missing", "omit", "lost", "not included", "ignored")
    ):
        return "context_loss"

    # 4. Propagation error: a good step's output was misused by the next step
    scores_by_step = {s.step: s.quality_score for s in step_scores}
    step_order = ["intake", "extraction", "classification", "summarization"]
    for i, step in enumerate(step_order[:-1]):
        next_step = step_order[i + 1]
        if (
            scores_by_step.get(step, 5) >= 4
            and scores_by_step.get(next_step, 5) <= 2
        ):
            return "propagation_error"

    # 5. Prompt failure: low quality despite high self-reported confidence
    root_span = next((s for s in spans if s.step == root_cause_step), None)
    root_score = next((s for s in step_scores if s.step == root_cause_step), None)
    if root_span and root_score:
        if root_span.confidence and root_span.confidence >= 4 and root_score.quality_score <= 2:
            return "prompt_failure"

    # Default
    return "propagation_error"
