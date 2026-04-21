from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class AnalyzeRequest(BaseModel):
    query: str = Field(..., description="예: 삼성전자 지금 추가매수 괜찮을까?")
    ticker: Optional[str] = Field(default=None, description="예: 005930.KS")
    portfolio_text: Optional[str] = Field(default=None, description="보유 종목/비중 텍스트")
    risk_profile: Optional[str] = Field(default="balanced")


class AgentSection(BaseModel):
    title: str
    summary: str
    bullets: List[str] = []
    evidence: List[str] = []


class AnalyzeResponse(BaseModel):
    plan: Dict[str, Any]
    sections: List[AgentSection]
    final_report: str
    warnings: List[str] = []
