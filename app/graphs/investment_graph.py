from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph
from langgraph.store.memory import InMemoryStore

from app.agents.fundamental_agent import run_fundamental_agent
from app.agents.market_agent import run_market_agent
from app.agents.memory_profile_agent import build_memory_profile_with_llm
from app.agents.planner_agent import run_planner
from app.agents.portfolio_agent import run_portfolio_agent
from app.agents.report_agent import run_report_agent
from app.agents.report_verify_agent import refine_report_via_self_verify
from app.agents.reviewer_agent import run_reviewer_agent
from app.agents.risk_agent import run_risk_agent
from app.rag.retriever import format_rag_context, retrieve_for_query

logger = logging.getLogger(__name__)
CHECKPOINTER = MemorySaver()
MEMORY_STORE = InMemoryStore()
MEMORY_NAMESPACE = ("conversation", "investai")

# Planner tasks.market → … → tasks.portfolio 순으로 실행; 비활성 노드는 그래프에서 건너뜀.
TASK_ORDER = ["market", "fundamental", "risk", "portfolio"]

_ROUTE_TARGETS = {
    "market": "market",
    "fundamental": "fundamental",
    "risk": "risk",
    "portfolio": "portfolio",
    "reviewer": "reviewer",
}


def next_specialist_after(completed: Optional[str], state: AgentState) -> str:
    """Return the next enabled specialist after `completed`, or reviewer if none remain."""
    tasks = state.get("plan", {}).get("tasks", {})
    if completed is None:
        start_idx = 0
    else:
        try:
            start_idx = TASK_ORDER.index(completed) + 1
        except ValueError:
            start_idx = 0
    for i in range(start_idx, len(TASK_ORDER)):
        name = TASK_ORDER[i]
        if tasks.get(name, True):
            return name
    return "reviewer"


class AgentState(TypedDict, total=False):
    session_id: str
    turn_index: int
    context_summary: str
    memory_profile: Dict[str, Any]
    contextual_query: str
    query: str
    ticker: Optional[str]
    portfolio_text: Optional[str]
    risk_profile: Optional[str]
    plan: Dict[str, Any]
    retrieval_query: str
    rag_context: List[Dict[str, Any]]
    citations: Dict[str, List[Dict[str, str]]]
    market_notes: str
    fundamental_notes: str
    risk_notes: str
    portfolio_notes: str
    review_notes: str
    final_report: str


def _extract_structured_memory(report: str, risk_profile: str | None, query: str) -> dict[str, Any]:
    text = (report or "").strip()
    lines = [ln.strip("- ").strip() for ln in text.splitlines() if ln.strip()]
    risk_clues = [ln for ln in lines if "리스크" in ln][:5]
    action_clues = [ln for ln in lines if any(k in ln for k in ("비중", "분할", "손절", "현금", "추가 확인"))][:6]
    return {
        "last_user_intent": query[:240],
        "risk_profile": risk_profile or "balanced",
        "key_risks": risk_clues,
        "action_items": action_clues,
        "last_report_excerpt": text[:1200],
    }


def _query_for_turn(state: AgentState) -> str:
    return state.get("contextual_query") or state["query"]


def memory_bootstrap_node(state: AgentState) -> AgentState:
    session_id = state.get("session_id")
    if not session_id:
        return {"turn_index": 1, "context_summary": "", "contextual_query": state["query"]}

    item = MEMORY_STORE.get(MEMORY_NAMESPACE, session_id)
    if not item:
        return {"turn_index": 1, "context_summary": "", "contextual_query": state["query"]}

    payload = item.value or {}
    prev_turn = int(payload.get("turn_index", 0))
    prev_summary = str(payload.get("last_report_summary", "")).strip()
    memory_profile = payload.get("memory_profile", {}) if isinstance(payload.get("memory_profile"), dict) else {}
    contextual_query = state["query"]
    if prev_summary:
        contextual_query = f"{state['query']}\n\n[이전 대화 요약]\n{prev_summary}"
    return {
        "turn_index": prev_turn + 1,
        "context_summary": prev_summary,
        "contextual_query": contextual_query,
        "memory_profile": memory_profile,
    }


def planner_node(state: AgentState) -> AgentState:
    return {
        "plan": run_planner(
            _query_for_turn(state),
            state.get("ticker"),
            state.get("portfolio_text"),
            state.get("risk_profile"),
            state.get("context_summary", ""),
            state.get("memory_profile", {}),
        )
    }


def rag_node(state: AgentState) -> AgentState:
    retrieval_query = state.get("retrieval_query") or state["query"]
    rag_context = retrieve_for_query(
        query=retrieval_query,
        ticker=state.get("ticker"),
        k=4,
    )
    citations = dict(state.get("citations", {}))
    citations["rag"] = [
        {
            "source": "rag_document",
            "title": item.get("source_id", "unknown"),
            "url": item.get("source_path", ""),
        }
        for item in rag_context
    ]
    return {"retrieval_query": retrieval_query, "rag_context": rag_context, "citations": citations}


def _rag_text(state: AgentState) -> str:
    return format_rag_context(state.get("rag_context", []))


def market_node(state: AgentState) -> AgentState:
    if not state.get("plan", {}).get("tasks", {}).get("market", True):
        return {"market_notes": ""}
    rag_text = _rag_text(state)
    logger.info("Prompt injection [market] with RAG context:\n%s", rag_text)
    result = run_market_agent(_query_for_turn(state), state.get("ticker"), rag_text)
    citations = dict(state.get("citations", {}))
    citations["market"] = result.get("citations", [])
    return {"market_notes": result.get("notes", ""), "citations": citations}


