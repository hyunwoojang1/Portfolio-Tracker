"""Portfolio Tracker — Streamlit 진입점.

실행: streamlit run app.py
모든 개인 데이터는 data/portfolio.db (로컬, git 제외)에만 저장된다.
"""

import streamlit as st

from db.database import init_db

st.set_page_config(page_title="Portfolio Tracker", page_icon="📊", layout="wide")

init_db()

pages = st.navigation(
    [
        st.Page("views/dashboard.py", title="대시보드", icon="📊", default=True),
        st.Page("views/trades.py", title="거래 입력", icon="📒"),
        st.Page("views/import_csv.py", title="거래내역 가져오기", icon="📥"),
        st.Page("views/cash.py", title="현금 · 환전", icon="💱"),
        st.Page("views/dividends.py", title="배당금", icon="💰"),
        st.Page("views/performance.py", title="성과 분석", icon="📈"),
    ]
)
pages.run()
