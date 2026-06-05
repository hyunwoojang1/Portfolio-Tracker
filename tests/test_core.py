"""핵심 계산 로직 검증: 포지션, 현금잔고, 실현손익, TWR, 베타.

실행: python -m pytest tests/ 또는 python tests/test_core.py
네트워크 불필요 — 가격 데이터는 합성으로 생성한다.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import numpy as np
import pandas as pd

from core.performance import (
    cumulative_return,
    daily_valuation,
    monthly_returns_table,
    portfolio_beta,
    twr_returns,
)
from core.portfolio import cash_balances, held_quantity, positions, trade_cash_delta


def make_trades():
    return pd.DataFrame(
        [
            # AAPL: 10주 @ $100 매수, 4주 @ $120 매도 → 보유 6주, 실현익 (120-101)*4 - 1 = 75
            {"id": 1, "trade_date": "2026-01-05", "symbol": "AAPL", "asset_type": "stock",
             "side": "BUY", "quantity": 10, "price": 100.0, "fee": 10.0, "currency": "USD"},
            {"id": 2, "trade_date": "2026-02-02", "symbol": "AAPL", "asset_type": "stock",
             "side": "SELL", "quantity": 4, "price": 120.0, "fee": 1.0, "currency": "USD"},
            # BTC: 0.1개 @ ₩100,000,000 매수 (원화)
            {"id": 3, "trade_date": "2026-01-10", "symbol": "BTC", "asset_type": "crypto",
             "side": "BUY", "quantity": 0.1, "price": 100_000_000.0, "fee": 5000.0, "currency": "KRW"},
        ]
    )


def make_cash_flows():
    return pd.DataFrame(
        [
            {"id": 1, "flow_date": "2026-01-02", "flow_type": "DEPOSIT", "currency": "KRW",
             "amount": 20_000_000.0, "counter_currency": None, "counter_amount": None},
            # ₩7,000,000 → $5,000 환전
            {"id": 2, "flow_date": "2026-01-03", "flow_type": "FX", "currency": "KRW",
             "amount": 7_000_000.0, "counter_currency": "USD", "counter_amount": 5000.0},
        ]
    )


def make_dividends():
    return pd.DataFrame(
        [
            {"id": 1, "pay_date": "2026-03-02", "symbol": "AAPL", "amount": 50.0,
             "tax": 7.5, "currency": "USD"},
        ]
    )


def test_trade_cash_delta():
    assert trade_cash_delta("BUY", 10, 100.0, 10.0) == -1010.0
    assert trade_cash_delta("SELL", 4, 120.0, 1.0) == 479.0
    print("OK trade_cash_delta")


def test_positions():
    pos = positions(make_trades())
    aapl = pos[pos["symbol"] == "AAPL"].iloc[0]
    # 평단 = (10*100 + 10) / 10 = 101
    assert abs(aapl["quantity"] - 6) < 1e-9
    assert abs(aapl["avg_cost"] - 101.0) < 1e-9
    # 실현익 = (120 - 101) * 4 - 1 = 75
    assert abs(aapl["realized_pnl"] - 75.0) < 1e-9
    btc = pos[pos["symbol"] == "BTC"].iloc[0]
    assert abs(btc["quantity"] - 0.1) < 1e-9
    assert btc["currency"] == "KRW"
    print("OK positions (이동평균 평단·실현손익)")


def test_cash_balances():
    bal = cash_balances(make_trades(), make_cash_flows(), make_dividends())
    # KRW: 2천만 입금 - 700만 환전 - (BTC 1천만 + 수수료 5천) = 2,995,000
    assert abs(bal["KRW"] - 2_995_000.0) < 1e-6, bal
    # USD: 5000 환전입금 - 1010 매수 + 479 매도 + 42.5 배당 = 4511.5
    assert abs(bal["USD"] - 4511.5) < 1e-6, bal
    print("OK cash_balances (KRW/USD 듀얼 장부)")


def test_held_quantity():
    assert abs(held_quantity(make_trades(), "AAPL") - 6) < 1e-9
    assert abs(held_quantity(make_trades(), "btc") - 0.1) < 1e-9
    print("OK held_quantity")


def make_fake_prices(start="2025-12-20"):
    idx = pd.date_range(start, pd.Timestamp.today().normalize(), freq="D")
    rng = np.random.default_rng(42)
    aapl = 100 * np.cumprod(1 + rng.normal(0.0005, 0.01, len(idx)))
    btc = 70_000 * np.cumprod(1 + rng.normal(0.001, 0.03, len(idx)))
    prices = pd.DataFrame({"AAPL": aapl, "BTC-USD": btc}, index=idx)
    fx = pd.Series(1400.0 + rng.normal(0, 5, len(idx)).cumsum() * 0.1, index=idx)
    return prices, fx


def test_valuation_and_twr():
    trades, flows, divs = make_trades(), make_cash_flows(), make_dividends()
    prices, fx = make_fake_prices()

    val = daily_valuation(trades, flows, divs, prices, fx, base="KRW")
    assert not val.empty
    assert (val["value"].dropna() > 0).all()
    # 첫날(입금일) 평가액 ≈ 입금액
    assert abs(val["value"].iloc[0] - 20_000_000.0) < 1.0

    ret = twr_returns(val)
    # 입금만 있던 날의 TWR은 0이어야 함 (외부 흐름 제거 확인)
    assert abs(ret.iloc[0]) < 1e-12
    cum = cumulative_return(ret)
    assert len(cum) == len(ret)
    print(f"OK daily_valuation + TWR (최종 평가액 ₩{val['value'].iloc[-1]:,.0f}, 누적수익 {cum.iloc[-1]*100:+.2f}%)")


def test_beta():
    idx = pd.date_range("2025-06-01", periods=400, freq="D")
    rng = np.random.default_rng(7)
    bench = pd.Series(rng.normal(0.0005, 0.01, len(idx)), index=idx)
    port = 1.5 * bench + pd.Series(rng.normal(0, 0.002, len(idx)), index=idx)
    beta = portfolio_beta(port, bench)
    assert beta is not None and 1.3 < beta < 1.7, beta
    # 표본 부족이면 None
    assert portfolio_beta(port.iloc[:10], bench.iloc[:10]) is None
    print(f"OK portfolio_beta (기대 1.5 → 계산 {beta:.3f})")


def test_monthly_table():
    idx = pd.date_range("2026-01-01", periods=120, freq="D")
    ret = pd.Series(0.001, index=idx)
    table = monthly_returns_table(ret)
    assert not table.empty
    assert 2026 in table.index
    print("OK monthly_returns_table")


if __name__ == "__main__":
    test_trade_cash_delta()
    test_positions()
    test_cash_balances()
    test_held_quantity()
    test_valuation_and_twr()
    test_beta()
    test_monthly_table()
    print("\n전체 테스트 통과")
