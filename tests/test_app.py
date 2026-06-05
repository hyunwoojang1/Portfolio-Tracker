"""Streamlit AppTest로 각 화면 렌더링 검증 (임시 DB 사용, 실데이터 미접촉).

실행: python tests/test_app.py  (네트워크 필요 — yfinance 시세 호출)
"""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from streamlit.testing.v1 import AppTest

import db.database as database

# 테스트용 임시 DB로 교체 (실제 data/portfolio.db 보호)
_tmp = Path(tempfile.mkdtemp())
database.DATA_DIR = _tmp
database.DB_PATH = _tmp / "test.db"

VIEWS = [
    "views/dashboard.py",
    "views/trades.py",
    "views/cash.py",
    "views/dividends.py",
    "views/performance.py",
]


def run_view(path: str) -> AppTest:
    at = AppTest.from_file(str(PROJECT_ROOT / path), default_timeout=60)
    at.run()
    assert not at.exception, f"{path} 예외 발생: {at.exception}"
    return at


def test_empty_db_renders():
    database.init_db()
    for view in VIEWS:
        run_view(view)
        print(f"OK (빈 DB) {view}")


def test_with_data_renders():
    database.add_cash_flow("2026-04-01", "DEPOSIT", "KRW", 20_000_000)
    database.add_cash_flow("2026-04-02", "FX", "KRW", 7_000_000, "USD", 5_000)
    database.add_trade("2026-04-03", "AAPL", "stock", "BUY", 10, 200.0, 1.0, "USD")
    database.add_trade("2026-04-10", "BTC", "crypto", "BUY", 0.05, 100_000_000.0, 5_000.0, "KRW")
    database.add_trade("2026-05-01", "AAPL", "stock", "SELL", 3, 220.0, 1.0, "USD")
    database.add_dividend("2026-05-15", "AAPL", 12.0, 1.8, "USD")

    for view in VIEWS:
        run_view(view)
        print(f"OK (데이터 있음) {view}")


if __name__ == "__main__":
    test_empty_db_renders()
    test_with_data_renders()
    print("\nAppTest 전체 통과")
