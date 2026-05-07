from __future__ import annotations

import re
from enum import Enum
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class RiskProfile(str, Enum):
    conservative = "conservative"
    balanced = "balanced"
    aggressive = "aggressive"


QUERY_MIN_CHARS = 5
# 짧은 다줄+비중 예시(한글 3줄)도 통과하도록 현실적인 하한
PORTFOLIO_MIN_CHARS = 22

# 비중 기호 또는 퍼센트 패턴 (ASCII/전각)
_PORTFOLIO_PERCENT_RE = re.compile(r"\d(?:[\d,.]*)\s*[%％]")
# 흔한 티커 형태 (예: 005930.KS, AAPL, TSLA)
_PORTFOLIO_TICKER_HINT_RE = re.compile(
    r"(?:^|[\s,;])(\d{6}\.[A-Z]{2}|(?<![a-z])[A-Za-z]{1,5}\.[A-Za-z]{1,4})\b",
)
QUERY_FALLBACK_WHEN_PORTFOLIO_ONLY = (
    "제공된 포트폴리오를 기준으로 비중·리스크 진단 및 개선 제안을 분석해주세요."
)


def _validate_portfolio_format(text: str) -> None:
    """종목명·비중 등 구조가 있는 포트폴리오 텍스트인지 검증 (비었을 때 호출 안 함)."""
    if len(text) < PORTFOLIO_MIN_CHARS:
        raise ValueError(
            f"portfolio_text는 최소 {PORTFOLIO_MIN_CHARS}자 이상으로 종목·비중 정보를 적어 주세요."
        )
    if _PORTFOLIO_PERCENT_RE.search(text):
        return
    lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
    substantive = [ln for ln in lines if any(ch.isdigit() for ch in ln)]
    if len(lines) >= 2 and len(substantive) >= 2:
        return
    if _PORTFOLIO_TICKER_HINT_RE.search(text) and re.search(r"\d", text):
        return
    comma_like = len(re.findall(r"[,，]", text))
    if comma_like >= 2 and len(text) >= PORTFOLIO_MIN_CHARS and re.search(r"\d", text):
        return
    raise ValueError(
        "portfolio_text 형식: 줄바꿈으로 종목별 구분 또는 '종목, 비중%' 포함, "
        "또는 티커(예: 005930.KS)·숫자(비중/수량)가 함께 있어야 합니다."
    )


class AnalyzeRequest(BaseModel):
    query: str = Field(
        default="",
        description="분석 질문. 비워도 되며 이 경우 포트폴리오 텍스트로 최소 입력을 충족해야 합니다.",
    )
    ticker: Optional[str] = Field(default=None, description="예: 005930.KS")
    portfolio_text: Optional[str] = Field(default=None, description="보유 종목/비중 텍스트")
    risk_profile: RiskProfile = Field(
        default=RiskProfile.balanced,
        description="위험 성향 — conservative | balanced | aggressive",
    )
    session_id: Optional[str] = Field(
        default=None,
        description="멀티턴 대화 세션 ID. 같은 값을 보내면 이전 턴 맥락을 이어서 분석합니다.",
    )
    reset_memory: bool = Field(
        default=False,
        description="true면 해당 session_id의 체크포인트/요약 메모리를 초기화하고 현재 턴부터 다시 시작합니다.",
    )

    @field_validator("risk_profile", mode="before")
    @classmethod
    def risk_profile_coerce(cls, v: Union[str, RiskProfile, None]) -> RiskProfile:
        if v is None:
            return RiskProfile.balanced
        if isinstance(v, RiskProfile):
            return v
        if isinstance(v, str):
            try:
                return RiskProfile(v.strip().lower())
            except ValueError:
                allowed = ", ".join(e.value for e in RiskProfile)
                raise ValueError(f"risk_profile는 다음 중 하나여야 합니다: {allowed}") from None
        raise ValueError("risk_profile는 문자열 또는 conservative/balanced/aggressive 값만 허용됩니다")

    @field_validator("query")
    @classmethod
    def strip_query(cls, v: Optional[str]) -> str:
        return (v or "").strip()

    @field_validator("portfolio_text")
    @classmethod
    def normalize_portfolio_text(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        s = v.strip()
        return s or None

    @field_validator("ticker")
    @classmethod
    def strip_optional_ticker(cls, v: Optional[str]) -> Optional[str]:
        if not v:
            return None
        s = v.strip()
        return s or None

    @model_validator(mode="after")
    def mutual_query_portfolio_rules(self) -> AnalyzeRequest:
        q = self.query
        p = self.portfolio_text
        query_ok = len(q) >= QUERY_MIN_CHARS

        if p is not None:
            _validate_portfolio_format(p)

        if query_ok:
            return self

        if p is None:
            raise ValueError(
                f"query는 최소 {QUERY_MIN_CHARS}자 이상이거나 portfolio_text가 최소 규격을 충족해야 합니다."
            )

        # portfolio-only 또는 짧은 질문 보조: 형식 검증 통과 상태
        return self


class AgentSection(BaseModel):
    title: str
    summary: str
    bullets: List[str] = []
    evidence: List[str] = []


class Citation(BaseModel):
    source: str
    url: str = ""
    title: str = ""


class AnalyzeResponse(BaseModel):
    session_id: str = ""
    turn_index: int = 1
    memory_summary: str = ""
    memory_profile: Dict[str, Any] = {}
    plan: Dict[str, Any]
    sections: List[AgentSection]
    final_report: str
    citations: Dict[str, List[Citation]] = {}
    warnings: List[str] = []


class ResearchDocumentInput(BaseModel):
    filename: str
    content: str
    doc_type: Optional[str] = "research_note"
    ticker: Optional[str] = "UNKNOWN"
    section: Optional[str] = "body"

    @field_validator("filename")
    @classmethod
    def filename_nonempty(cls, v: str) -> str:
        s = (v or "").strip()
        if not s:
            raise ValueError("filename은 비어 있을 수 없습니다")
        return s

    @field_validator("content")
    @classmethod
    def content_nonempty(cls, v: str) -> str:
        if not (v or "").strip():
            raise ValueError("content는 비어 있거나 공백만일 수 없습니다")
        return v


class IngestDocumentsRequest(BaseModel):
    documents: List[ResearchDocumentInput] = Field(..., min_length=1)
    chunk_size: int = 900
    chunk_overlap: int = 120
    save_to_research_dir: bool = True
    rebuild_index: bool = True

    @model_validator(mode="after")
    def chunks_consistent(self) -> IngestDocumentsRequest:
        if self.chunk_size < 120:
            raise ValueError("chunk_size는 최소 120 이상이어야 합니다")
        if self.chunk_overlap < 0 or self.chunk_overlap >= self.chunk_size:
            raise ValueError("chunk_overlap는 0 이상이며 chunk_size보다 작아야 합니다")
        return self


class ChunkPreview(BaseModel):
    source_id: str
    ticker: str
    doc_type: str
    chunk_index: int
    hash: str
    text_preview: str


class IngestDocumentsResponse(BaseModel):
    input_documents: int
    accepted_documents: int
    generated_chunks: int
    saved_files: List[str] = []
    chunk_previews: List[ChunkPreview] = []
    warnings: List[str] = []


class SessionMemoryResponse(BaseModel):
    session_id: str
    turn_index: int = 0
    updated_at: str = ""
    last_query: str = ""
    memory_summary: str = ""
    memory_profile: Dict[str, Any] = {}
