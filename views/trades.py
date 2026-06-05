"""거래 입력: 매수/매도 기록 추가, 목록 조회, 삭제."""

import datetime as dt

import streamlit as st

from core.portfolio import held_quantity, trade_cash_delta
from db.database import add_trade, delete_trade, get_trades

ASSET_TYPES = {"주식": "stock", "ETF": "etf", "암호화폐": "crypto"}
SIDES = {"매수": "BUY", "매도": "SELL"}

st.title("📒 거래 입력")

with st.form("trade_form", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    trade_date = c1.date_input("거래일", value=dt.date.today(), max_value=dt.date.today())
    symbol = c2.text_input("종목 코드", placeholder="AAPL, SPY, BTC ...").strip().upper()
    asset_label = c3.selectbox("자산 유형", list(ASSET_TYPES.keys()))

    c4, c5, c6, c7 = st.columns(4)
    side_label = c4.selectbox("구분", list(SIDES.keys()))
    quantity = c5.number_input("수량", min_value=0.0, step=1.0, format="%.6f")
    price = c6.number_input("단가", min_value=0.0, step=0.01, format="%.4f")
    fee = c7.number_input("수수료", min_value=0.0, step=0.01, format="%.2f", value=0.0)

    c8, c9 = st.columns([1, 3])
    currency = c8.selectbox(
        "통화", ["USD", "KRW"], help="미국주식은 USD, 원화로 산 코인은 KRW"
    )
    note = c9.text_input("메모", placeholder="(선택)")

    submitted = st.form_submit_button("거래 추가", type="primary")

if submitted:
    asset_type = ASSET_TYPES[asset_label]
    side = SIDES[side_label]
    if not symbol:
        st.error("종목 코드를 입력하세요.")
    elif quantity <= 0:
        st.error("수량은 0보다 커야 합니다.")
    elif price <= 0:
        st.error("단가는 0보다 커야 합니다.")
    else:
        trades = get_trades()
        if side == "SELL":
            held = held_quantity(trades, symbol)
            if quantity > held + 1e-9:
                st.error(f"보유 수량({held:g})보다 많이 매도할 수 없습니다.")
                st.stop()
        add_trade(
            trade_date=trade_date.isoformat(),
            symbol=symbol,
            asset_type=asset_type,
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            currency=currency,
            note=note,
        )
        delta = trade_cash_delta(side, quantity, price, fee)
        st.success(f"{symbol} {side_label} {quantity:g}주 기록 완료 (현금 {delta:+,.2f} {currency})")

# ---------- 거래 내역 ----------
st.subheader("거래 내역")
trades = get_trades()
if trades.empty:
    st.info("기록된 거래가 없습니다.")
else:
    display = trades.sort_values(["trade_date", "id"], ascending=False)[
        ["id", "trade_date", "symbol", "asset_type", "side", "quantity", "price", "fee", "currency", "note"]
    ].rename(
        columns={
            "trade_date": "거래일", "symbol": "종목", "asset_type": "유형", "side": "구분",
            "quantity": "수량", "price": "단가", "fee": "수수료", "currency": "통화", "note": "메모",
        }
    )
    st.dataframe(display, width="stretch", hide_index=True)

    with st.expander("거래 삭제"):
        del_id = st.number_input("삭제할 거래 ID", min_value=1, step=1)
        if st.button("삭제", type="secondary"):
            if del_id in trades["id"].values:
                delete_trade(int(del_id))
                st.success(f"거래 #{del_id} 삭제 완료")
                st.rerun()
            else:
                st.error("존재하지 않는 거래 ID입니다.")
