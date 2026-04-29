from llm import complete_json

TYPE_INSTRUCTIONS = {
    "contract": "Focus on parties involved, obligations, key terms, dates, and any penalties or conditions.",
    "invoice": "Focus on vendor, client, line items, amounts, due date, and payment terms.",
    "report": "Focus on findings, conclusions, recommendations, and supporting data points.",
    "correspondence": "Focus on sender, recipient, purpose of communication, action items, and tone.",
}

SYSTEM_PROMPT_TEMPLATE = """You are a document summarizer.
Summarize the document as a {document_type}.
{instructions}

Return valid JSON with this exact shape:
{{
  "summary": "<concise paragraph summary>",
  "key_points": ["list of 3-5 bullet point highlights"],
  "document_type": "{document_type}"
}}
Return only the JSON object, no explanation."""


def summarize(doc: dict, entities: dict, classification: dict) -> dict:
    """
    Step 4 — Summarization.
    Generates a structured summary tailored to the classified document type.
    """
    doc_type = classification.get("document_type", "correspondence")
    instructions = TYPE_INSTRUCTIONS.get(doc_type, TYPE_INSTRUCTIONS["correspondence"])

    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(
        document_type=doc_type,
        instructions=instructions,
    )

    return complete_json(system_prompt, [doc["raw_text"]])
