"""대시보드: 총 평가액, 현금 잔고, 보유 종목, 자산배분 차트."""

import pandas as pd
import plotly.express as px
import streamlit as st

from core.portfolio import cash_balances, positions
from core.prices import close_history, last_usdkrw, sector_of, to_yf_symbol
from db.database import get_cash_flows, get_dividends, get_trades

ASSET_TYPE_LABELS = {"stock": "주식", "etf": "ETF", "crypto": "암호화폐"}

st.title("📊 대시보드")

trades = get_trades()
cash_flows = get_cash_flows()
dividends = get_dividends()

if trades.empty and cash_flows.empty:
    st.info("아직 데이터가 없습니다. **거래 입력** 또는 **현금 · 환전** 메뉴에서 시작하세요.")
    st.stop()

try:
    fx_now = last_usdkrw()
except RuntimeError as err:
    st.error(str(err))
    st.stop()

base = st.sidebar.radio("표시 통화", ["KRW", "USD"], horizontal=True)


def in_base(amount: float, currency: str) -> float:
    if currency == base:
        return amount
    return amount * fx_now if base == "KRW" else amount / fx_now


def fmt(amount: float) -> str:
    return f"₩{amount:,.0f}" if base == "KRW" else f"${amount:,.2f}"


# ---------- 현금 + 보유 평가 ----------
cash = cash_balances(trades, cash_flows, dividends)
pos = positions(trades)

rows = []
if not pos.empty:
    start = (pd.Timestamp.today() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
    yf_symbols = tuple(
        sorted({to_yf_symbol(p.symbol, p.asset_type) for p in pos.itertuples()})
    )
    px_df = close_history(yf_symbols, start)

    for p in pos.itertuples():
        yf_sym = to_yf_symbol(p.symbol, p.asset_type)
        price_usd = (
            float(px_df[yf_sym].dropna().iloc[-1])
            if not px_df.empty and yf_sym in px_df.columns and not px_df[yf_sym].dropna().empty
            else None
        )
        if price_usd is None:
            st.warning(f"{p.symbol} 시세를 가져오지 못했습니다.")
            continue
        mv = in_base(p.quantity * price_usd, "USD")
        cost = in_base(p.total_cost, p.currency)
        rows.append(
            {
                "종목": p.symbol,
                "유형": ASSET_TYPE_LABELS.get(p.asset_type, p.asset_type),
                "섹터": sector_of(yf_sym, p.asset_type),
                "수량": p.quantity,
                "평단가": p.avg_cost,
                "현재가(USD)": price_usd,
                "평가액": mv,
                "매입액": cost,
                "평가손익": mv - cost,
                "수익률(%)": (mv / cost - 1) * 100 if cost > 0 else 0.0,
            }
        )

holdings = pd.DataFrame(rows)
holdings_value = holdings["평가액"].sum() if not holdings.empty else 0.0
cash_value = in_base(cash["KRW"], "KRW") + in_base(cash["USD"], "USD")
total_value = holdings_value + cash_value
total_cost = holdings["매입액"].sum() if not holdings.empty else 0.0
unrealized = holdings_value - total_cost

# ---------- 상단 메트릭 ----------
c1, c2, c3, c4 = st.columns(4)
c1.metric("총 자산", fmt(total_value))
c2.metric(
    "평가손익",
    fmt(unrealized),
    f"{(holdings_value / total_cost - 1) * 100:+.2f}%" if total_cost > 0 else None,
)
c3.metric("현금 (KRW)", f"₩{cash['KRW']:,.0f}")
c4.metric("현금 (USD)", f"${cash['USD']:,.2f}")
st.caption(f"적용 환율: 1 USD = ₩{fx_now:,.1f} (yfinance)")

# ---------- 보유 종목 테이블 ----------
if not holdings.empty:
    st.subheader("보유 종목")
    display = holdings.sort_values("평가액", ascending=False).reset_index(drop=True)
    st.dataframe(
        display,
        width="stretch",
        column_config={
            "수량": st.column_config.NumberColumn(format="%.4f"),
            "평단가": st.column_config.NumberColumn(format="%.2f"),
            "현재가(USD)": st.column_config.NumberColumn(format="%.2f"),
            "평가액": st.column_config.NumberColumn(format="localized"),
            "매입액": st.column_config.NumberColumn(format="localized"),
            "평가손익": st.column_config.NumberColumn(format="localized"),
            "수익률(%)": st.column_config.NumberColumn(format="%.2f"),
        },
    )

    # ---------- 자산배분 차트 ----------
    st.subheader("자산배분")
    alloc = pd.concat(
        [
            holdings[["종목", "평가액"]].rename(columns={"종목": "이름"}),
            pd.DataFrame(
                [
                    {"이름": "현금(KRW)", "평가액": in_base(cash["KRW"], "KRW")},
                    {"이름": "현금(USD)", "평가액": in_base(cash["USD"], "USD")},
                ]
            ),
        ]
    )
    alloc = alloc[alloc["평가액"] > 0]

    col_a, col_b = st.columns(2)
    with col_a:
        fig = px.pie(alloc, names="이름", values="평가액", title="종목별 (현금 포함)", hole=0.4)
        st.plotly_chart(fig, width="stretch")
    with col_b:
        sector_alloc = holdings.groupby("섹터")["평가액"].sum().reset_index()
        fig2 = px.pie(sector_alloc, names="섹터", values="평가액", title="섹터별", hole=0.4)
        st.plotly_chart(fig2, width="stretch")
else:
    st.info("보유 중인 종목이 없습니다.")
