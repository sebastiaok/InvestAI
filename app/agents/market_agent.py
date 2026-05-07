from __future__ import annotations

from typing import Any

from app.agents.live_context import (
    citations_from_live_payload,
    format_live_json,
    live_data_fallback_banner,
    merge_agent_citations,
)
from app.prompts.system_prompts import MARKET_SYSTEM
from app.services.llm import chat, chat_with_tools
from app.services.market_tools import fetch_news_data, fetch_quote_data
from app.tools.investment_tools import extend_with_optional_mcp, get_market_tools


def tool_trace_to_citations(traces: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for trace in traces:
        result = trace.get("result", {})
        if isinstance(result, dict):
            out.extend(citations_from_live_payload(result))
    return out


def run_market_agent(query: str, ticker: str | None, rag_context: str = "") -> dict[str, Any]:
    quote = fetch_quote_data(ticker)
    news = fetch_news_data(ticker)
    live_block = {"quote": quote, "news": news}
    banner = live_data_fallback_banner(quote, news)

    prefetch_citations = merge_agent_citations(
        citations_from_live_payload(quote),
        citations_from_live_payload(news),
    )

    prompt = f"""
질문: {query}

아래는 선조회한 시세·뉴스 원천 데이터(JSON)이다. 고정 더미 요약 블록은 사용하지 않는다.
근거 작성 시 우선 아래 필드와 뉴스 항목 title/url을 인용 가능한 형태로 명시하라.
{banner}

실시간·준실시간 시장 데이터:
{format_live_json(live_block)}

RAG 근거:
{rag_context}

필요하면 도구를 추가 호출하여 최신 시세·뉴스를 재확인할 수 있다.
"""
    tools = extend_with_optional_mcp(get_market_tools())
    tool_result = chat_with_tools(MARKET_SYSTEM, prompt, tools=tools, max_steps=8)
    answer = tool_result.get("answer", "") or chat(MARKET_SYSTEM, prompt)
    traces = tool_result.get("tool_traces", [])
    citations = merge_agent_citations(prefetch_citations, tool_trace_to_citations(traces))
    return {"notes": answer, "citations": citations}
