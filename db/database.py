"""SQLite 연결·초기화·CRUD. 모든 개인 데이터는 data/portfolio.db 로컬 파일에만 저장된다."""

import sqlite3
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DB_PATH = DATA_DIR / "portfolio.db"
SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"


def get_connection() -> sqlite3.Connection:
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    with get_connection() as conn:
        conn.executescript(SCHEMA_PATH.read_text(encoding="utf-8"))


def fetch_df(query: str, params: tuple = ()) -> pd.DataFrame:
    with get_connection() as conn:
        return pd.read_sql_query(query, conn, params=params)


def execute(query: str, params: tuple = ()) -> int:
    with get_connection() as conn:
        cur = conn.execute(query, params)
        conn.commit()
        return cur.lastrowid


# ---------- trades ----------

def add_trade(
    trade_date: str,
    symbol: str,
    asset_type: str,
    side: str,
    quantity: float,
    price: float,
    fee: float,
    currency: str,
    note: str = "",
    external_id: str | None = None,
) -> int:
    return execute(
        """
        INSERT INTO trades
            (trade_date, symbol, asset_type, side, quantity, price, fee, currency, note, external_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (trade_date, symbol.strip().upper(), asset_type, side, quantity, price, fee, currency, note, external_id),
    )


def add_trade_if_new(
    trade_date: str,
    symbol: str,
    asset_type: str,
    side: str,
    quantity: float,
    price: float,
    fee: float,
    currency: str,
    note: str = "",
    external_id: str | None = None,
) -> bool:
    """external_id 중복이면 건너뛰는 멱등 삽입 (CSV 가져오기·증권사 동기화용).

    returns: 실제로 삽입됐으면 True, 중복으로 건너뛰었으면 False
    """
    with get_connection() as conn:
        cur = conn.execute(
            """
            INSERT OR IGNORE INTO trades
                (trade_date, symbol, asset_type, side, quantity, price, fee, currency, note, external_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (trade_date, symbol.strip().upper(), asset_type, side, quantity, price, fee, currency, note, external_id),
        )
        conn.commit()
        return cur.rowcount > 0


def get_trades() -> pd.DataFrame:
    return fetch_df("SELECT * FROM trades ORDER BY trade_date, id")


def delete_trade(trade_id: int) -> None:
    execute("DELETE FROM trades WHERE id = ?", (trade_id,))


# ---------- cash flows ----------

def add_cash_flow(
    flow_date: str,
    flow_type: str,
    currency: str,
    amount: float,
    counter_currency: str | None = None,
    counter_amount: float | None = None,
    note: str = "",
) -> int:
    return execute(
        """
        INSERT INTO cash_flows
            (flow_date, flow_type, currency, amount, counter_currency, counter_amount, note)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (flow_date, flow_type, currency, amount, counter_currency, counter_amount, note),
    )


def get_cash_flows() -> pd.DataFrame:
    return fetch_df("SELECT * FROM cash_flows ORDER BY flow_date, id")


def delete_cash_flow(flow_id: int) -> None:
    execute("DELETE FROM cash_flows WHERE id = ?", (flow_id,))


# ---------- dividends ----------

def add_dividend(
    pay_date: str,
    symbol: str,
    amount: float,
    tax: float,
    currency: str,
    note: str = "",
) -> int:
    return execute(
        """
        INSERT INTO dividends (pay_date, symbol, amount, tax, currency, note)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (pay_date, symbol.strip().upper(), amount, tax, currency, note),
    )


def get_dividends() -> pd.DataFrame:
    return fetch_df("SELECT * FROM dividends ORDER BY pay_date, id")


def delete_dividend(dividend_id: int) -> None:
    execute("DELETE FROM dividends WHERE id = ?", (dividend_id,))
