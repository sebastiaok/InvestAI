# InvestAI Agent 설계 문서 (구현 동기화판)

이 문서는 현재 `Final` 프로젝트의 실제 구현 상태를 기준으로 시스템 설계를 정리한다.

## 1. 설계 목표

- 질문 중심의 투자 분석 워크플로를 멀티에이전트로 분리해 일관된 브리프를 생성한다.
- 리서치 문서 기반 RAG를 실제 분석 단계(Planner 포함)에 주입한다.
- 도구 호출(`tool_choice=auto`)을 통해 정적 프롬프트 의존을 줄이고 최신 근거를 보강한다.
- 세션 기반 멀티턴 메모리를 지원해 대화 연속성과 재분석 생산성을 높인다.
- 입력 오류/LLM 오류를 구분해 API 소비자가 대응 가능한 에러 계약을 제공한다.

## 2. 실행 아키텍처

### 2.1 구성 요소

- API 레이어: `FastAPI` (`app/main.py`)
- 오케스트레이션: `LangGraph` (`app/graphs/investment_graph.py`)
- LLM/Tool 런타임: `OpenAI/AzureOpenAI + LangChain Tool`
- 문서 처리/RAG: `app/rag/*`, FAISS (`data/vector_store/faiss`)
- UI: `Streamlit` (`streamlit_app.py`)

### 2.2 상위 데이터 흐름

```mermaid
flowchart TD
    UI[Streamlit] -->|POST /ingest-docs (optional)| ING[Ingestion]
    UI -->|POST /analyze| API[FastAPI]
    API --> GRAPH[LangGraph App]
    GRAPH --> LLM[LLM + Tool Calling]
    GRAPH --> RAG[FAISS Retriever]
    GRAPH --> MEM[Checkpointer + Store]
    GRAPH --> API
    API --> UI
```

## 3. Agent Graph 설계

### 3.1 노드

- `memory_bootstrap`
- `planner`
- `rag`
- `market`
- `fundamental`
- `risk`
- `portfolio`
- `reviewer`
- `report`

### 3.2 라우팅 정책

- Entry: `memory_bootstrap -> planner`
- Planner 이후:
  - `tasks.rag or tasks.research == true`면 `rag` 선행
  - 아니면 활성화된 첫 specialist로 직행
- Specialist 간:
  - `next_specialist_after(...)`로 다음 활성 노드 결정
- 종단:
  - `portfolio -> reviewer -> report -> END`

### 3.3 핵심 상태(`AgentState`)

- 입력/컨텍스트:
  - `query`, `ticker`, `portfolio_text`, `risk_profile`
  - `session_id`, `turn_index`, `context_summary`, `memory_profile`, `contextual_query`
- 분석 산출:
  - `plan`
  - `rag_context`, `citations`
  - `market_notes`, `fundamental_notes`, `risk_notes`, `portfolio_notes`, `review_notes`
  - `final_report`

## 4. Tool Calling 설계

### 4.1 공통 런타임

`app/services/llm.py`의 `chat_with_tools`:

- OpenAI function-tool 스키마 변환
- 반복 호출 루프(`max_steps`)로 tool-call chain 수행
- 도구 인자 JSON 파싱 실패 시 `LLMJSONParseError(stage="tool_arguments")`
- LLM 호출 실패 시 `LLMInvocationError(subtype=...)`로 래핑

### 4.2 도구 목록

`app/tools/investment_tools.py`:

- `quote_lookup`
- `news_lookup`
- `fundamental_lookup`
- `portfolio_holdings`
- `rag_search`

추가로 역할별 묶음:

- `get_planner_tools()`
- `get_reviewer_tools()`
- `get_report_tools()`
- `extend_with_optional_mcp()` (환경설정 시 MCP 확장 도구 병합)

### 4.3 MCP 확장 포인트

`app/tools/mcp_tools.py`:

