"""배당금: 수령 기록 추가/삭제. 세후 금액이 현금 잔고에 반영된다."""

import datetime as dt

import streamlit as st

from db.database import add_dividend, delete_dividend, get_dividends

st.title("💰 배당금")

with st.form("dividend_form", clear_on_submit=True):
    c1, c2, c3 = st.columns(3)
    pay_date = c1.date_input("지급일", value=dt.date.today())
    symbol = c2.text_input("종목 코드", placeholder="AAPL").strip().upper()
    currency = c3.selectbox("통화", ["USD", "KRW"])

    c4, c5, c6 = st.columns(3)
    amount = c4.number_input("배당금 (세전)", min_value=0.0, step=0.01, format="%.2f")
    tax = c5.number_input("원천징수세", min_value=0.0, step=0.01, format="%.2f", value=0.0)
    note = c6.text_input("메모", placeholder="(선택)")

    if st.form_submit_button("배당 기록", type="primary"):
        if not symbol:
            st.error("종목 코드를 입력하세요.")
        elif amount <= 0:
            st.error("배당금은 0보다 커야 합니다.")
        elif tax > amount:
            st.error("세금이 배당금보다 클 수 없습니다.")
        else:
            add_dividend(pay_date.isoformat(), symbol, amount, tax, currency, note)
            st.success(f"{symbol} 배당 {amount - tax:,.2f} {currency} (세후) 기록 완료")
            st.rerun()

st.subheader("배당 내역")
dividends = get_dividends()
if dividends.empty:
    st.info("기록된 배당이 없습니다.")
else:
    display = dividends.sort_values(["pay_date", "id"], ascending=False).copy()
    display["세후"] = display["amount"] - display["tax"]
    display = display[["id", "pay_date", "symbol", "amount", "tax", "세후", "currency", "note"]].rename(
        columns={
            "pay_date": "지급일", "symbol": "종목", "amount": "세전",
            "tax": "세금", "currency": "통화", "note": "메모",
        }
    )
    st.dataframe(display, width="stretch", hide_index=True)

    total_by_ccy = (
        dividends.assign(net=dividends["amount"] - dividends["tax"])
        .groupby("currency")["net"]
        .sum()
    )
    cols = st.columns(len(total_by_ccy) or 1)
    for col, (ccy, total) in zip(cols, total_by_ccy.items()):
        col.metric(f"누적 배당 (세후, {ccy})", f"{total:,.2f}")

    with st.expander("배당 삭제"):
        del_id = st.number_input("삭제할 배당 ID", min_value=1, step=1, key="div_del")
        if st.button("삭제", type="secondary", key="div_del_btn"):
            if del_id in dividends["id"].values:
                delete_dividend(int(del_id))
                st.success(f"배당 #{del_id} 삭제 완료")
                st.rerun()
            else:
                st.error("존재하지 않는 배당 ID입니다.")
