from llm import complete_json

SYSTEM_PROMPT = """You are a document entity extractor.
Extract structured information from the document and return valid JSON with this exact shape:
{
  "names": ["list of person or organization names"],
  "dates": ["list of dates in any format found"],
  "amounts": ["list of monetary amounts or quantities"],
  "key_terms": ["list of important domain-specific terms or concepts"]
}
Return only the JSON object, no explanation."""


def extract_entities(doc: dict) -> dict:
    """
    Step 2 — Extraction.
    Uses an LLM to extract structured entities from the document text.
    """
    return complete_json(SYSTEM_PROMPT, [doc["raw_text"]])
