"""선택적 MCP 기반 Tool 로딩 훅.

현재 Final 프로젝트는 Python 3.9·기본 requirements 기준으로 MCP 런타임(`mcp` 등) 미포함을 가정한다.
MCP Tool을 붙이려면:

1. `MCP_TOOLS_ENABLED=1` (또는 `true`) 환경변수 설정
2. (권장) Python 3.10+ 환경과 공식 `mcp` SDK 설치 후 아래 `load_mcp_stdio_tools` 함수 본문을 구현

이 모듈은 기본적으로 빈 리스트를 반환하여 기존 실행을 깨지 않는다.
"""

from __future__ import annotations

import os
from typing import List

from langchain_core.tools import BaseTool


def optional_mcp_tools() -> List[BaseTool]:
    if os.getenv("MCP_TOOLS_ENABLED", "").strip().lower() not in {"1", "true", "yes", "on"}:
        return []

    # 사용자 정의: MCP stdio/HTTP 클라이언트로 LangChain Tool 래핑 후 반환
    # from mcp import ClientSession ...
    return load_mcp_stdio_tools()


def load_mcp_stdio_tools() -> List[BaseTool]:
    """MCP 서버에서 Tool을 가져올 때 이 함수를 채운다. 미구현 시 빈 리스트."""
    return []
