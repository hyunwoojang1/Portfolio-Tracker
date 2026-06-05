"""yfinance 기반 가격·환율 조회 (Streamlit 캐시 적용).

- 미국 주식/ETF: 심볼 그대로 (AAPL, SPY)
- 암호화폐: 심볼-USD (BTC -> BTC-USD)
- 환율: USDKRW=X
모든 시세는 USD 기준으로 받고, KRW 환산은 환율 시리즈로 처리한다.
"""

import pandas as pd
import streamlit as st
import yfinance as yf

FX_TICKER = "USDKRW=X"
PRICE_CACHE_TTL = 1800  # 30분
INFO_CACHE_TTL = 86400  # 24시간


def to_yf_symbol(symbol: str, asset_type: str) -> str:
    symbol = symbol.strip().upper()
    if asset_type == "crypto":
        return f"{symbol}-USD"
    return symbol


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def close_history(yf_symbols: tuple[str, ...], start: str) -> pd.DataFrame:
    """일별 종가(USD). 컬럼 = yf 심볼, 인덱스 = 날짜(daily, ffill)."""
    if not yf_symbols:
        return pd.DataFrame()
    raw = yf.download(
        list(yf_symbols), start=start, progress=False, auto_adjust=True, group_by="column"
    )
    if raw.empty:
        return pd.DataFrame()
    close = raw["Close"]
    if isinstance(close, pd.Series):
        close = close.to_frame(name=yf_symbols[0])
    close.index = pd.to_datetime(close.index).tz_localize(None).normalize()
    # 주말·휴장일 포함 일 단위로 채워서 주식/코인/환율 캘린더를 통일
    full_idx = pd.date_range(close.index.min(), pd.Timestamp.today().normalize(), freq="D")
    return close.reindex(full_idx).ffill()


@st.cache_data(ttl=PRICE_CACHE_TTL, show_spinner=False)
def usdkrw_history(start: str) -> pd.Series:
    df = close_history((FX_TICKER,), start)
    if df.empty:
        raise RuntimeError("USDKRW 환율 데이터를 가져오지 못했습니다. 네트워크를 확인하세요.")
    return df[FX_TICKER]


def last_usdkrw() -> float:
    start = (pd.Timestamp.today() - pd.Timedelta(days=14)).strftime("%Y-%m-%d")
    return float(usdkrw_history(start).dropna().iloc[-1])


@st.cache_data(ttl=INFO_CACHE_TTL, show_spinner=False)
def sector_of(yf_symbol: str, asset_type: str) -> str:
    if asset_type == "crypto":
        return "Crypto"
    if asset_type == "etf":
        return "ETF"
    try:
        return yf.Ticker(yf_symbol).info.get("sector") or "Unknown"
    except Exception:
        return "Unknown"


@st.cache_data(ttl=INFO_CACHE_TTL, show_spinner=False)
def beta_of(yf_symbol: str) -> float | None:
    """yfinance가 제공하는 종목 베타 (참고용)."""
    try:
        beta = yf.Ticker(yf_symbol).info.get("beta")
        return float(beta) if beta is not None else None
    except Exception:
        return None
