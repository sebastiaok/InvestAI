from __future__ import annotations

import logging
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder

from app.errors import AppHTTPError, InputValidationAppError, LLMInvocationError, LLMJSONParseError
from app.graphs.investment_graph import build_graph, get_session_memory, reset_session_memory
from app.rag.ingestion import ingest_documents
from app.schemas import (
    AgentSection,
    AnalyzeRequest,
    AnalyzeResponse,
    IngestDocumentsRequest,
    IngestDocumentsResponse,
    QUERY_FALLBACK_WHEN_PORTFOLIO_ONLY,
    SessionMemoryResponse,
)
from app.services.market_tools import normalize_ticker_input

app = FastAPI(title="InvestAI Agent")
graph = build_graph()
logger = logging.getLogger(__name__)


def _error_payload(exc: AppHTTPError) -> dict[str, object]:
    if isinstance(exc, LLMJSONParseError):
        category = "llm_parse"
    elif isinstance(exc, LLMInvocationError):
        category = "llm"
    else:
        category = "input"
    body: dict[str, object] = {
        "success": False,
        "error_code": exc.error_code,
        "message": exc.message,
        "category": category,
    }
    if exc.detail:
        body["detail"] = exc.detail
    if isinstance(exc, LLMInvocationError):
        body["subtype"] = exc.subtype
        if exc.original_type:
            body["original_error_type"] = exc.original_type
    if isinstance(exc, LLMJSONParseError):
        if exc.snippet is not None:
            body["snippet"] = exc.snippet
        if exc.stage:
            body["stage"] = exc.stage
    return body


def _llm_invocation_status(exc: LLMInvocationError) -> int:
    if exc.subtype in ("authentication", "permission_denied"):
        return 403
    if exc.subtype == "rate_limit":
        return 429
    if exc.subtype == "connection":
        return 503
    return 502


@app.exception_handler(LLMInvocationError)
async def handle_llm_invocation(_request: Request, exc: LLMInvocationError) -> JSONResponse:
    logger.warning("LLM invocation failed: %s (%s)", exc.subtype, exc.message)
    return JSONResponse(status_code=_llm_invocation_status(exc), content=_error_payload(exc))


@app.exception_handler(LLMJSONParseError)
async def handle_llm_json_parse(_request: Request, exc: LLMJSONParseError) -> JSONResponse:
    logger.warning("LLM JSON parse error at stage=%s: %s", exc.stage, exc.message)
    return JSONResponse(status_code=exc.http_status, content=_error_payload(exc))


@app.exception_handler(InputValidationAppError)
async def handle_input_app_error(_request: Request, exc: InputValidationAppError) -> JSONResponse:
    return JSONResponse(status_code=exc.http_status, content=_error_payload(exc))


@app.exception_handler(RequestValidationError)
async def handle_request_validation(_request: Request, exc: RequestValidationError) -> JSONResponse:
    # Pydantic error context can include non-JSON-serializable objects (e.g., ValueError instance in ctx.error).
    safe_errors = jsonable_encoder(exc.errors(), custom_encoder={Exception: lambda e: str(e)})
    return JSONResponse(
        status_code=422,
        content={
            "success": False,
            "error_code": "REQUEST_VALIDATION_ERROR",
            "message": "요청 본문 또는 쿼리 파라미터 검증에 실패했습니다.",
            "category": "input",
            "errors": safe_errors,
        },
    )


@app.get("/")
def root():
    return {"message": "InvestAI Agent"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    session_id = (payload.session_id or str(uuid4())).strip()
    if payload.reset_memory:
        reset_session_memory(session_id)

    normalized_ticker = normalize_ticker_input(payload.ticker)
    effective_query = payload.query.strip() or QUERY_FALLBACK_WHEN_PORTFOLIO_ONLY
    state = graph.invoke(
        {
            "session_id": session_id,
            "query": effective_query,
            "ticker": normalized_ticker,
            "portfolio_text": payload.portfolio_text,
            "risk_profile": payload.risk_profile.value,
        },
        config={"configurable": {"thread_id": session_id}},
    )
    memory_info = get_session_memory(session_id)
    rag_evidence = [f"[{item.get('source_id', 'unknown')}] {item.get('source_path', '')}" for item in state.get("rag_context", [])]
    sections = [
        AgentSection(title="Market", summary=state.get("market_notes", ""), evidence=rag_evidence),
        AgentSection(title="Fundamental", summary=state.get("fundamental_notes", ""), evidence=rag_evidence),
        AgentSection(title="Risk", summary=state.get("risk_notes", ""), evidence=rag_evidence),
        AgentSection(title="Portfolio", summary=state.get("portfolio_notes", ""), evidence=rag_evidence),
        AgentSection(title="Review", summary=state.get("review_notes", ""), evidence=rag_evidence),
    ]
    return AnalyzeResponse(
        session_id=session_id,
        turn_index=int(state.get("turn_index", memory_info.get("turn_index", 1))),
        memory_summary=str(memory_info.get("last_report_summary", ""))[:400],
        memory_profile=memory_info.get("memory_profile", {}),
        plan=state.get("plan", {}),
        sections=sections,
        final_report=state.get("final_report", ""),
        citations=state.get("citations", {}),
        warnings=[],
    )


@app.get("/memory/{session_id}", response_model=SessionMemoryResponse)
def get_memory(session_id: str):
    info = get_session_memory(session_id.strip())
    return SessionMemoryResponse(
        session_id=session_id.strip(),
        turn_index=int(info.get("turn_index", 0)),
        updated_at=str(info.get("updated_at", "")),
        last_query=str(info.get("last_query", "")),
        memory_summary=str(info.get("last_report_summary", ""))[:600],
        memory_profile=info.get("memory_profile", {}),
    )


@app.post("/ingest-docs", response_model=IngestDocumentsResponse)
def ingest_docs(payload: IngestDocumentsRequest):
    result = ingest_documents(
        inputs=[item.model_dump() for item in payload.documents],
        chunk_size=payload.chunk_size,
        chunk_overlap=payload.chunk_overlap,
        save_to_research_dir=payload.save_to_research_dir,
        rebuild_index=payload.rebuild_index,
    )
    return IngestDocumentsResponse(**result)
