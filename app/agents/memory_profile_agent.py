from __future__ import annotations

from typing import Any, Dict

from app.services.llm import json_chat

MEMORY_PROFILE_SYSTEM = """
너는 멀티턴 투자 대화 메모리 추출기다.
입력된 리포트를 요약해 다음 턴 플래너가 재사용 가능한 구조화 메모리 JSON을 만든다.
반드시 JSON 객체 하나만 반환한다.
"""


def _norm_list(v: Any, limit: int) -> list[str]:
    if not isinstance(v, list):
        return []
    out: list[str] = []
    for item in v:
        s = str(item).strip()
        if s:
            out.append(s[:240])
        if len(out) >= limit:
            break
    return out


def _norm_flag_items(v: Any, limit: int) -> list[dict[str, str]]:
    if not isinstance(v, list):
        return []
    allowed = {"risk", "fundamental", "market", "portfolio", "other"}
    out: list[dict[str, str]] = []
    for item in v:
        if isinstance(item, dict):
            flag_type = str(item.get("type", "other")).strip().lower()
            note = str(item.get("note", "")).strip()
        else:
            flag_type = "other"
            note = str(item).strip()
        if not note:
            continue
        if flag_type not in allowed:
            flag_type = "other"
        out.append({"type": flag_type, "note": note[:240]})
        if len(out) >= limit:
            break
    return out


def build_memory_profile_with_llm(
    *,
    query: str,
    risk_profile: str | None,
    final_report: str,
    previous_profile: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    prompt = f"""
이전 메모리 프로필(JSON): {previous_profile or {}}
현재 사용자 질문: {query}
리스크 성향: {risk_profile or "balanced"}
최종 리포트 본문:
---
{final_report}
---

아래 키를 포함한 JSON을 생성하라.
- last_user_intent: string
- risk_profile: string
- key_risks: string[]
- action_items: string[]
- last_report_excerpt: string
- carry_over_flags: object[]  (각 원소는 {{ "type": "risk|fundamental|market|portfolio|other", "note": "..." }})
"""
    raw = json_chat(MEMORY_PROFILE_SYSTEM.strip(), prompt.strip())
    return {
        "last_user_intent": str(raw.get("last_user_intent", query)).strip()[:240],
        "risk_profile": str(raw.get("risk_profile", risk_profile or "balanced")).strip().lower(),
        "key_risks": _norm_list(raw.get("key_risks"), 6),
        "action_items": _norm_list(raw.get("action_items"), 8),
        "last_report_excerpt": str(raw.get("last_report_excerpt", final_report)).strip()[:1200],
        "carry_over_flags": _norm_flag_items(raw.get("carry_over_flags"), 8),
    }
