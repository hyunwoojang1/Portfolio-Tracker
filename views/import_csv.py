"""거래내역 가져오기: 증권사 CSV/엑셀 파일을 컬럼 매핑으로 일괄 입력.

증권사마다 컬럼 이름이 달라서 업로드 → 미리보기 → 매핑 → 가져오기 순서로 진행한다.
external_id(주문번호 또는 행 지문)로 멱등 처리 — 같은 파일을 두 번 올려도 중복되지 않는다.
"""

import hashlib
import io

import pandas as pd
import streamlit as st

from db.database import add_trade_if_new

NONE_OPTION = "(없음)"
BUY_KEYWORDS = ("매수", "BUY", "buy", "매입")
SELL_KEYWORDS = ("매도", "SELL", "sell")

COLUMN_GUESSES = {
    "date": ("거래일", "거래일자", "체결일", "체결일자", "주문일자", "date", "Date"),
    "symbol": ("종목코드", "티커", "심볼", "종목", "종목명", "symbol", "ticker", "Symbol"),
    "side": ("매매구분", "거래구분", "구분", "매수매도", "side", "type", "거래종류"),
    "quantity": ("수량", "체결수량", "주문수량", "quantity", "qty", "Quantity"),
    "price": ("단가", "체결단가", "체결가", "가격", "price", "Price"),
    "fee": ("수수료", "수수료등", "제비용", "fee", "commission"),
    "external_id": ("주문번호", "체결번호", "원주문번호", "order_id"),
}

st.title("📥 거래내역 가져오기")
st.caption("나무증권 홈페이지/HTS에서 받은 거래내역 엑셀·CSV를 올리면 일괄 입력합니다.")

uploaded = st.file_uploader("거래내역 파일", type=["csv", "xlsx", "xls"])

with st.expander("템플릿 CSV 받기 (직접 정리해서 올리고 싶을 때)"):
    template = "trade_date,symbol,side,quantity,price,fee\n2026-01-05,AAPL,BUY,10,200.5,0.25\n"
    st.download_button("템플릿 다운로드", template, "trades_template.csv", "text/csv")

if uploaded is None:
    st.stop()


def read_file(file) -> pd.DataFrame:
    if file.name.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(file)
    raw = file.read()
    for encoding in ("utf-8-sig", "cp949", "utf-8"):
        try:
            return pd.read_csv(io.BytesIO(raw), encoding=encoding)
        except UnicodeDecodeError:
            continue
    raise ValueError("파일 인코딩을 인식하지 못했습니다 (utf-8/cp949 지원).")


try:
    df = read_file(uploaded)
except Exception as err:
    st.error(f"파일을 읽지 못했습니다: {err}")
    st.stop()

df.columns = [str(c).strip() for c in df.columns]
st.subheader("미리보기")
st.dataframe(df.head(10), width="stretch", hide_index=True)


def guess_index(key: str, columns: list[str], optional: bool = False) -> int:
    options = ([NONE_OPTION] if optional else []) + columns
    for guess in COLUMN_GUESSES[key]:
        if guess in columns:
            return options.index(guess)
    return 0


cols = list(df.columns)
st.subheader("컬럼 매핑")
c1, c2, c3 = st.columns(3)
date_col = c1.selectbox("거래일 컬럼", cols, index=guess_index("date", cols))
symbol_col = c2.selectbox("종목 컬럼", cols, index=guess_index("symbol", cols))
side_col = c3.selectbox("매수/매도 컬럼", cols, index=guess_index("side", cols))

c4, c5, c6 = st.columns(3)
qty_col = c4.selectbox("수량 컬럼", cols, index=guess_index("quantity", cols))
price_col = c5.selectbox("단가 컬럼", cols, index=guess_index("price", cols))
fee_options = [NONE_OPTION] + cols
fee_col = c6.selectbox("수수료 컬럼 (없으면 0)", fee_options, index=guess_index("fee", cols, optional=True))

