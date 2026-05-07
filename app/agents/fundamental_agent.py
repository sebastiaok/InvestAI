from __future__ import annotations

from typing import Any

from app.agents.live_context import (
    citations_from_live_payload,
    format_live_json,
    live_data_fallback_banner,
    merge_agent_citations,
)
from app.prompts.system_prompts import FUNDAMENTAL_SYSTEM
from app.services.llm import chat, chat_with_tools
from app.services.market_tools import fetch_fundamental_data
from app.tools.investment_tools import extend_with_optional_mcp, get_fundamental_tools


def tool_trace_to_citations(traces: list[dict[str, Any]]) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for trace in traces:
        result = trace.get("result", {})
        if isinstance(result, dict):
            out.extend(citations_from_live_payload(result))
    return out


def run_fundamental_agent(query: str, ticker: str | None, rag_context: str = "") -> dict[str, Any]:
    fundamentals = fetch_fundamental_data(ticker)
    banner = live_data_fallback_banner(fundamentals)

    prefetch_citations = merge_agent_citations(citations_from_live_payload(fundamentals))

    prompt = f"""
질문: {query}

아래는 선조회한 재무·밸류에이션 지표(JSON)다. 고정 더미 재무 블록은 사용하지 않는다.
근거 작성 시 우선 아래 숫자/지표 출처(URL)를 명시하라.
{banner}

실시간·준실시간 기초재무 데이터:
{format_live_json(fundamentals)}

RAG 근거:
{rag_context}

필요하면 fundamental_lookup 도구로 동일 종목 재조회 가능하다.
"""
    tools = extend_with_optional_mcp(get_fundamental_tools())
    tool_result = chat_with_tools(FUNDAMENTAL_SYSTEM, prompt, tools=tools, max_steps=8)
    answer = tool_result.get("answer", "") or chat(FUNDAMENTAL_SYSTEM, prompt)
    traces = tool_result.get("tool_traces", [])
    citations = merge_agent_citations(prefetch_citations, tool_trace_to_citations(traces))
    return {"notes": answer, "citations": citations}
