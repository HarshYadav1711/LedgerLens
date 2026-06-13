# LedgerLens

LedgerLens is an internal transaction processing service. It accepts CSV uploads of bank transactions, runs them through a deterministic cleaning and anomaly-detection pipeline, enriches missing categories via a local LLM, and produces a structured spending summary. Processing is fully asynchronous — the API returns a job ID immediately and clients poll for completion.

## Stack

| Component | Role |
|-----------|------|
| FastAPI | HTTP API |
| PostgreSQL | Job, transaction, and summary persistence |
| Celery + Redis | Async job queue and worker dispatch |
| Ollama | Local LLM for category classification and narrative summary |
| Docker Compose | Runtime orchestration |

No external paid APIs. The LLM runs locally through Ollama.

## Prerequisites

- Docker and Docker Compose v2
- ~4 GB free disk space (Ollama model download on first run)
- `curl` for the examples below

## Setup

```bash
git clone <repository-url>
cd LedgerLens
docker compose up --build
```

First startup pulls the `llama3.2` model into Ollama (~2 GB). The worker starts only after the model is available.

Confirm the API is ready:

```bash
curl http://localhost:8000/health
```

Expected response:

```json
{"status":"ok"}
```

Interactive API docs: `http://localhost:8000/docs`

### Environment variables

Defaults are in [`.env.example`](.env.example). Docker Compose injects these automatically. For local development without Docker, copy the file:

```bash
cp .env.example .env
```

Key variables:

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | `postgresql://ledgerlens:ledgerlens@postgres:5432/ledgerlens` | PostgreSQL connection |
| `REDIS_URL` | `redis://redis:6379/0` | Celery broker |
| `OLLAMA_BASE_URL` | `http://ollama:11434` | Ollama API endpoint |
| `OLLAMA_MODEL` | `llama3.2` | Model for classification and summary |
| `LLM_BATCH_SIZE` | `25` | Transactions per classification request |
| `LLM_MAX_RETRIES` | `3` | Retry attempts for failed LLM calls |

### Local development (without Docker)

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Start PostgreSQL, Redis, and Ollama separately, then:
alembic upgrade head
uvicorn app.main:app --reload --port 8000
celery -A app.celery_app worker --loglevel=info
```

## API reference

### `GET /health`

Liveness check.

```bash
curl http://localhost:8000/health
```

### `POST /jobs/upload`

Upload a CSV file. Validates structure, creates a `pending` job, enqueues background processing, and returns immediately with HTTP 202.

```bash
curl -X POST http://localhost:8000/jobs/upload \
  -F "file=@sample_transactions.csv"
```

Response:

```json
{
  "job_id": 1,
  "status": "pending",
  "message": "Job accepted for processing"
}
```

Required CSV columns: `txn_id`, `date`, `merchant`, `amount`, `currency`, `status`, `category`, `account_id`. Optional: `notes`.

### `GET /jobs/{job_id}/status`

Poll job progress. When `status` is `completed`, the response includes a compact summary.

```bash
curl http://localhost:8000/jobs/1/status
```

Response (completed):

```json
{
  "job_id": 1,
  "status": "completed",
  "filename": "sample_transactions.csv",
  "row_count_raw": 10,
  "row_count_clean": 9,
  "created_at": "2026-06-14T10:00:00Z",
  "completed_at": "2026-06-14T10:00:45Z",
  "error_message": null,
  "summary": {
    "total_spend_inr": 58469.0,
    "total_spend_usd": 284.99,
    "top_merchants": [
      {"merchant": "Unknown Merchant", "total_amount": 50000.0}
    ],
    "anomaly_count": 3,
    "narrative": "Spending is concentrated in a few merchants with several anomalies flagged.",
    "risk_level": "medium"
  }
}
```

### `GET /jobs/{job_id}/results`

Full structured output for a completed job. Returns 409 if the job is not yet completed.

```bash
curl http://localhost:8000/jobs/1/results
```

Response includes:

- `transactions` — all cleaned rows with anomaly flags and LLM enrichment
- `anomalies` — subset where `is_anomaly` is true
- `category_breakdown` — per-category count and total spend
- `top_merchants` — top 3 merchants by total amount (computed deterministically)
- `summary` — stored narrative, risk level, and spend totals

### `GET /jobs`

List all jobs, newest first. Optional status filter.

```bash
curl http://localhost:8000/jobs
curl "http://localhost:8000/jobs?status=completed"
curl "http://localhost:8000/jobs?status=pending"
```

Valid filter values: `pending`, `processing`, `completed`, `failed`.

## Architecture

```
HTTP Client
    |
    v
FastAPI (api) -----> PostgreSQL
    |                     ^
    | enqueue             | read/write
    v                     |
Redis (broker)            |
    |                     |
    v                     |
Celery Worker ------------+
    |
    v