def fundamental_node(state: AgentState) -> AgentState:
    if not state.get("plan", {}).get("tasks", {}).get("fundamental", True):
        return {"fundamental_notes": ""}
    rag_text = _rag_text(state)
    logger.info("Prompt injection [fundamental] with RAG context:\n%s", rag_text)
    result = run_fundamental_agent(_query_for_turn(state), state.get("ticker"), rag_text)
    citations = dict(state.get("citations", {}))
    citations["fundamental"] = result.get("citations", [])
    return {"fundamental_notes": result.get("notes", ""), "citations": citations}


def risk_node(state: AgentState) -> AgentState:
    if not state.get("plan", {}).get("tasks", {}).get("risk", True):
        return {"risk_notes": ""}
    rag_text = _rag_text(state)
    logger.info("Prompt injection [risk] with RAG context:\n%s", rag_text)
    result = run_risk_agent(
        _query_for_turn(state),
        state.get("market_notes", ""),
        state.get("fundamental_notes", ""),
        state.get("risk_profile"),
        rag_text,
        ticker=state.get("ticker"),
    )
    citations = dict(state.get("citations", {}))
    citations["risk"] = result.get("citations", [])
    return {"risk_notes": result.get("notes", ""), "citations": citations}


def portfolio_node(state: AgentState) -> AgentState:
    if not state.get("plan", {}).get("tasks", {}).get("portfolio", True):
        return {"portfolio_notes": ""}
    rag_text = _rag_text(state)
    logger.info("Prompt injection [portfolio] with RAG context:\n%s", rag_text)
    result = run_portfolio_agent(_query_for_turn(state), state.get("portfolio_text"), rag_text)
    citations = dict(state.get("citations", {}))
    citations["portfolio"] = result.get("citations", [])
    return {"portfolio_notes": result.get("notes", ""), "citations": citations}


def reviewer_node(state: AgentState) -> AgentState:
    rag_text = _rag_text(state)
    logger.info("Prompt injection [reviewer] with RAG context:\n%s", rag_text)
    return {
        "review_notes": run_reviewer_agent(
            state.get("market_notes", ""),
            state.get("fundamental_notes", ""),
            state.get("risk_notes", ""),
            state.get("portfolio_notes", ""),
            rag_text,
        )
    }


def report_node(state: AgentState) -> AgentState:
    rag_text = _rag_text(state)
    logger.info("Prompt injection [report] with RAG context:\n%s", rag_text)
    draft = run_report_agent(
        state["query"],
        state.get("risk_profile"),
        state.get("market_notes", ""),
        state.get("fundamental_notes", ""),
        state.get("risk_notes", ""),
        state.get("portfolio_notes", ""),
        state.get("review_notes", ""),
        rag_text,
    )
    final = refine_report_via_self_verify(
        draft_report=draft,
        query=_query_for_turn(state),
        risk_profile=state.get("risk_profile"),
        citations=state.get("citations"),
        max_rounds=2,
    )
    session_id = state.get("session_id")
    if session_id:
        try:
            memory_profile = build_memory_profile_with_llm(
                query=state.get("query", ""),
                risk_profile=state.get("risk_profile"),
                final_report=final,
                previous_profile=state.get("memory_profile", {}),
            )
        except Exception:
            memory_profile = _extract_structured_memory(final, state.get("risk_profile"), state.get("query", ""))
        MEMORY_STORE.put(
            MEMORY_NAMESPACE,
            session_id,
            {
                "turn_index": int(state.get("turn_index", 1)),
                "last_query": state.get("query", ""),
                "last_report_summary": final[:1200],
                "memory_profile": memory_profile,
                "updated_at": datetime.now(timezone.utc).isoformat(),
            },
        )
    return {"final_report": final}


def route_after_planner(state: AgentState) -> str:
    tasks = state.get("plan", {}).get("tasks", {})
    if tasks.get("rag") or tasks.get("research"):
        return "rag"
    return next_specialist_after(None, state)


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("memory", memory_bootstrap_node)
    graph.add_node("planner", planner_node)
    graph.add_node("rag", rag_node)
    graph.add_node("market", market_node)
    graph.add_node("fundamental", fundamental_node)
    graph.add_node("risk", risk_node)
    graph.add_node("portfolio", portfolio_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("report", report_node)

    graph.set_entry_point("memory")
    graph.add_edge("memory", "planner")
    planner_routes = {"rag": "rag", **_ROUTE_TARGETS}
    graph.add_conditional_edges(
        "planner",
        route_after_planner,
        planner_routes,
    )
    graph.add_conditional_edges(
        "rag",
        lambda s: next_specialist_after(None, s),
        _ROUTE_TARGETS,
    )
    graph.add_conditional_edges(
        "market",
        lambda s: next_specialist_after("market", s),
        _ROUTE_TARGETS,
    )
    graph.add_conditional_edges(
        "fundamental",
        lambda s: next_specialist_after("fundamental", s),
        _ROUTE_TARGETS,
    )
    graph.add_conditional_edges(
        "risk",
        lambda s: next_specialist_after("risk", s),
        _ROUTE_TARGETS,
    )
    graph.add_edge("portfolio", "reviewer")
    graph.add_edge("reviewer", "report")
    graph.add_edge("report", END)
    return graph.compile(checkpointer=CHECKPOINTER, store=MEMORY_STORE)


def reset_session_memory(session_id: str) -> None:
    CHECKPOINTER.delete_thread(session_id)
    MEMORY_STORE.delete(MEMORY_NAMESPACE, session_id)


def get_session_memory(session_id: str) -> dict[str, Any]:
    item = MEMORY_STORE.get(MEMORY_NAMESPACE, session_id)
    return item.value if item else {}
