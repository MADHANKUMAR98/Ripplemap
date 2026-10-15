"""FastAPI backend service exposing RippleMap investigation and scoring capabilities."""

import dataclasses
import logging
from typing import Any, Optional
from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.config import config
from app.db import db_client
from app.graph_queries import get_selectable_infrastructure_nodes, validate_node_id
from app.investigation_agent import run_investigation_agent
from app.schema import AgentBriefing

logger = logging.getLogger(__name__)

app = FastAPI(
    title="RippleMap API",
    description="Infrastructure Intelligence & Cascading Consequence Analysis Engine",
    version="1.0.0",
)

# Configure CORS for local React/Vite development
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8501",  # Streamlit
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _serialize_value(val: Any) -> Any:
    """Recursively serializes Enums, dataclasses, and collections to JSON-safe types."""
    if hasattr(val, "value"):
        return val.value
    if dataclasses.is_dataclass(val):
        return _serialize_value(dataclasses.asdict(val))
    if isinstance(val, dict):
        return {k: _serialize_value(v) for k, v in val.items()}
    if isinstance(val, (list, tuple, set)):
        return [_serialize_value(i) for i in val]
    return val


# Request Models
class InvestigateRequest(BaseModel):
    source_id: str = Field(..., description="ID of source asset to investigate", json_schema_extra={"example": "SUB-001"})
    use_llm: bool = Field(default=True, description="Enable optional Groq natural-language synthesis")
    question: Optional[str] = Field(default=None, description="Optional inquiry question")


class QuestionRequest(BaseModel):
    source_id: str = Field(..., description="Context source asset ID", json_schema_extra={"example": "SUB-001"})
    question: str = Field(..., description="Inquiry question to evaluate", json_schema_extra={"example": "Why is this recovery plan ranked first?"})
    use_llm: bool = Field(default=True, description="Enable optional Groq explanation")



# -----------------------------------------------------------------------------
# Endpoints
# -----------------------------------------------------------------------------

@app.get("/api/health")
def get_health():
    """Health check endpoint validating FalkorDB graph connectivity and configuration."""
    try:
        is_healthy = db_client.is_healthy()
        nodes = db_client.query("MATCH (n) RETURN count(n)")[0][0] if is_healthy else 0
        rels = db_client.query("MATCH ()-[r]->() RETURN count(r)")[0][0] if is_healthy else 0
    except Exception as e:
        logger.warning(f"Health check database query failed: {e}")
        is_healthy = False
        nodes, rels = 0, 0

    return {
        "status": "healthy" if is_healthy else "degraded",
        "database_connected": is_healthy,
        "graph_name": config.graph_name,
        "host": config.host,
        "port": config.port,
        "node_count": nodes,
        "relationship_count": rels,
        "groq_configured": config.is_groq_configured,
        "groq_model": config.groq_model,
    }


@app.get("/api/sources")
def get_sources():
    """Returns the list of selectable physical infrastructure assets for simulation."""
    try:
        nodes = get_selectable_infrastructure_nodes(client=db_client)
        return {"sources": nodes, "total": len(nodes)}
    except Exception as e:
        logger.error(f"Failed to fetch selectable sources: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch infrastructure sources: {e}")


@app.get("/api/investigate")
def investigate_get(
    source_id: str = Query("SUB-001", description="Asset ID to investigate"),
    use_llm: bool = Query(True, description="Enable Groq narrative generation"),
    question: Optional[str] = Query(None, description="Optional question"),
):
    """Executes deterministic cascade investigation and recovery plan optimization (GET)."""
    return run_investigation_endpoint(source_id=source_id, use_llm=use_llm, question=question)


@app.post("/api/investigate")
def investigate_post(req: InvestigateRequest):
    """Executes deterministic cascade investigation and recovery plan optimization (POST)."""
    return run_investigation_endpoint(source_id=req.source_id, use_llm=req.use_llm, question=req.question)


def run_investigation_endpoint(source_id: str, use_llm: bool, question: Optional[str] = None):
    try:
        clean_id = validate_node_id(source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        briefing: AgentBriefing = run_investigation_agent(
            source_id=clean_id,
            question=question,
            persist_memory=False,  # Zero database mutation from dashboard use
            use_llm=use_llm,
            client=db_client,
        )
        return _serialize_value(briefing)
    except Exception as e:
        logger.error(f"Investigation execution error for '{source_id}': {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Investigation execution failed: {e}")


@app.post("/api/ask")
def ask_question(req: QuestionRequest):
    """Evaluates an evidence-grounded question with optional Groq natural-language explanation."""
    try:
        clean_id = validate_node_id(req.source_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    try:
        briefing: AgentBriefing = run_investigation_agent(
            source_id=clean_id,
            question=req.question,
            persist_memory=False,
            use_llm=req.use_llm,
            client=db_client,
        )
        if briefing.grounded_answers:
            return _serialize_value(briefing.grounded_answers[0])
        raise HTTPException(status_code=500, detail="No grounded answer produced.")
    except Exception as e:
        logger.error(f"Question answering error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to evaluate grounded question: {e}")
