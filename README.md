# LedgerLens

Backend service for an AI-powered transaction processing pipeline.

**Stage 0 — project skeleton.** Infrastructure and package layout are in place; business logic plugs in next.

## Stack

| Component | Role |
|-----------|------|
| FastAPI | HTTP API |
| PostgreSQL | Persistence |
| Celery + Redis | Async job queue |
| Ollama | Local LLM (optional profile, no paid APIs) |
| Docker Compose | Runtime |

## Quick Start

```bash
git clone <your-repo-url>
cd LedgerLens
docker compose up --build
```

API health check: `http://localhost:8000/health`

To include Ollama for later LLM stages:

```bash
docker compose --profile llm up --build
```

## Project Structure

```
app/
├── main.py           # FastAPI entrypoint + /health
├── config.py         # pydantic-settings loader
├── database.py       # SQLAlchemy engine + session
├── celery_app.py     # Celery configuration
├── api/              # HTTP route modules
├── models/           # SQLAlchemy ORM models
├── schemas/          # Pydantic request/response models
├── services/         # Cleaning, anomaly, LLM, summary
├── workers/          # Celery task definitions
└── utils/            # Shared helpers (logging)
alembic/              # Database migrations
```

## Local Development

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
cp .env.example .env

alembic upgrade head
uvicorn app.main:app --reload
celery -A app.celery_app worker --loglevel=info
```

## Environment Variables

See [.env.example](.env.example).

## Verify Worker

```bash
docker compose exec worker celery -A app.celery_app inspect ping
```

## License

MIT