- 기본은 빈 리스트 반환 (기본 런타임 보호)
- `MCP_TOOLS_ENABLED=1`일 때 사용자 구현 로더를 통해 확장 가능

## 5. RAG 설계

### 5.1 입력 소스 및 포맷

- 리서치 저장 경로: `data/research`
- 지원 포맷: `md`, `txt`, `pdf`
  - PDF는 `pypdf.PdfReader`로 텍스트 추출

### 5.2 전처리/청킹

- `clean_text`: 제어문자/URL/공백 정규화
- `chunk_documents`:
  - 기본 `chunk_size=900`
  - 기본 `chunk_overlap=120`
- 메타데이터:
  - `source_id`, `source_path`, `doc_type`, `ticker`, `section`, `chunk_index`, `hash`, `ingested_at`

### 5.3 인덱스 전략

- 벡터스토어: FAISS (`faiss-cpu`)
- 저장 경로: `data/vector_store/faiss`
- `build_or_load_vector_store`로 lazy build/load
- 검색: `retrieve_for_query(query, ticker, k)` + ticker 후보 필터 fallback

## 6. 멀티턴 메모리 설계

### 6.1 저장소 구성

- Checkpointer: `MemorySaver`
- Store: `InMemoryStore`
- namespace: `("conversation", "investai")`

### 6.2 저장/조회 계약

- 저장 시점: `report_node` 완료 후
- 저장 필드:
  - `turn_index`
  - `last_query`
  - `last_report_summary`
  - `memory_profile`
  - `updated_at`
- API:
  - `GET /memory/{session_id}`
  - `reset_session_memory(session_id)`

### 6.3 구조화 메모리(`memory_profile`)

생성 경로:

1. `memory_profile_agent.build_memory_profile_with_llm(...)` 우선
2. 실패 시 `_extract_structured_memory(...)` 규칙 기반 fallback

스키마:

- `last_user_intent`
- `risk_profile`
- `key_risks[]`
- `action_items[]`
- `last_report_excerpt`
- `carry_over_flags[]` (typed)
  - `{type: risk|fundamental|market|portfolio|other, note: ...}`

### 6.4 플래너 보정

`planner_agent._apply_memory_flags(...)`:

- `carry_over_flags` typed 항목을 우선 해석
- legacy string flag도 하위호환
- 관련 task를 강제로 `true` 보정
- flag 존재 시 `research/rag`를 꺼두지 않음

## 7. API/스키마 설계

### 7.1 입력 검증 (`AnalyzeRequest`)

- `risk_profile` enum 강제
- `query`/`portfolio_text` 상호 규칙 검증
- 포트폴리오 형식 규칙 검증
- 멀티턴 필드:
  - `session_id`
  - `reset_memory`

### 7.2 응답 (`AnalyzeResponse`)

- `session_id`, `turn_index`
- `memory_summary`, `memory_profile`
- `plan`, `sections`, `final_report`, `citations`, `warnings`

### 7.3 에러 핸들러

- `LLMInvocationError` -> 403/429/503/502 분기
- `LLMJSONParseError` -> 422
- `RequestValidationError` -> 422
  - `jsonable_encoder(... custom_encoder={Exception: str})`로 직렬화 안전성 보장

## 8. 프롬프트/검증 루프 설계

- `advanced_prompting.py`
  - Few-shot
  - 인용 규칙
  - 자기검증 시스템 프롬프트
- `report_verify_agent.py`
  - 리포트 초안에 대해 JSON self-check 라운드(`max_rounds=2`)
  - 만족/심각도 기반 조기 종료

## 9. Streamlit UX 설계 (현재 반영)

- 메인 화면 중심 입력:
  - 질문(필수)
  - 포트폴리오(선택)
  - 리서치 문서 업로드(선택)
- 리서치 문서 업로드 시 분석 실행 전에 자동 `/ingest-docs`
- Chunk 설정 아래에
  - ingest 상태
  - 생성된 문서/청크 메타데이터
  - 질문 기반 RAG 검색 결과

