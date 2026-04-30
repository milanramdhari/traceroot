from llm import complete_json
from tracing.tracer import instrument

SYSTEM_PROMPT = """You are a document classifier.
Given a document and a summary of its extracted entities, classify the document type.

Valid types: contract, invoice, report, correspondence

Return valid JSON with this exact shape:
{
  "document_type": "<one of the valid types>",
  "confidence": <integer 1-5 rating your certainty in this classification>,
  "reasoning": "<one sentence explaining the classification>"
}
Return only the JSON object, no explanation."""


@instrument("classification")
def classify_document(doc: dict, entities: dict) -> dict:
    """
    Step 3 — Classification.
    Classifies the document type using the raw text and extracted entities.
    """
    entity_summary = (
        f"Names: {entities.get('names', [])}\n"
        f"Dates: {entities.get('dates', [])}\n"
        f"Amounts: {entities.get('amounts', [])}\n"
        f"Key terms: {entities.get('key_terms', [])}"
    )

    return complete_json(SYSTEM_PROMPT, [doc["raw_text"], entity_summary])
