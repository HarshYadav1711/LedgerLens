from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from app.models.enums import JobStatus


def test_health_returns_service_metadata(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["service"] == "LedgerLens"
    assert "version" in body


def test_upload_rejects_non_csv(client: TestClient) -> None:
    response = client.post(
        "/jobs/upload",
        files={"file": ("data.txt", b"a,b", "text/plain")},
    )
    assert response.status_code == 400
    assert "CSV" in response.json()["detail"]


def test_upload_rejects_missing_columns(client: TestClient) -> None:
    response = client.post(
        "/jobs/upload",
        files={"file": ("bad.csv", b"txn_id,date\n1,2024-01-01\n", "text/csv")},
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert "missing required columns" in detail.lower()
    assert "merchant" in detail


def test_status_returns_404_for_unknown_job(client: TestClient, mock_db_session: MagicMock) -> None:
    mock_db_session.get.return_value = None
    response = client.get("/jobs/99999/status")
    assert response.status_code == 404
    assert "not found" in response.json()["detail"].lower()


def test_results_returns_409_for_incomplete_job(client: TestClient, mock_db_session: MagicMock) -> None:
    job = MagicMock()
    job.id = 1
    job.status = JobStatus.processing
    mock_db_session.get.return_value = job

    response = client.get("/jobs/1/results")
    assert response.status_code == 409
    assert "not completed" in response.json()["detail"].lower()


def test_list_jobs_returns_empty_list(client: TestClient, mock_db_session: MagicMock) -> None:
    mock_db_session.query.return_value.order_by.return_value.all.return_value = []
    response = client.get("/jobs")
    assert response.status_code == 200
    assert response.json() == {"jobs": [], "total": 0}
