import json
import sys

from intake import ingest
from extraction import extract_entities
from classification import classify_document
from summarization import summarize

SAMPLE_DOCUMENT = """
INVOICE #1042
Date: March 15, 2024
Due Date: April 15, 2024

From: Acme Design Studio
To: GlobalTech Inc.

Services Rendered:
- UI/UX Design Consultation: $3,200.00
- Prototype Development: $1,800.00
- Accessibility Audit: $600.00

Subtotal: $5,600.00
Tax (8%): $448.00
Total Due: $6,048.00

Payment terms: Net 30. Late payments subject to 1.5% monthly interest.
Please remit payment to: payments@acmedesign.com
"""


def run_pipeline(source: str) -> dict:
    """
    Runs all 4 pipeline steps in sequence and returns the combined result.
    """
    doc = ingest(source)
    entities = extract_entities(doc)
    classification = classify_document(doc, entities)
    summary = summarize(doc, entities, classification)

    return {
        "intake": doc,
        "extraction": entities,
        "classification": classification,
        "summarization": summary,
    }


if __name__ == "__main__":
    source = sys.argv[1] if len(sys.argv) > 1 else SAMPLE_DOCUMENT
    result = run_pipeline(source)
    print(json.dumps(result, indent=2))
