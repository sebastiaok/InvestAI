# InvestAI Agent

실무형 투자분석 Copilot 예제입니다. 이 프로젝트는 투자 판단을 자동으로 대신하지 않고,
시장 조사, 뉴스 요약, 포트폴리오 리스크 점검, RAG 기반 근거 제시, 리포트 초안 작성을 수행합니다.

## 핵심 기능
- Multi-Agent 구조 (단일 Agent 아님)
- LangGraph 기반 오케스트레이션
- RAG 기반 내부 리서치 노트 검색
- Structured Output 기반 분석 결과 정리
- MCP/A2A 확장 고려 구조
- FastAPI + Streamlit 패키징

## Agent 구성
- Planner Agent: 사용자 질의를 작업 단위로 분해
- Market Agent: 시장/뉴스/가격 정보 수집
- Fundamental Agent: 재무/실적/밸류에이션 관점 분석
- Risk Agent: 리스크와 반대 시나리오 정리
- Portfolio Agent: 보유 종목과 포트폴리오 영향 평가
- Report Agent: 최종 투자 브리프 작성
- Reviewer Agent: 누락/과장/근거 부족 검토

## 프로젝트 구조
```text
Final/
├── app/
│   ├── agents/
│   │   ├── planner_agent.py
│   │   ├── market_agent.py
│   │   ├── fundamental_agent.py
│   │   ├── risk_agent.py
│   │   ├── portfolio_agent.py
│   │   ├── research_agent.py
│   │   ├── reviewer_agent.py
│   │   └── report_agent.py
│   ├── graphs/
│   │   └── investment_graph.py
│   ├── prompts/
│   │   └── system_prompts.py
│   ├── services/
│   │   ├── llm.py
│   │   ├── market_tools.py
│   │   └── retriever.py
│   ├── config.py
│   ├── main.py
│   └── schemas.py
├── docs/
├── scripts/
│   └── check_aoai.py
├── tests/
├── streamlit_app.py
└── README.md
```

## 프로세스 흐름
```mermaid
flowchart TD
    U[User] --> ST[Streamlit UI]
    ST -->|POST /analyze| API[FastAPI / app.main.analyze]

    API --> TRY{graph.invoke 성공?}
    TRY -->|Yes| G[LangGraph investment_graph]
    TRY -->|No| EH[Exception Handler]

    subgraph Agent_Orchestration[LangGraph Agent Orchestration]
        G --> P[Planner Agent]
        P --> M[Market Agent]
        M --> F[Fundamental Agent]
        F --> R[Risk Agent]
        R --> PO[Portfolio Agent]
        PO --> RS[Research Agent]
        RS --> RV[Reviewer Agent]
        RV --> RP[Report Agent]
    end

    P -. uses .-> LLM[services/llm.py]
    M -. uses .-> TOOL[services/market_tools.py]
    RS -. uses .-> RET[services/retriever.py]
    F -. uses .-> LLM
    R -. uses .-> LLM
    PO -. uses .-> LLM
    RV -. uses .-> LLM
    RP -. uses .-> LLM

    RP --> OK[AnalyzeResponse<br/>plan + sections + final_report + empty warnings]
    EH --> FAIL[Fallback AnalyzeResponse<br/>empty plan and sections + error final_report + warnings]

    OK --> ST
    FAIL --> ST
```

### 시퀀스 다이어그램
```mermaid
sequenceDiagram
    participant U as User
    participant ST as Streamlit
    participant API as FastAPI /analyze
    participant G as LangGraph
    participant LLM as LLM/Tools

    U->>ST: 질문/티커/포트폴리오 입력
    ST->>API: POST /analyze
    API->>G: graph.invoke(state)

    G->>LLM: Planner
    LLM-->>G: plan
    G->>LLM: Market
    LLM-->>G: market_notes
    G->>LLM: Fundamental
    LLM-->>G: fundamental_notes
    G->>LLM: Risk
    LLM-->>G: risk_notes
    G->>LLM: Portfolio
    LLM-->>G: portfolio_notes
    G->>LLM: Research(RAG)
    LLM-->>G: research_context
    G->>LLM: Reviewer
    LLM-->>G: review_notes
    G->>LLM: Report
    LLM-->>G: final_report
    G-->>API: aggregated state

    alt 정상 처리
        API-->>ST: 200 AnalyzeResponse(plan/sections/final_report)
    else 예외 발생
        API-->>ST: 200 Fallback AnalyzeResponse(warnings 포함)
    end
    ST-->>U: 결과 화면 렌더링
```

## 실행
```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload
streamlit run streamlit_app.py
```

### Azure OpenAI 연결 점검
```bash
python scripts/check_aoai.py
```

## 주의
- 본 프로젝트는 투자 자문 대행이 아니라 분석 보조 도구 예제입니다.
- 실시간 시세/뉴스 API는 실제 환경에 맞게 교체해야 합니다.
