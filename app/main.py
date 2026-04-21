from __future__ import annotations

import logging

from fastapi import FastAPI

from app.graphs.investment_graph import build_graph
from app.schemas import AnalyzeRequest, AnalyzeResponse, AgentSection
from app.services.market_tools import normalize_ticker_input

app = FastAPI(title="InvestAI Agent")
graph = build_graph()
logger = logging.getLogger(__name__)


@app.get("/")
def root():
    return {"message": "InvestAI Agent"}


@app.post("/analyze", response_model=AnalyzeResponse)
def analyze(payload: AnalyzeRequest):
    try:
        normalized_ticker = normalize_ticker_input(payload.ticker)
        state = graph.invoke(
            {
                "query": payload.query,
                "ticker": normalized_ticker,
                "portfolio_text": payload.portfolio_text,
            }
        )
        sections = [
            AgentSection(title="Market", summary=state.get("market_notes", "")),
            AgentSection(title="Fundamental", summary=state.get("fundamental_notes", "")),
            AgentSection(title="Risk", summary=state.get("risk_notes", "")),
            AgentSection(title="Portfolio", summary=state.get("portfolio_notes", "")),
            AgentSection(title="Review", summary=state.get("review_notes", "")),
        ]
        return AnalyzeResponse(
            plan=state.get("plan", {}),
            sections=sections,
            final_report=state.get("final_report", ""),
            warnings=[],
        )
    except Exception as exc:
        logger.exception("Analyze failed")
        warning = f"Analysis failed: {exc.__class__.__name__}. Check AOAI network/key configuration."
        fallback_sections = [
            AgentSection(title="Market", summary=""),
            AgentSection(title="Fundamental", summary=""),
            AgentSection(title="Risk", summary=""),
            AgentSection(title="Portfolio", summary=""),
            AgentSection(title="Review", summary=""),
        ]
        return AnalyzeResponse(
            plan={},
            sections=fallback_sections,
            final_report="분석 중 오류가 발생했습니다. 네트워크/키 설정을 확인한 뒤 다시 시도해주세요.",
            warnings=[warning],
        )
