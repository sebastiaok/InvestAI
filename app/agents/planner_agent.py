from __future__ import annotations

import json
import logging

from app.prompts.advanced_prompting import PLANNER_FEW_SHOT_KO
from app.prompts.system_prompts import PLANNER_SYSTEM
from app.services.llm import chat_with_tools, json_chat, parse_json_object_from_assistant_text
from app.tools.investment_tools import extend_with_optional_mcp, get_planner_tools

logger = logging.getLogger(__name__)


def _planner_profile_hint(risk_profile: str | None) -> str:
    profile = (risk_profile or "balanced").lower().strip()
    if profile == "conservative":
        return "보수형: 리스크 점검과 자본보전 항목의 우선순위를 높여 계획하라."
    if profile == "aggressive":
        return "공격형: 성장 모멘텀/업사이드 분석 비중을 높이고 리스크 허용 범위를 함께 명시하라."
    return "균형형: 수익 기회와 리스크 관리가 균형되도록 계획 우선순위를 배치하라."


def _apply_memory_flags(
    normalized_tasks: dict[str, bool], memory_profile: dict | None, portfolio_text: str | None
) -> dict[str, bool]:
    """이전 턴 carry_over_flags를 바탕으로 Planner task를 보정한다."""
    profile = memory_profile or {}
    flags_raw = profile.get("carry_over_flags", [])
    joined_parts: list[str] = []
    typed_flags: list[str] = []
    if isinstance(flags_raw, list):
        for item in flags_raw:
            if isinstance(item, dict):
                ftype = str(item.get("type", "")).strip().lower()
                note = str(item.get("note", "")).strip().lower()
                if ftype:
                    typed_flags.append(ftype)
                if note:
                    joined_parts.append(note)
            else:
                joined_parts.append(str(item).lower())
    joined = " ".join(joined_parts)

    if "risk" in typed_flags or any(k in joined for k in ("리스크", "변동성", "환율", "금리", "downside", "risk")):
        normalized_tasks["risk"] = True

    if "fundamental" in typed_flags or any(
        k in joined for k in ("실적", "밸류", "valuation", "per", "roe", "fundamental")
    ):
        normalized_tasks["fundamental"] = True

    if "market" in typed_flags or any(k in joined for k in ("뉴스", "모멘텀", "시장", "market", "news", "quote")):
        normalized_tasks["market"] = True

    if portfolio_text and (
        "portfolio" in typed_flags
        or any(k in joined for k in ("리밸런싱", "비중", "집중", "포트폴리오", "rebalanc", "portfolio"))
    ):
        normalized_tasks["portfolio"] = True

    # flag가 있으면 관련 근거 재탐색이 필요하므로 rag/research를 꺼두지 않음
    if joined_parts or typed_flags:
        normalized_tasks["research"] = True
        normalized_tasks["rag"] = True

    return normalized_tasks


def run_planner(
    query: str,
    ticker: str | None,
    portfolio_text: str | None,
    risk_profile: str | None,
    conversation_context: str = "",
    memory_profile: dict | None = None,
) -> dict:
    profile_hint = _planner_profile_hint(risk_profile)
    prompt = f"""
{PLANNER_FEW_SHOT_KO}

사용자 질문: {query}
티커: {ticker}
포트폴리오 정보: {portfolio_text}
리스크 성향: {risk_profile}
성향별 계획 지침: {profile_hint}
이전 대화 요약(있을 때만 참고): {conversation_context or "(없음)"}
구조화 메모리(이전 결론/리스크/액션): {memory_profile or {}}

아래 키를 포함한 Plan 흐름도를 작성해라.
- objective
- tasks: market, fundamental, risk, portfolio에 대한 true/false
- output_style

도구(rag_search, quote_lookup 등)로 근거를 보강한 뒤, 최종 메시지는 지정된 JSON 스키마만 출력한다.
"""
    tools = extend_with_optional_mcp(get_planner_tools())
    tool_rounds = chat_with_tools(PLANNER_SYSTEM, prompt, tools=tools, max_steps=12)
    text = (tool_rounds.get("answer") or "").strip()
    raw_plan: dict
    try:
        raw_plan = parse_json_object_from_assistant_text(text)
    except (ValueError, json.JSONDecodeError):
        logger.warning("Planner tool phase did not yield parseable JSON; falling back to json_chat")
        raw_plan = json_chat(
            PLANNER_SYSTEM,
            prompt
            + "\n\n이전 응답이 JSON만 포함하지 않았을 수 있다. 도구 결과를 반영했다면 그대로 반영하고, "
            "objective/tasks/output_style 키를 갖는 JSON 하나만 출력하라.",
        )
    tasks = raw_plan.get("tasks", {})
    normalized_tasks = {
        "market": bool(tasks.get("market", True)),
        "fundamental": bool(tasks.get("fundamental", True)),
        "risk": bool(tasks.get("risk", True)),
        "portfolio": bool(tasks.get("portfolio", bool(portfolio_text))),
        "research": bool(tasks.get("research", True)),
        "rag": bool(tasks.get("rag", tasks.get("research", True))),
    }
    normalized_tasks = _apply_memory_flags(normalized_tasks, memory_profile, portfolio_text)
    raw_plan["tasks"] = normalized_tasks
    return raw_plan
