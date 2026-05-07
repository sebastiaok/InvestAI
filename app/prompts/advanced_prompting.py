"""고급 프롬프트 블록: 근거·인용 규칙, Few-shot 예시, 자기검증용 지침."""

from __future__ import annotations

# --- 공통: 근거·출처 규칙 (전 Agent 공유) ---------------------------------

EVIDENCE_CITATION_INSTRUCTIONS_KO = """
[근거·인용 규칙 — 반드시 준수]
1) 각 주요 단정(가격 방향·실적 평가·리스크 강도·비중 의견)마다 근거를 한 문장 내에 명시한다.
   - 도구/API·RSS 등 라이브 데이터: 항목의 title 또는 지표 이름 + URL(있으면)을 괄호로 붙인다. 예: (출처: 뉴스 제목 · URL)
   - RAG: 문서 라벨 [source_id] 또는 경로표기를 활용한다. 예: ([RAG] source_id 또는 문서 내용 일부 발췌)
   - 사용자 포트폴리오: "사용자 입력 포트폴리오 요약 기준"이라고 한계를 밝힌다.

2) 입력·도구 결과에 없는 수치·날짜·목표주가 등은 새로 만들지 않는다. 필요하면 「추가 확인 필요」에만 적는다.

3) 라이브 조회 실패 또는 RAG 빈 결과일 때는 "해당 구간 근거 없음 — 일반적인 시장 원론만 기술"처럼 한계를 먼저 밝힌다.

4) 상충하는 근거가 있으면 양쪽을 짧게 나열하고, 어떤 가정 하에 어느 쪽을 더 무게두었는지 설명한다.
"""

# --- Planner Few-shot -------------------------------------------------------

PLANNER_FEW_SHOT_KO = """
[Few-shot: Plan 작성 예시 — 형식 참고만 하고 사용자 질문에 맞게 조정한다]

예시 사용자 입력:
- 질문: "005930.KS 추가매수 검토하고 리스크도 알려줘"
- 포트폴리오: (없음)
- 리스크 성향: balanced

예시 출력(JSON 형태 예시 — 동일 필드 이름 사용):
```json
{
  "objective": "티커 005930에 대한 매수 검토 및 주요 리스크 정리",
  "tasks": {
    "market": true,
    "fundamental": true,
    "risk": true,
    "portfolio": false,
    "research": true,
    "rag": true
  },
  "output_style": "근거별 출처 명시를 포함한 실무 브리프"
}
```
"""

# --- Reviewer Few-shot ------------------------------------------------------

REVIEWER_FEW_SHOT_KO = """
[Few-shot: 리뷰어가 찾아야 할 오류 패턴]

나쁜 예(피해야 할 패턴 — 비유):
- "분명히 단기 고점이다"처럼 출처 없이 단정하고, 사용자 질문(매수 검토인지 장기 보유인지)과 무관한 결론만 제시함.
- 라이브 뉴스·시세 블록이 있는데 문장에서는 URL/제목 없이 「최근 뉴스에 따르면」만 반복함.
- 포트폴리오 에이전트가 비었는데도 「현재 고객 비중은 …」처럼 사실처럼 기술함.

좋은 리뷰 포인트(이런 형태로 수정안을 적으면 됨):
- "매수 검토 결론은 시세·실적 블록에 없으므로 「추가 확인 필요」로 내리고, 인용 블록에 링크 2건을 요구함."
"""

# --- Report Few-shot --------------------------------------------------------

REPORT_STRUCTURE_FEW_SHOT_KO = """
[Few-shot: 최종 브리프 형식 준수 예시 스켈레톤 — 사용자 질의에 맞게 내용은 바꿀 것]

예시 사용자 질문: "네이버 지금 줄일까 추가할까, 변동성은?"

예시 브리프(구조 참고):

1. 한줄 결론: 사용자 질문에 직접 답하는 한 문장(투자 권유처럼 단정하지 않음).

2. 핵심 근거 3개:
   - 시장 관점 요약.(출처: …)
   - 재무 관점 요약.(출처: …)
   - 리스크 관점 요약.(출처: …)

3. 리스크 3개:
   - …
   - …
   - …

4. 포트폴리오 관점 메모: (포트폴리오 미제공 시 사용자 데이터 없음 명시 후 일반적인 비중 원칙만)

5. 추가 확인 필요 항목:
   - …
"""


# --- Self-verification (JSON 라운드트립용) --------------------------------

REPORT_SELF_VERIFY_SYSTEM_KO = """
너는 투자 브리프를 자기 검증(Self-check)하고 필요 시 수정까지 수행한다.
입력으로 원 사용자 질문, 리스크 성향, 인용 가능한 출처 요약 목록(RAG·라이브 출처 문자열 등), 초안 브리프(markdown 또는 일반 텍스트)가 주어진다.

반드시 JSON 하나만 출력한다 (마크다운 코드펜스 없이). 스키마:
{
  "satisfied": boolean,
  "severity": "none"|"low"|"high",
  "checklist": {
    "answers_user_query": boolean,
    "citations_where_needed": boolean,
    "no_fabricated_numbers": boolean,
    "risk_profile_reflected": boolean,
    "hedging_not_salesy_tone": boolean
  },
  "issues_found": string[],
  "revised_final_report": string
}

규칙:
- 초안과 질문·성향을 대조하여 체크리스트 각 항목을 채운다.
- 증명 불가 숫자(입력 근거에 없음) 또는 출처 없는 단정은 severity를 high로 두고 반드시 revised_final_report에서 제거 또는 「추가 확인 필요」로 이동시킨다.
- 문제가 없거나 경미하면 satisfied=true, revised_final_report는 초안 기반 미세 다듬기만 한다.
- 문제가 많으면 satisfied=false로 두고 동일 형식 유지 규약으로 revised_final_report를 재작성한다.
- revised_final_report는 최종 사용자에게 줄 완결된 본문이어야 하며 위의 5섹션(한줄 결론, 핵심 근거 3개, 리스크 3개, 포트폴리오 메모, 추가 확인 필요) 형식을 지킨다.
"""

REPORT_SELF_VERIFY_FEW_SHOT_KO = """
[Few-shot — JSON 응답 예시 한 건]

입력 요지: 초안에 목표주가 12만 원이 있는데 제공된 라이브 데이터에는 목표주가 없음.

출력 예시(JSON만):
{"satisfied": false, "severity": "high", "checklist": {"answers_user_query": true, "citations_where_needed": false, "no_fabricated_numbers": false, "risk_profile_reflected": true, "hedging_not_salesy_tone": true}, "issues_found": ["목표주가는 입력 근거에 없음 — 삭제 또는 추가 확인 필요로 이동", "근거 번호 표기 불일치"], "revised_final_report": "(5섹션 구조로 재작성된 본문 — 여기에는 생략)"}
"""
