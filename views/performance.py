"""성과 분석: 벤치마크 대비 누적수익률, 포트폴리오 베타, 월별 수익률 히트맵."""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from core.performance import (
    benchmark_returns,
    cumulative_return,
    daily_valuation,
    monthly_returns_table,
    portfolio_beta,
    twr_returns,
)
from core.prices import close_history, to_yf_symbol, usdkrw_history
from db.database import get_cash_flows, get_dividends, get_trades

BENCHMARK_PRESETS = {
    "S&P 500 (SPY)": "SPY",
    "나스닥 100 (QQQ)": "QQQ",
    "KOSPI (^KS11)": "^KS11",
    "비트코인 (BTC-USD)": "BTC-USD",
    "직접 입력": None,
}
PERIODS = {"3개월": 90, "6개월": 180, "1년": 365, "전체": None}

st.title("📈 성과 분석")

trades = get_trades()
cash_flows = get_cash_flows()
dividends = get_dividends()

if trades.empty:
    st.info("거래 기록이 있어야 성과를 분석할 수 있습니다. **거래 입력**에서 시작하세요.")
    st.stop()

# ---------- 설정 ----------
c1, c2, c3 = st.columns(3)
preset = c1.selectbox("벤치마크", list(BENCHMARK_PRESETS.keys()))
bench_symbol = BENCHMARK_PRESETS[preset]
if bench_symbol is None:
    bench_symbol = c2.text_input("벤치마크 티커", value="VTI").strip().upper()
period_label = c3.selectbox("기간", list(PERIODS.keys()), index=3)
base = st.sidebar.radio("기준 통화", ["KRW", "USD"], horizontal=True)

if not bench_symbol:
    st.warning("벤치마크 티커를 입력하세요.")
    st.stop()

# ---------- 데이터 적재 ----------
first_date = pd.to_datetime(trades["trade_date"]).min()
fetch_start = (first_date - pd.Timedelta(days=14)).strftime("%Y-%m-%d")

port_symbols = tuple(
    sorted({to_yf_symbol(t.symbol, t.asset_type) for t in trades.itertuples()})
)
with st.spinner("시세 데이터를 가져오는 중..."):
    prices = close_history(port_symbols, fetch_start)
    bench_prices_df = close_history((bench_symbol,), fetch_start)
    try:
        fx = usdkrw_history(fetch_start)
    except RuntimeError as err:
        st.error(str(err))
        st.stop()

if bench_prices_df.empty or bench_symbol not in bench_prices_df.columns:
    st.error(f"벤치마크 '{bench_symbol}' 시세를 가져오지 못했습니다. 티커를 확인하세요.")
    st.stop()

valuation = daily_valuation(trades, cash_flows, dividends, prices, fx, base=base)
if valuation.empty or len(valuation) < 2:
    st.info("데이터가 충분하지 않습니다. 거래일 이후 최소 2일이 지나야 합니다.")
    st.stop()

port_ret = twr_returns(valuation)
bench_ret = benchmark_returns(bench_prices_df[bench_symbol], valuation.index)

# 기간 필터
days = PERIODS[period_label]
if days is not None:
    cutoff = pd.Timestamp.today().normalize() - pd.Timedelta(days=days)
    port_ret_w = port_ret[port_ret.index >= cutoff]
    bench_ret_w = bench_ret[bench_ret.index >= cutoff]
else:
    port_ret_w, bench_ret_w = port_ret, bench_ret

cum_port = cumulative_return(port_ret_w)
cum_bench = cumulative_return(bench_ret_w)

# ---------- 메트릭 ----------
beta = portfolio_beta(port_ret_w, bench_ret_w)
m1, m2, m3 = st.columns(3)
m1.metric(f"포트폴리오 수익률 ({period_label})", f"{cum_port.iloc[-1] * 100:+.2f}%")
m2.metric(f"{bench_symbol} 수익률 ({period_label})", f"{cum_bench.iloc[-1] * 100:+.2f}%")
m3.metric(
    f"베타 (vs {bench_symbol})",
    f"{beta:.2f}" if beta is not None else "표본 부족",
    help="주간 수익률 기준. 8주 이상의 데이터가 필요합니다.",
)

# ---------- 누적 수익률 차트 ----------
st.subheader("누적 수익률 비교 (TWR)")
st.caption("시간가중수익률(TWR) — 입출금 타이밍의 영향을 제거해 벤치마크와 공정하게 비교합니다.")
fig = go.Figure()
fig.add_trace(go.Scatter(x=cum_port.index, y=cum_port * 100, name="내 포트폴리오", line=dict(width=2.5)))
fig.add_trace(go.Scatter(x=cum_bench.index, y=cum_bench * 100, name=bench_symbol, line=dict(width=1.5, dash="dot")))
fig.update_layout(yaxis_title="누적 수익률 (%)", hovermode="x unified", legend=dict(orientation="h"))
st.plotly_chart(fig, width="stretch")

# ---------- 평가액 추이 ----------
st.subheader(f"총 자산 추이 ({base})")
fig_v = px.area(valuation, y="value")
fig_v.update_layout(yaxis_title=f"평가액 ({base})", showlegend=False)
st.plotly_chart(fig_v, width="stretch")

# ---------- 월별 수익률 히트맵 ----------
st.subheader("월별 수익률")
monthly = monthly_returns_table(port_ret)
if monthly.empty:
    st.info("월별 수익률을 계산할 데이터가 부족합니다.")
else:
    fig_m = px.imshow(
        monthly * 100,
        text_auto=".1f",
        color_continuous_scale="RdYlGn",
        color_continuous_midpoint=0,
        aspect="auto",
        labels=dict(x="월", y="연도", color="%"),
    )
    st.plotly_chart(fig_m, width="stretch")
