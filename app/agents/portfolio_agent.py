from __future__ import annotations

from typing import Any

from app.agents.live_context import format_live_json, merge_agent_citations
from app.prompts.system_prompts import PORTFOLIO_SYSTEM
from app.services.llm import chat, chat_with_tools
from app.services.market_tools import parse_portfolio_text
from app.tools.investment_tools import extend_with_optional_mcp, get_portfolio_tools


def _tool_trace_citations(traces: list[dict[str, Any]]) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for trace in traces:
        result = trace.get("result", {})
        if not isinstance(result, dict):
            continue
        source = str(result.get("source", ""))
        if source:
            rows.append(
                {
                    "source": source,
                    "url": str(result.get("url", "")),
                    "title": str(result.get("title", "portfolio")),
                }
            )
    return rows


def run_portfolio_agent(query: str, portfolio_text: str | None, rag_context: str = "") -> dict[str, Any]:
    holdings = parse_portfolio_text(portfolio_text)
    prefetch_citations = merge_agent_citations(
        [
            {
                "source": "user_portfolio_structure",
                "url": "",
                "title": f"lines={len(holdings)}",
            }
        ]
    )

    raw_portfolio = portfolio_text or ""

    prompt = f"""
질문: {query}

아래는 사용자 포트폴리오 텍스트에서 파싱한 구조화 보유내역이다(사용자 입력 기반).

원문 포트폴리오 텍스트(portfolio_holdings 도구 호출 시 동일 문자열을 portfolio_text 인자로 넣을 것):
---
{raw_portfolio if raw_portfolio.strip() else "(비어 있음)"}
---

구조화 보유내역(JSON):
{format_live_json(holdings)}

RAG 근거:
{rag_context}

portfolio_holdings 도구로 같은 텍스트를 재파싱·검증할 수 있다. 없는 종목 코드는 과장하지 말라.

집중도, 분산도, 리스크, 기존 메모와의 관계를 분석해라.
"""

    tools = extend_with_optional_mcp(get_portfolio_tools())
    tool_result = chat_with_tools(PORTFOLIO_SYSTEM, prompt, tools=tools, max_steps=6)
    answer = tool_result.get("answer", "") or chat(PORTFOLIO_SYSTEM, prompt)
    citations = merge_agent_citations(prefetch_citations, _tool_trace_citations(tool_result.get("tool_traces", [])))
    return {"notes": answer, "citations": citations}