Ollama (local LLM)
```

Source diagram: [`docs/architecture.drawio`](docs/architecture.drawio) — open in [draw.io](https://app.diagrams.net/) or the VS Code Draw.io extension.

### Draw.io diagram guidance

The diagram should show six components and five data flows:

1. **HTTP client** sends requests to **FastAPI**
2. **FastAPI** enqueues tasks to **Redis** on upload
3. **FastAPI** reads job status and results from **PostgreSQL**
4. **Celery worker** dequeues from **Redis**
5. **Celery worker** reads/writes **PostgreSQL** during processing
6. **Celery worker** calls **Ollama** for batched classification and narrative summary

Label the worker pipeline stages: Clean, Anomaly Detect, Batch Classify, Narrative Summary. Keep the layout left-to-right: client, API, queue, worker, with PostgreSQL below the API and Ollama below the worker.

## Request lifecycle

1. **Upload.** Client sends a CSV to `POST /jobs/upload`. The API validates the file structure, counts raw rows, creates a `Job` row with `status=pending`, stores the file on disk, and enqueues a Celery task. The response returns `job_id` immediately. No CSV processing happens in the request thread.

2. **Processing.** The worker picks up the task, sets `status=processing`, and runs four stages in order:
   - **Clean** — normalize dates to ISO 8601, strip currency symbols, uppercase status, fill missing categories with `Uncategorised`, remove exact duplicate rows
   - **Anomaly detect** — flag amounts exceeding 3x the account median; flag USD transactions with domestic-only merchants (Swiggy, Ola, IRCTC, etc.)
   - **Batch classify** — send uncategorised rows to Ollama in batches of up to 25; assign one of eight categories per row
   - **Summary** — one Ollama call for narrative and risk level; deterministic fallback if the call fails

3. **Persist.** The worker writes all transactions and a `JobSummary` row to PostgreSQL, sets `row_count_clean`, and marks the job `completed`.

4. **Poll.** Client calls `GET /jobs/{job_id}/status` until `status` is `completed` or `failed`.

5. **Retrieve.** Client calls `GET /jobs/{job_id}/results` for the full output.

## Retry behavior

LLM calls retry up to 3 times with exponential backoff (2s, 4s, 8s by default). Retry configuration is controlled by `LLM_MAX_RETRIES` and `LLM_RETRY_BASE_DELAY`.

If a classification batch fails after all retries, affected rows are marked `llm_failed=true` and the error is stored in `llm_raw_response`. The job continues processing remaining batches.

Summary generation is best-effort. If the LLM call fails, the worker falls back to a deterministic narrative built from computed aggregates. The job still completes.

Fatal errors (invalid file on disk, database failure) set `status=failed` with `error_message` populated.

## Scaling bottlenecks and trade-offs

| Bottleneck | Impact | Mitigation |
|------------|--------|------------|
| Ollama inference | Single-node LLM is the slowest stage; classification and summary are sequential per job | Run multiple Celery workers for parallel jobs; scale Ollama with a GPU or a dedicated inference host |
| Worker concurrency | Default concurrency is 2 per worker container | Increase `--concurrency` or add worker replicas; each job is independent |
| PostgreSQL writes | Large CSVs produce bulk inserts at end of pipeline | Batch inserts or COPY for very large files; current design targets typical statement volumes |
| Redis | Single broker instance | Replace with Redis Cluster or a managed broker for HA |
| File storage | Uploads stored on a local Docker volume | Move to object storage (S3, MinIO) for multi-node workers |
| No authentication | Any client can upload and read jobs | Add API key or mTLS at the gateway layer before production deployment |

The service is designed for internal use behind a trusted network boundary. Horizontal scaling of the API layer is straightforward — it is stateless. The worker and Ollama layers are the primary scaling constraints.

## Limitations

- CSV only. No JSON, Excel, or API-based ingestion.
- Single LLM provider (Ollama). No model routing or fallback across providers.
- Anomaly rules are deterministic heuristics, not statistical models.
- Category classification accuracy depends on the local model and prompt quality.
- No job cancellation or reprocessing endpoint.
- No pagination on `GET /jobs` or `GET /jobs/{id}/results`.
- Upload files are stored on local disk, not replicated.

## Project structure

```
app/
├── api/              # HTTP routes
├── models/           # SQLAlchemy ORM (Job, Transaction, JobSummary)
├── schemas/          # Pydantic response models
├── services/         # Cleaning, anomaly, classification, LLM, aggregates, results
├── workers/          # Celery task definitions
├── config.py         # Settings loader
├── database.py       # Engine and session
├── celery_app.py     # Celery configuration
└── main.py           # FastAPI entrypoint
alembic/              # Database migrations
docs/                 # Architecture diagram
sample_transactions.csv
```

## Technical review video

A 3-minute walkthrough should cover:

1. **Problem and scope** (20s) — what LedgerLens does: CSV in, cleaned transactions and summary out
2. **Architecture** (40s) — show the draw.io diagram; explain why processing is async and why Ollama runs locally
3. **Live demo** (60s) — `docker compose up`, upload `sample_transactions.csv`, poll status, fetch results; point out anomalies and category breakdown
4. **Pipeline detail** (40s) — walk through the four worker stages; mention batch LLM calls and retry behavior
5. **Trade-offs** (20s) — Ollama as the bottleneck, no auth by design, what you would add for production

Keep the demo focused on the API responses, not the code. Show one anomaly row and explain why it was flagged.

## License

MIT
