"""거래내역 가져오기 검증: 멱등 삽입 + 화면 렌더링."""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import db.database as database

_tmp = Path(tempfile.mkdtemp())
database.DATA_DIR = _tmp
database.DB_PATH = _tmp / "test.db"


def test_idempotent_insert():
    database.init_db()
    ok1 = database.add_trade_if_new(
        "2026-01-05", "AAPL", "stock", "BUY", 10, 200.0, 0.5, "USD", external_id="import-abc"
    )
    ok2 = database.add_trade_if_new(
        "2026-01-05", "AAPL", "stock", "BUY", 10, 200.0, 0.5, "USD", external_id="import-abc"
    )
    assert ok1 is True and ok2 is False, (ok1, ok2)
    assert len(database.get_trades()) == 1
    print("OK add_trade_if_new 멱등성 (중복 주문번호 건너뜀)")


def test_import_view_renders():
    from streamlit.testing.v1 import AppTest

    at = AppTest.from_file(str(PROJECT_ROOT / "views" / "import_csv.py"), default_timeout=30)
    at.run()
    assert not at.exception, at.exception
    print("OK import_csv 화면 렌더링")


if __name__ == "__main__":
    test_idempotent_insert()
    test_import_view_renders()
    print("\n가져오기 테스트 통과")
