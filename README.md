# TraceRoot

> Root-cause analysis and observability for multi-step AI pipelines.

TraceRoot is an observability and failure forensics platform for LLM-powered workflows. It traces every intermediate step in an AI pipeline, captures structured execution metadata, and identifies where failures originate when the final output is incorrect.

Modern AI pipelines often fail silently. A bad final response may actually originate several steps earlier in the workflow. TraceRoot provides end-to-end visibility into pipeline execution so failures can be diagnosed, analyzed, and converted into reusable evaluation cases.

---

## Getting Started

```bash
# Install dependencies
pip install -r requirements.txt

# Run the pipeline (processes a sample invoice document)
python pipeline/pipeline.py

# Analyze the most recent trace
python analysis/analyzer.py

# Analyze a specific trace
python analysis/analyzer.py <trace_id>
```

---

## Architecture

```
pipeline/   → 4-step document processing (intake → extraction → classification → summarization)
tracing/    → Trace/Span dataclasses and @instrument decorator
storage/    → JSON trace files + SQLite index (storage/index.db)
analysis/   → Backward trace analyzer, LLM-as-judge, failure categorization
api/        → FastAPI backend (planned)
frontend/   → UI (planned)
evals/      → Evaluation datasets (planned)
docker/     → Docker config (planned)
```

---

## Key Files

| File | Role |
|---|---|
| `pipeline/llm.py` | Central LLM interface via LiteLLM; set `LLM_MODEL` env var to switch providers |
| `pipeline/pipeline.py` | Orchestrator — runs all 4 steps wrapped in a trace |
| `tracing/tracer.py` | `@instrument("step_name")` decorator, `start_trace` / `finish_trace` |
| `storage/store.py` | `save_trace()` and `save_analysis()` — writes JSON + indexes SQLite |
| `analysis/analyzer.py` | `analyze_trace(trace_id)` entry point |

---

## Environment Variables

Create a `.env` file at the project root (never commit it):

```
ANTHROPIC_API_KEY=...   # default LLM provider
OPENAI_API_KEY=...      # optional
GEMINI_API_KEY=...      # optional
LLM_MODEL=anthropic/claude-sonnet-4-6   # override to switch providers
```

---

## Pipeline Steps

Each step is independently traced and analyzed:

1. **Intake** — accept raw document (text, markdown, or PDF)
2. **Extraction** — LLM extracts names, dates, amounts, key terms
3. **Classification** — LLM classifies document type (contract, invoice, report, correspondence)
4. **Summarization** — LLM generates a structured summary tailored to the document type

---

## Failure Analysis

When a trace is flagged, TraceRoot walks backward through spans using an LLM-as-judge to score each step's output. The first step with a significant quality drop is flagged as the root cause, categorized, and explained with an evidence chain.

**Failure taxonomy:**

| Type | Meaning |
|---|---|
| `extraction_hallucination` | Entities extracted that don't exist in the source |
| `misclassification` | Wrong document type assigned |
| `propagation_error` | Correct step output misused by the next step |
| `prompt_failure` | LLM ignored instructions despite high confidence |
| `context_loss` | Important info from earlier steps was dropped |

---

## Storage Layout

```
storage/
├── index.db          # SQLite: traces + analyses tables
├── traces/           # one <trace_id>.json per pipeline run
└── analyses/         # one <trace_id>.json per analysis run
```

---

## Viewing Traces (Local UI)

```bash
python3 storage/trace_viewer.py         # start web dashboard on port 8765
python3 storage/trace_viewer.py --open  # auto-open browser
python3 storage/trace_viewer.py --table # terminal table view
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) — table of all traces, click a row to see span timelines, latencies, and full LLM prompts/responses.

---

## Viewing Failure Analyses (Local UI)

```bash
python3 storage/analysis_viewer.py         # start web dashboard on port 8766
python3 storage/analysis_viewer.py --open  # auto-open browser
python3 storage/analysis_viewer.py --table # terminal table view
```

Open [http://127.0.0.1:8766/](http://127.0.0.1:8766/) — table of analyses with explanation, step scores, and evidence snippets.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| LLM Provider | Anthropic Claude (via LiteLLM — switchable) |
| Storage | SQLite + JSON traces |
| Backend API | FastAPI (planned) |
| Frontend | React or Streamlit (planned) |
| Containerization | Docker (planned) |
