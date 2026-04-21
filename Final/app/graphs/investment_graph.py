from __future__ import annotations

from typing import Any, Dict, Optional, TypedDict

from langgraph.graph import END, StateGraph

from app.agents.fundamental_agent import run_fundamental_agent
from app.agents.market_agent import run_market_agent
from app.agents.planner_agent import run_planner
from app.agents.portfolio_agent import run_portfolio_agent
from app.agents.report_agent import run_report_agent
from app.agents.reviewer_agent import run_reviewer_agent
from app.agents.risk_agent import run_risk_agent


class AgentState(TypedDict, total=False):
    query: str
    ticker: Optional[str]
    portfolio_text: Optional[str]
    risk_profile: Optional[str]
    plan: Dict[str, Any]
    market_notes: str
    fundamental_notes: str
    risk_notes: str
    portfolio_notes: str
    review_notes: str
    final_report: str


def planner_node(state: AgentState) -> AgentState:
    return {
        "plan": run_planner(
            state["query"],
            state.get("ticker"),
            state.get("portfolio_text"),
            state.get("risk_profile"),
        )
    }


def market_node(state: AgentState) -> AgentState:
    return {"market_notes": run_market_agent(state["query"], state.get("ticker"))}


def fundamental_node(state: AgentState) -> AgentState:
    return {"fundamental_notes": run_fundamental_agent(state["query"], state.get("ticker"))}


def risk_node(state: AgentState) -> AgentState:
    return {
        "risk_notes": run_risk_agent(
            state["query"],
            state.get("market_notes", ""),
            state.get("fundamental_notes", ""),
            state.get("risk_profile"),
        )
    }


def portfolio_node(state: AgentState) -> AgentState:
    return {"portfolio_notes": run_portfolio_agent(state["query"], state.get("portfolio_text"))}


def reviewer_node(state: AgentState) -> AgentState:
    return {
        "review_notes": run_reviewer_agent(
            state.get("market_notes", ""),
            state.get("fundamental_notes", ""),
            state.get("risk_notes", ""),
            state.get("portfolio_notes", ""),
        )
    }


def report_node(state: AgentState) -> AgentState:
    return {
        "final_report": run_report_agent(
            state["query"],
            state.get("risk_profile"),
            state.get("market_notes", ""),
            state.get("fundamental_notes", ""),
            state.get("risk_notes", ""),
            state.get("portfolio_notes", ""),
            state.get("review_notes", ""),
        )
    }


def build_graph():
    graph = StateGraph(AgentState)
    graph.add_node("planner", planner_node)
    graph.add_node("market", market_node)
    graph.add_node("fundamental", fundamental_node)
    graph.add_node("risk", risk_node)
    graph.add_node("portfolio", portfolio_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("report", report_node)

    graph.set_entry_point("planner")
    graph.add_edge("planner", "market")
    graph.add_edge("market", "fundamental")
    graph.add_edge("fundamental", "risk")
    graph.add_edge("risk", "portfolio")
    graph.add_edge("portfolio", "reviewer")
    graph.add_edge("reviewer", "report")
    graph.add_edge("report", END)
    return graph.compile()
