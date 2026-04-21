import requests
import streamlit as st

st.set_page_config(page_title="InvestAI Agent", layout="wide")
st.title("📈 InvestAI Agent")
st.caption("시장/재무/리스크/포트폴리오/RAG를 결합한 투자분석 Copilot")

with st.sidebar:
    st.header("입력")
    api_base = st.text_input("FastAPI URL", value="http://127.0.0.1:8000")
    ticker = st.text_input("Ticker", value="005930.KS")
    risk_profile = st.selectbox("Risk Profile", ["conservative", "balanced", "aggressive"], index=1)

query = st.text_area("질문", value="삼성전자 지금 추가매수 괜찮을까? 시장과 리스크까지 함께 봐줘.", height=120)
portfolio_text = st.text_area(
    "포트폴리오 (종목, 비중 형식)",
    value="삼성전자, 35%\nTIGER 미국나스닥100, 25%\n현금, 20%\nSK하이닉스, 20%",
    height=150,
)

if st.button("분석 실행", use_container_width=True):
    with st.spinner("멀티 에이전트가 분석 중입니다..."):
        resp = requests.post(
            f"{api_base}/analyze",
            json={
                "query": query,
                "ticker": ticker,
                "portfolio_text": portfolio_text,
                "risk_profile": risk_profile,
            },
            timeout=120,
        )
        resp.raise_for_status()
        data = resp.json()

    st.subheader("최종 투자 브리프")
    st.write(data["final_report"])

    st.subheader("계획")
    st.json(data["plan"])

    st.subheader("Agent 결과")
    for section in data["sections"]:
        with st.expander(section["title"], expanded=False):
            st.write(section["summary"])
