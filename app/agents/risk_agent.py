from __future__ import annotations

from typing import Any, Optional

from app.agents.live_context import (
    citations_from_live_payload,
    format_live_json,
    live_data_fallback_banner,
    merge_agent_citations,
)
from app.prompts.system_prompts import RISK_SYSTEM
from app.services.llm import chat, chat_with_tools
from app.services.market_tools import fetch_fundamental_data, fetch_news_data, fetch_quote_data
from app.tools.investment_tools import extend_with_optional_mcp, get_risk_tools


def _tool_trace_citations(traces: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for trace in traces:
        result = trace.get("result", {})
        if isinstance(result, dict):
            out.extend(citations_from_live_payload(result))
    return out


def _risk_profile_guideline(risk_profile: str | None) -> str:
    profile = (risk_profile or "balanced").lower().strip()
    if profile == "conservative":
        return (
            "보수형 기준: 원금 보전과 변동성 최소화를 우선하라. "
            "최대 손실 가능 구간, 방어적 대응(현금 비중/분할매수/손절 기준)을 구체적으로 제시하라."
        )
    if profile == "aggressive":
        return (
            "공격형 기준: 변동성 허용을 전제로 상승 잠재력과 하방 리스크의 비대칭을 함께 제시하라. "
            "고위험 시나리오와 감내 조건(투자 기간/손실 허용 범위)을 명확히 제시하라."
        )
    return (
        "균형형 기준: 수익 기회와 리스크 관리의 균형을 맞춰라. "
        "기본 시나리오와 스트레스 시나리오를 함께 제시하고, 대응 우선순위를 정리하라."
    )


def run_risk_agent(
    query: str,
    market_notes: str,
    fundamental_notes: str,
    risk_profile: str | None,
    rag_context: str = "",
    ticker: Optional[str] = None,
) -> dict[str, Any]:
    guideline = _risk_profile_guideline(risk_profile)
    quote = fetch_quote_data(ticker)
    news = fetch_news_data(ticker, limit=6)
    fundamentals = fetch_fundamental_data(ticker)
    live_block = {"quote": quote, "news": news, "fundamentals": fundamentals}
    banner = live_data_fallback_banner(quote, news, fundamentals)

    prefetch_citations = merge_agent_citations(
        citations_from_live_payload(quote),
        citations_from_live_payload(news),
        citations_from_live_payload(fundamentals),
    )

    prompt = f"""
질문: {query}
선행 Agent 시장 메모: {market_notes}
선행 Agent 재무 메모: {fundamental_notes}
리스크 성향: {risk_profile}
성향별 가이드: {guideline}

아래는 리스크 검토를 위한 선조회 라이브 데이터(JSON)다. 하방·이벤트·반대 시나리오 작성 시 우선 인용하라.
{banner}

라이브 보조 데이터:
{format_live_json(live_block)}

RAG 근거:
{rag_context}

필요 시 quote_lookup, news_lookup, fundamental_lookup 도구로 재확인하라.
"""

    tools = extend_with_optional_mcp(get_risk_tools())
    tool_result = chat_with_tools(RISK_SYSTEM, prompt, tools=tools, max_steps=10)
    answer = tool_result.get("answer", "") or chat(RISK_SYSTEM, prompt)
    citations = merge_agent_citations(prefetch_citations, _tool_trace_citations(tool_result.get("tool_traces", [])))
    return {"notes": answer, "citations": citations}
