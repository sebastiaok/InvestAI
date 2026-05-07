from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

from app.prompts.advanced_prompting import REPORT_SELF_VERIFY_FEW_SHOT_KO, REPORT_SELF_VERIFY_SYSTEM_KO
from app.services.llm import json_chat

logger = logging.getLogger(__name__)

_CITATIONS_MAX_CHARS = 3200


def _compact_citations(citations: Optional[Dict[str, Any]]) -> str:
    if not citations:
        return "(출처 목록 없음)"
    raw = json.dumps(citations, ensure_ascii=False)
    if len(raw) <= _CITATIONS_MAX_CHARS:
        return raw
    return raw[: _CITATIONS_MAX_CHARS] + "\n...(truncated for prompt length)"


def refine_report_via_self_verify(
    draft_report: str,
    query: str,
    risk_profile: Optional[str],
    citations: Optional[Dict[str, Any]],
    *,
    max_rounds: int = 2,
) -> str:
    """초안에 대해 JSON 자기검증·수정 라운드를 최대 `max_rounds`번 수행하고 최종 본문을 반환한다."""
    current = (draft_report or "").strip()
    if not current:
        return ""

    citation_blob = _compact_citations(citations)

    for round_idx in range(max_rounds):
        user_prompt = f"""
{REPORT_SELF_VERIFY_FEW_SHOT_KO}

---- 입력 (라운드 {round_idx + 1}/{max_rounds}) ----
사용자 질문: {query}
리스크 성향: {risk_profile or "balanced"}

인용 가능한 출처 요약(dict JSON). 본문에 없는 새 URL·수치·날짜를 만들지 말 것:
{citation_blob}

---- 현재 초안 ----
{current}

위 초안만을 자기 검증하여 JSON 스키마에 맞게 응답하라 (마크다운 코드블록 금지).
"""
        try:
            data = json_chat(REPORT_SELF_VERIFY_SYSTEM_KO.strip(), user_prompt.strip())
        except Exception as exc:
            logger.warning("Self-verify json_chat failed round %s: %s", round_idx + 1, exc)
            return current

        revised = str(data.get("revised_final_report") or "").strip()
        if revised:
            current = revised

        satisfied = bool(data.get("satisfied"))
        severity = str(data.get("severity") or "none").lower()

        issues = data.get("issues_found")
        if isinstance(issues, list) and issues:
            logger.info(
                "Report self-verify r%s: severity=%s satisfied=%s issues=%s",
                round_idx + 1,
                severity,
                satisfied,
                issues[:5],
            )

        if severity == "none" or (satisfied and severity != "high"):
            return current

    return current
