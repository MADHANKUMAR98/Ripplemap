"""Tests for RippleMap FastAPI backend endpoints."""

import pytest
from fastapi.testclient import TestClient
from app.api import app
from app.db import db_client


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


def test_api_health_endpoint(client):
    """Ensures /api/health returns valid status and live graph counts."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()

    assert data["status"] == "healthy"
    assert data["database_connected"] is True
    assert data["node_count"] == 59
    assert data["relationship_count"] == 135
    assert data["graph_name"] == "ripplemap"


def test_api_sources_endpoint(client):
    """Ensures /api/sources returns selectable physical infrastructure assets."""
    response = client.get("/api/sources")
    assert response.status_code == 200
    data = response.json()

    assert "sources" in data
    assert data["total"] >= 10

    ids = [s["id"] for s in data["sources"]]
    assert "SUB-001" in ids
    assert "HOSP-001" in ids
    assert "PUMP-001" in ids


def test_api_investigate_sub001_endpoint(client):
    """Ensures /api/investigate returns canonical cascade findings, scores, and plans."""
    response = client.get("/api/investigate?source_id=SUB-001&use_llm=false")
    assert response.status_code == 200
    data = response.json()

    assert data["source_node_id"] == "SUB-001"
    assert len(data["direct_findings"]) == 6
    assert len(data["downstream_findings"]) == 2
    assert len(data["ripple_scores"]) == 9
    assert data["ripple_scores"][0]["total_score"] == 85.0
    assert data["recommended_plan"]["plan_id"] == "PLAN-ACT-ACT-001"
    assert data["recommended_plan"]["composite_benefit_score"] == 242.0


def test_api_investigate_invalid_source_400(client):
    """Ensures invalid source ID format returns 400 Bad Request."""
    response = client.get("/api/investigate?source_id=INVALID;;--SELECT")
    assert response.status_code == 400


def test_api_ask_question_endpoint(client):
    """Ensures /api/ask evaluates grounded inquiries with supporting assets."""
    payload = {
        "source_id": "SUB-001",
        "question": "Why is this recovery plan ranked first?",
        "use_llm": False,
    }
    response = client.post("/api/ask", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert "question" in data
    assert "answer" in data
    assert data["evidence_sufficient"] is True


def test_api_zero_mutation_guarantee(client):
    """Confirms calling API endpoints causes zero mutations to graph baseline."""
    n_before = db_client.query("MATCH (n) RETURN count(n)")[0][0]
    r_before = db_client.query("MATCH ()-[r]->() RETURN count(r)")[0][0]

    _ = client.get("/api/sources")
    _ = client.get("/api/investigate?source_id=SUB-001&use_llm=false")

    n_after = db_client.query("MATCH (n) RETURN count(n)")[0][0]
    r_after = db_client.query("MATCH ()-[r]->() RETURN count(r)")[0][0]

    assert n_before == n_after == 59
    assert r_before == r_after == 135