c7, c8, c9 = st.columns(3)
ext_options = [NONE_OPTION] + cols
ext_col = c7.selectbox(
    "주문번호 컬럼 (중복 방지 키)", ext_options, index=guess_index("external_id", cols, optional=True),
    help="없으면 날짜·종목·수량·단가로 지문을 만들어 중복을 막습니다.",
)
asset_label = c8.selectbox("자산 유형 (일괄 적용)", ["주식", "ETF", "암호화폐"])
currency = c9.selectbox("통화 (일괄 적용)", ["USD", "KRW"])

ASSET_MAP = {"주식": "stock", "ETF": "etf", "암호화폐": "crypto"}


def to_number(value) -> float:
    """'1,234.56' 같은 천단위 구분 문자열도 숫자로 변환."""
    if pd.isna(value):
        return 0.0
    return float(str(value).replace(",", "").replace("주", "").strip())


def parse_side(value) -> str | None:
    text = str(value)
    if any(k in text for k in BUY_KEYWORDS):
        return "BUY"
    if any(k in text for k in SELL_KEYWORDS):
        return "SELL"
    return None


def build_rows() -> tuple[list[dict], list[str]]:
    rows, errors = [], []
    fingerprints: dict[str, int] = {}
    for i, raw in df.iterrows():
        line = f"{i + 2}행"  # 헤더 다음부터
        try:
            trade_date = pd.to_datetime(str(raw[date_col]).strip()).date().isoformat()
            symbol = str(raw[symbol_col]).strip().upper()
            side = parse_side(raw[side_col])
            quantity = to_number(raw[qty_col])
            price = to_number(raw[price_col])
            fee = to_number(raw[fee_col]) if fee_col != NONE_OPTION else 0.0
        except Exception as err:
            errors.append(f"{line}: 값 해석 실패 — {err}")
            continue
        if side is None:
            errors.append(f"{line}: 매수/매도 구분 인식 실패 ('{raw[side_col]}')")
            continue
        if not symbol or quantity <= 0 or price <= 0:
            errors.append(f"{line}: 종목/수량/단가 값이 유효하지 않음")
            continue

        if ext_col != NONE_OPTION and str(raw[ext_col]).strip():
            external_id = f"import-{str(raw[ext_col]).strip()}"
        else:
            base = f"{trade_date}|{symbol}|{side}|{quantity:g}|{price:g}"
            seq = fingerprints[base] = fingerprints.get(base, 0) + 1
            digest = hashlib.sha1(f"{base}|{seq}".encode()).hexdigest()[:16]
            external_id = f"import-{digest}"

        rows.append(
            {
                "trade_date": trade_date, "symbol": symbol, "side": side,
                "quantity": quantity, "price": price, "fee": fee,
                "external_id": external_id,
            }
        )
    return rows, errors


rows, errors = build_rows()

st.subheader("가져오기 결과 미리보기")
if errors:
    with st.expander(f"⚠️ 건너뛸 행 {len(errors)}개"):
        for e in errors:
            st.text(e)
if not rows:
    st.warning("가져올 수 있는 행이 없습니다. 컬럼 매핑을 확인하세요.")
    st.stop()

preview = pd.DataFrame(rows)[["trade_date", "symbol", "side", "quantity", "price", "fee"]]
st.dataframe(preview, width="stretch", hide_index=True)
st.caption(f"{len(rows)}건 가져오기 준비 완료 · 자산유형 {asset_label} · 통화 {currency}")

if st.button(f"{len(rows)}건 가져오기", type="primary"):
    inserted = skipped = 0
    for r in rows:
        ok = add_trade_if_new(
            trade_date=r["trade_date"], symbol=r["symbol"], asset_type=ASSET_MAP[asset_label],
            side=r["side"], quantity=r["quantity"], price=r["price"], fee=r["fee"],
            currency=currency, note=f"가져오기: {uploaded.name}", external_id=r["external_id"],
        )
        inserted += ok
        skipped += not ok
    st.success(f"완료 — 신규 {inserted}건 입력, 중복 {skipped}건 건너뜀")
    if inserted:
        st.balloons()