## 10. 운영 이슈/제약

- AOAI Private Endpoint 경로가 맞지 않으면 403 (`permission_denied`)
- 인메모리 스토어는 프로세스 재시작 시 세션 메모리 유실
- FAISS 로컬 파일 기반이므로 동시 업데이트/배포 전략 별도 필요

## 11. 검증 전략

- 단위 테스트(`unittest`)로 핵심 계약 고정:
  - retriever 동작
  - RAG 포맷
  - memory bootstrap/reset
  - memory profile 정규화
  - carry-over typed flag 보정
- 런타임 smoke:
  - `/` health
  - `/analyze` validation path (422)
  - `/ingest-docs` pipeline

## 12. 확장 계획

- persistent store(redis/sql)로 세션 메모리 영속화
- reranker 도입으로 RAG 정밀도 향상
- tool trace를 기준으로 근거 신뢰도 점수 부여
- MCP 도구 로더 실제 구현 및 권한/타임아웃 관리

## 13. API 계약 상세

### 13.1 `/analyze` 요청 스키마

- `query: str`  
  - 최소 5자 이상 또는 `portfolio_text`가 유효 형식이어야 함.
- `ticker: str | null`  
  - 시세/재무 툴에게 힌트 제공, RAG 필터에도 사용 가능.
- `portfolio_text: str | null`  
  - `parse_portfolio_text`로 구조화, Portfolio Agent와 Risk Agent에 전달.
- `risk_profile: "conservative" | "balanced" | "aggressive"`
- `session_id: str | null`  
  - 없으면 서버에서 UUID 발급.
- `reset_memory: bool`  
  - true면 해당 `session_id`의 LangGraph 체크포인트 + Store 메모리 삭제 후 이번 턴부터 새로 쌓기.

### 13.2 `/analyze` 응답 스키마

- `session_id: str`
- `turn_index: int`
- `memory_summary: str`
- `memory_profile: dict`
  - `last_user_intent`, `risk_profile`, `key_risks`, `action_items`, `last_report_excerpt`, `carry_over_flags`.
- `plan: dict`
  - `objective`, `tasks`, `output_style`.
- `sections: AgentSection[]`
  - `title`, `summary`, `bullets`, `evidence`.
- `final_report: str`
- `citations: dict[str, Citation[]]`
- `warnings: str[]`

### 13.3 `/ingest-docs`

- 입력 `IngestDocumentsRequest`:
  - `documents: ResearchDocumentInput[]`
  - `chunk_size`, `chunk_overlap`
  - `save_to_research_dir`, `rebuild_index`
- 출력 `IngestDocumentsResponse`:
  - `input_documents`, `accepted_documents`, `generated_chunks`
  - `saved_files`, `chunk_previews`, `warnings`

### 13.4 `/memory/{session_id}`

- 입력: path param `session_id`
- 출력 `SessionMemoryResponse`:
  - `turn_index`, `updated_at`, `last_query`, `memory_summary`, `memory_profile`

## 14. UI 스크린 플로우

### 14.1 메인 화면

- 사이드바
  - FastAPI URL
  - Risk Profile
  - Conversation Session ID + 세션 메모리 초기화 버튼
- 메인 본문
  - 질문 입력(필수, 규칙 안내 문구 포함)
  - 포트폴리오 텍스트/파일 업로드(선택)
  - 리서치 문서 업로드 + Chunk 설정(선택)
  - Chunk 설정 아래:
    - 인제스트 결과/경고
    - 생성된 문서/청크 메타데이터
    - 질문 기반 RAG 검색 결과
  - 분석 실행 버튼

### 14.2 결과 영역

- Session/Turn 정보
- Session Memory Profile(JSON 뷰)
- 질문 원문
- 분석 결과(최종 브리프)
- Planner Plan
- Agent별 결과(expander)
- Citations(expander)
