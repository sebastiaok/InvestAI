from __future__ import annotations

from app.prompts.advanced_prompting import REVIEWER_FEW_SHOT_KO
from app.prompts.system_prompts import REVIEWER_SYSTEM
from app.services.llm import chat, chat_with_tools
from app.tools.investment_tools import extend_with_optional_mcp, get_reviewer_tools


def run_reviewer_agent(
    market_notes: str, fundamental_notes: str, risk_notes: str, portfolio_notes: str, rag_context: str = ""
) -> str:
    prompt = f"""
{REVIEWER_FEW_SHOT_KO}

시장: {market_notes}
재무: {fundamental_notes}
리스크: {risk_notes}
포트폴리오: {portfolio_notes}
RAG 근거: {rag_context}

누락된 근거, 충돌, 과장 가능성을 검토하고 수정 포인트를 3~5개로 정리하라.
"""
    tools = extend_with_optional_mcp(get_reviewer_tools())
    tool_result = chat_with_tools(REVIEWER_SYSTEM, prompt, tools=tools, max_steps=8)
    draft = (tool_result.get("answer") or "").strip()
    return draft if draft else chat(REVIEWER_SYSTEM, prompt)
