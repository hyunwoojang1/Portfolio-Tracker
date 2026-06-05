"""일별 평가액 시계열, TWR 수익률, 베타, 월별 수익률 계산.

TWR(시간가중수익률)을 쓰는 이유: 입금/출금 타이밍의 영향을 제거해야
벤치마크 지수와 공정하게 비교할 수 있다. 입출금(DEPOSIT/WITHDRAW)만
외부 현금흐름으로 취급하고, 매매·환전·배당은 포트폴리오 내부 사건으로 본다.
"""

import numpy as np
import pandas as pd

from core.portfolio import cash_events
from core.prices import to_yf_symbol

MIN_BETA_SAMPLES = 8  # 주간 수익률 기준 최소 표본 수


def _daily_quantity_matrix(trades: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """날짜 × 심볼 보유수량 매트릭스."""
    symbols = sorted(trades["symbol"].unique())
    deltas = pd.DataFrame(0.0, index=idx, columns=symbols)
    for t in trades.itertuples():
        date = pd.to_datetime(t.trade_date)
        signed = t.quantity if t.side == "BUY" else -t.quantity
        deltas.loc[date, t.symbol] += signed
    return deltas.cumsum()


def _daily_cash_matrix(events: pd.DataFrame, idx: pd.DatetimeIndex) -> pd.DataFrame:
    """날짜 × 통화 현금잔고 매트릭스."""
    cash = pd.DataFrame(0.0, index=idx, columns=["KRW", "USD"])
    if events.empty:
        return cash
    pivot = events.pivot_table(index="date", columns="currency", values="amount", aggfunc="sum")
    for ccy in ("KRW", "USD"):
        if ccy in pivot.columns:
            cash[ccy] = pivot[ccy].reindex(idx).fillna(0.0)
    return cash.cumsum()


def daily_valuation(
    trades: pd.DataFrame,
    cash_flows: pd.DataFrame,
    dividends: pd.DataFrame,
    prices_usd: pd.DataFrame,
    fx: pd.Series,
    base: str = "KRW",
) -> pd.DataFrame:
    """일별 총 평가액과 외부 현금흐름.

    returns: DataFrame(index=date, columns=[value, ext_flow]) — base 통화 기준
    """
    events = cash_events(trades, cash_flows, dividends)
    if events.empty and trades.empty:
        return pd.DataFrame(columns=["value", "ext_flow"])

    start = events["date"].min() if not events.empty else pd.to_datetime(trades["trade_date"]).min()
    idx = pd.date_range(start, pd.Timestamp.today().normalize(), freq="D")

    fx = fx.reindex(idx).ffill().bfill()

    # 보유 종목 평가액 (USD)
    holdings_usd = pd.Series(0.0, index=idx)
    if not trades.empty:
        qty = _daily_quantity_matrix(trades, idx)
        for symbol in qty.columns:
            asset_type = trades.loc[trades["symbol"] == symbol, "asset_type"].iloc[-1]
            yf_sym = to_yf_symbol(symbol, asset_type)
            if yf_sym not in prices_usd.columns:
                continue
            px = prices_usd[yf_sym].reindex(idx).ffill()
            holdings_usd = holdings_usd.add((qty[symbol] * px).fillna(0.0), fill_value=0.0)

    # 현금 잔고
    cash = _daily_cash_matrix(events, idx)
    total_usd = holdings_usd + cash["USD"] + cash["KRW"] / fx

    # 외부 현금흐름(입출금)을 base 통화로 환산
    ext = events[events["kind"].isin(["DEPOSIT", "WITHDRAW"])]
    ext_flow = pd.Series(0.0, index=idx)
    for e in ext.itertuples():
        rate = fx.loc[e.date] if e.date in fx.index else fx.iloc[-1]
        if base == "KRW":
            ext_flow.loc[e.date] += e.amount * rate if e.currency == "USD" else e.amount
        else:
            ext_flow.loc[e.date] += e.amount / rate if e.currency == "KRW" else e.amount

    value = total_usd * fx if base == "KRW" else total_usd
    return pd.DataFrame({"value": value, "ext_flow": ext_flow})


def twr_returns(valuation: pd.DataFrame) -> pd.Series:
    """일별 TWR 수익률: r_t = (V_t - F_t) / V_{t-1} - 1"""
    prev = valuation["value"].shift(1)
    r = (valuation["value"] - valuation["ext_flow"]) / prev - 1
    r = r.replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if len(r) > 0:
        r.iloc[0] = 0.0
    return r


def cumulative_return(returns: pd.Series) -> pd.Series:
    return (1 + returns).cumprod() - 1


def benchmark_returns(bench_prices: pd.Series, idx: pd.DatetimeIndex) -> pd.Series:
    px = bench_prices.reindex(idx).ffill()
    return px.pct_change().fillna(0.0)


def portfolio_beta(port_ret: pd.Series, bench_ret: pd.Series) -> float | None:
    """주간 수익률 기준 베타. 주식(주5일)·코인(주7일) 캘린더 차이를 흡수한다."""
    weekly_p = (1 + port_ret).resample("W-FRI").prod() - 1
    weekly_b = (1 + bench_ret).resample("W-FRI").prod() - 1
    aligned = pd.concat([weekly_p, weekly_b], axis=1, keys=["p", "b"]).dropna()
    aligned = aligned[(aligned != 0).any(axis=1)]
    if len(aligned) < MIN_BETA_SAMPLES:
        return None
    var_b = aligned["b"].var()
    if var_b == 0 or np.isnan(var_b):
        return None
    return float(aligned["p"].cov(aligned["b"]) / var_b)


def monthly_returns_table(returns: pd.Series) -> pd.DataFrame:
    """연도 × 월 수익률 피벗 (히트맵용)."""
    monthly = (1 + returns).resample("ME").prod() - 1
    if monthly.empty:
        return pd.DataFrame()
    df = monthly.to_frame("ret")
    df["year"] = df.index.year
    df["month"] = df.index.month
    return df.pivot_table(index="year", columns="month", values="ret")
