"""거래·현금흐름·배당 원장에서 포지션, 현금잔고, 실현손익을 도출한다.

원칙: DB에는 사건(event)만 저장하고 잔고·포지션은 항상 재계산한다 (불변 원장).
평단가는 이동평균법(매수 시 평단 갱신, 매도 시 평단 유지) — 국내 증권사 방식과 동일.
"""

import pandas as pd

CURRENCIES = ("KRW", "USD")


def trade_cash_delta(side: str, quantity: float, price: float, fee: float) -> float:
    gross = quantity * price
    if side == "BUY":
        return -(gross + fee)
    return gross - fee


def cash_events(
    trades: pd.DataFrame, cash_flows: pd.DataFrame, dividends: pd.DataFrame
) -> pd.DataFrame:
    """현금에 영향을 주는 모든 사건. columns = [date, currency, amount, kind]"""
    events: list[tuple] = []
    for t in trades.itertuples():
        delta = trade_cash_delta(t.side, t.quantity, t.price, t.fee)
        events.append((t.trade_date, t.currency, delta, "TRADE"))
    for f in cash_flows.itertuples():
        if f.flow_type == "DEPOSIT":
            events.append((f.flow_date, f.currency, f.amount, "DEPOSIT"))
        elif f.flow_type == "WITHDRAW":
            events.append((f.flow_date, f.currency, -f.amount, "WITHDRAW"))
        else:  # FX: 판 통화에서 빠지고 산 통화로 들어옴
            events.append((f.flow_date, f.currency, -f.amount, "FX"))
            events.append((f.flow_date, f.counter_currency, f.counter_amount, "FX"))
    for d in dividends.itertuples():
        events.append((d.pay_date, d.currency, d.amount - d.tax, "DIVIDEND"))

    df = pd.DataFrame(events, columns=["date", "currency", "amount", "kind"])
    if not df.empty:
        df["date"] = pd.to_datetime(df["date"])
    return df


def cash_balances(
    trades: pd.DataFrame, cash_flows: pd.DataFrame, dividends: pd.DataFrame
) -> dict[str, float]:
    """현재 통화별 현금 잔고."""
    balances = {ccy: 0.0 for ccy in CURRENCIES}
    events = cash_events(trades, cash_flows, dividends)
    if events.empty:
        return balances
    summed = events.groupby("currency")["amount"].sum()
    for ccy in CURRENCIES:
        balances[ccy] = float(summed.get(ccy, 0.0))
    return balances


def positions(trades: pd.DataFrame) -> pd.DataFrame:
    """보유 포지션 + 종목별 실현손익(이동평균법).

    returns columns:
        symbol, asset_type, currency, quantity, avg_cost, total_cost, realized_pnl
    """
    if trades.empty:
        return pd.DataFrame(
            columns=["symbol", "asset_type", "currency", "quantity", "avg_cost", "total_cost", "realized_pnl"]
        )

    rows = []
    ordered = trades.sort_values(["trade_date", "id"])
    for symbol, grp in ordered.groupby("symbol"):
        qty, cost, realized = 0.0, 0.0, 0.0
        for t in grp.itertuples():
            if t.side == "BUY":
                qty += t.quantity
                cost += t.quantity * t.price + t.fee
            else:
                avg = cost / qty if qty > 0 else 0.0
                realized += (t.price - avg) * t.quantity - t.fee
                cost -= avg * t.quantity
                qty -= t.quantity
        last = grp.iloc[-1]
        rows.append(
            {
                "symbol": symbol,
                "asset_type": last["asset_type"],
                "currency": last["currency"],
                "quantity": qty,
                "avg_cost": cost / qty if qty > 1e-9 else 0.0,
                "total_cost": cost if qty > 1e-9 else 0.0,
                "realized_pnl": realized,
            }
        )
    return pd.DataFrame(rows)


def held_quantity(trades: pd.DataFrame, symbol: str) -> float:
    """특정 종목의 현재 보유 수량 (매도 가능 수량 검증용)."""
    if trades.empty:
        return 0.0
    grp = trades[trades["symbol"] == symbol.strip().upper()]
    bought = grp.loc[grp["side"] == "BUY", "quantity"].sum()
    sold = grp.loc[grp["side"] == "SELL", "quantity"].sum()
    return float(bought - sold)
