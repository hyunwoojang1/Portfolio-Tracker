"""현금 · 환전: 입금/출금/환전 기록과 통화별 잔고."""

import datetime as dt

import streamlit as st

from core.portfolio import cash_balances
from db.database import add_cash_flow, delete_cash_flow, get_cash_flows, get_dividends, get_trades

st.title("💱 현금 · 환전")

trades = get_trades()
cash_flows = get_cash_flows()
dividends = get_dividends()

balances = cash_balances(trades, cash_flows, dividends)
c1, c2 = st.columns(2)
c1.metric("원화 잔고", f"₩{balances['KRW']:,.0f}")
c2.metric("달러 잔고", f"${balances['USD']:,.2f}")
if balances["KRW"] < 0 or balances["USD"] < 0:
    st.warning("잔고가 음수입니다. 누락된 입금이나 환전 기록이 있는지 확인하세요.")

tab_dep, tab_wd, tab_fx = st.tabs(["입금", "출금", "환전"])

with tab_dep, st.form("deposit_form", clear_on_submit=True):
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    d_date = c1.date_input("날짜", value=dt.date.today(), key="dep_date")
    d_ccy = c2.selectbox("통화", ["KRW", "USD"], key="dep_ccy")
    d_amount = c3.number_input("금액", min_value=0.0, step=10000.0, format="%.2f", key="dep_amt")
    d_note = c4.text_input("메모", key="dep_note")
    if st.form_submit_button("입금 기록", type="primary"):
        if d_amount <= 0:
            st.error("금액은 0보다 커야 합니다.")
        else:
            add_cash_flow(d_date.isoformat(), "DEPOSIT", d_ccy, d_amount, note=d_note)
            st.success(f"{d_ccy} {d_amount:,.2f} 입금 기록 완료")
            st.rerun()

with tab_wd, st.form("withdraw_form", clear_on_submit=True):
    c1, c2, c3, c4 = st.columns([1, 1, 1, 2])
    w_date = c1.date_input("날짜", value=dt.date.today(), key="wd_date")
    w_ccy = c2.selectbox("통화", ["KRW", "USD"], key="wd_ccy")
    w_amount = c3.number_input("금액", min_value=0.0, step=10000.0, format="%.2f", key="wd_amt")
    w_note = c4.text_input("메모", key="wd_note")
    if st.form_submit_button("출금 기록", type="primary"):
        if w_amount <= 0:
            st.error("금액은 0보다 커야 합니다.")
        else:
            add_cash_flow(w_date.isoformat(), "WITHDRAW", w_ccy, w_amount, note=w_note)
            st.success(f"{w_ccy} {w_amount:,.2f} 출금 기록 완료")
            st.rerun()

with tab_fx, st.form("fx_form", clear_on_submit=True):
    st.caption("예: 원화 1,400,000 → 달러 1,000 환전이면 판 통화 KRW / 산 통화 USD")
    c1, c2, c3 = st.columns(3)
    f_date = c1.date_input("날짜", value=dt.date.today(), key="fx_date")
    f_from = c2.selectbox("판 통화", ["KRW", "USD"], key="fx_from")
    f_from_amt = c3.number_input("판 금액", min_value=0.0, step=10000.0, format="%.2f", key="fx_from_amt")
    c4, c5 = st.columns([1, 2])
    f_to_amt = c4.number_input("받은 금액", min_value=0.0, step=10.0, format="%.2f", key="fx_to_amt")
    f_note = c5.text_input("메모", key="fx_note")
    if st.form_submit_button("환전 기록", type="primary"):
        f_to = "USD" if f_from == "KRW" else "KRW"
        if f_from_amt <= 0 or f_to_amt <= 0:
            st.error("판 금액과 받은 금액 모두 0보다 커야 합니다.")
        else:
            add_cash_flow(
                f_date.isoformat(), "FX", f_from, f_from_amt,
                counter_currency=f_to, counter_amount=f_to_amt, note=f_note,
            )
            rate = f_from_amt / f_to_amt if f_from == "KRW" else f_to_amt / f_from_amt
            st.success(f"{f_from} {f_from_amt:,.2f} → {f_to} {f_to_amt:,.2f} (환율 ₩{rate:,.1f}/$)")
            st.rerun()

# ---------- 내역 ----------
st.subheader("현금 흐름 내역")
if cash_flows.empty:
    st.info("기록된 현금 흐름이 없습니다.")
else:
    display = cash_flows.sort_values(["flow_date", "id"], ascending=False)[
        ["id", "flow_date", "flow_type", "currency", "amount", "counter_currency", "counter_amount", "note"]
    ].rename(
        columns={
            "flow_date": "날짜", "flow_type": "구분", "currency": "통화", "amount": "금액",
            "counter_currency": "받은 통화", "counter_amount": "받은 금액", "note": "메모",
        }
    )
    display["구분"] = display["구분"].map({"DEPOSIT": "입금", "WITHDRAW": "출금", "FX": "환전"})
    st.dataframe(display, width="stretch", hide_index=True)

    with st.expander("기록 삭제"):
        del_id = st.number_input("삭제할 기록 ID", min_value=1, step=1, key="cash_del")
        if st.button("삭제", type="secondary", key="cash_del_btn"):
            if del_id in cash_flows["id"].values:
                delete_cash_flow(int(del_id))
                st.success(f"기록 #{del_id} 삭제 완료")
                st.rerun()
            else:
                st.error("존재하지 않는 기록 ID입니다.")
