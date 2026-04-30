# TraceRoot

> Root-cause analysis and observability for multi-step AI pipelines.

TraceRoot is an observability and failure forensics platform for LLM-powered workflows. It traces every intermediate step in an AI pipeline, captures structured execution metadata, and identifies where failures originate when the final output is incorrect.

Modern AI pipelines often fail silently. A bad final response may actually originate several steps earlier in the workflow. TraceRoot provides end-to-end visibility into pipeline execution so failures can be diagnosed, analyzed, and converted into reusable evaluation cases.

---

## Features

- Multi-step AI pipeline tracing
- Structured span-based observability
- Prompt and response logging
- Latency and token tracking
- Confidence scoring per pipeline step
- Automated root cause analysis
- Failure categorization system
- Interactive trace exploration UI
- Human feedback and trace flagging
- Auto-generated evaluation datasets from failures
- Regression testing against historical failures

---

## Example Pipeline

The system processes documents through a multi-step AI workflow:

1. Intake
2. Entity Extraction
3. Document Classification
4. Structured Summarization

Each stage is independently traced and analyzed.

---

## Failure Analysis

When a pipeline output is flagged as incorrect, TraceRoot performs backward trace analysis to determine where quality degradation first occurred.

Example failure categories:

- Extraction Hallucination
- Misclassification
- Prompt Failure
- Propagation Error
- Context Loss

The system generates an evidence chain showing how the failure propagated through the pipeline.

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.11+ |
| LLM Provider | OpenAI API |
| Orchestration | Custom Pipeline / LangChain |
| Observability | OpenTelemetry |
| Storage | SQLite + JSON traces |
| Backend API | FastAPI |
| Frontend | React or Streamlit |
| Containerization | Docker |

---

## Architecture Overview

```text
Document Input
      ↓
Pipeline Execution
      ↓
Step-Level Tracing
      ↓
Trace Storage
      ↓
Failure Detection
      ↓
Backward Root Cause Analysis
      ↓
Human Review & Feedback
      ↓
Evaluation Dataset Generation
```

---

## Project Structure

```text
traceroot/
├── pipeline/     # Multi-step AI pipeline stages (intake, extraction, classification, summarization)
├── tracing/      # Span-based tracing and OpenTelemetry instrumentation
├── storage/      # SQLite database and JSON trace files
├── analysis/     # Root cause analysis and failure categorization
├── api/          # FastAPI backend
├── frontend/     # React or Streamlit UI
├── evals/        # Evaluation datasets and regression tests
└── docker/       # Dockerfiles and compose configuration
```

---

## Viewing traces (local UI)

After you run the pipeline, traces are written to `storage/index.db` (SQLite index) and `storage/traces/<trace_id>.json` (full span data).

**Web dashboard** (stdlib only; binds on this machine only — tries IPv6 `::` first so `localhost` in the browser works more reliably):

```bash
python3 storage/trace_viewer.py
# optional: open browser tab automatically
python3 storage/trace_viewer.py --open
```

Open [http://127.0.0.1:8765/](http://127.0.0.1:8765/) for a table of all traces; click a row to open span timelines, latencies, and expandable JSON (including LLM prompts/responses where recorded). If the terminal shows an IPv6 line, [http://[::1]:8765/](http://[::1]:8765/) also works.

**If the browser says “connection failed”:** keep the terminal running (the server stops when you exit). Use **`http://127.0.0.1:8765/`** (not `https://`). If the port is busy, run `python3 storage/trace_viewer.py --port 8875`. You can force the bind address with `--bind 127.0.0.1` or `--bind 0.0.0.0`.

**Terminal table** (same SQLite index):

```bash
python3 storage/trace_viewer.py --table
```

Use `--port <n>` if `8765` is already in use.

---

## Viewing failure analyses (local UI)

After you run the analyzer, results are saved to `storage/analyses/<trace_id>.json` and indexed in the same SQLite file (`analyses` table).

```bash
python3 analysis/analyzer.py              # latest trace from index
python3 analysis/analyzer.py <trace_id>
```

**Web dashboard** (default port **8766** so it can run next to the trace viewer):

```bash
python3 storage/analysis_viewer.py
python3 storage/analysis_viewer.py --open
```

Open [http://127.0.0.1:8766/](http://127.0.0.1:8766/) for a table of analyses; click through for explanation, step scores, and evidence snippets. Same connection tips as the trace viewer (`http` not `https`, keep the process running, `--port` / `--bind` if needed).

**Terminal table:**

```bash
python3 storage/analysis_viewer.py --table
```