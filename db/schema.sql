-- 포트폴리오 트래커 스키마
-- 거래: 매수/매도. external_id는 증권사 주문번호(향후 나무증권 자동 동기화 upsert 키)
CREATE TABLE IF NOT EXISTS trades (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    trade_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    asset_type TEXT NOT NULL DEFAULT 'stock' CHECK (asset_type IN ('stock', 'etf', 'crypto')),
    side TEXT NOT NULL CHECK (side IN ('BUY', 'SELL')),
    quantity REAL NOT NULL CHECK (quantity > 0),
    price REAL NOT NULL CHECK (price >= 0),
    fee REAL NOT NULL DEFAULT 0 CHECK (fee >= 0),
    currency TEXT NOT NULL CHECK (currency IN ('USD', 'KRW')),
    note TEXT,
    external_id TEXT UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 현금 흐름: 입금/출금/환전
-- FX는 currency/amount = 판 통화·금액, counter_currency/counter_amount = 산 통화·금액
CREATE TABLE IF NOT EXISTS cash_flows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    flow_date TEXT NOT NULL,
    flow_type TEXT NOT NULL CHECK (flow_type IN ('DEPOSIT', 'WITHDRAW', 'FX')),
    currency TEXT NOT NULL CHECK (currency IN ('USD', 'KRW')),
    amount REAL NOT NULL CHECK (amount > 0),
    counter_currency TEXT CHECK (counter_currency IN ('USD', 'KRW')),
    counter_amount REAL CHECK (counter_amount > 0),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

-- 배당금 (세후 = amount - tax 가 현금에 반영됨)
CREATE TABLE IF NOT EXISTS dividends (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pay_date TEXT NOT NULL,
    symbol TEXT NOT NULL,
    amount REAL NOT NULL CHECK (amount >= 0),
    tax REAL NOT NULL DEFAULT 0 CHECK (tax >= 0),
    currency TEXT NOT NULL CHECK (currency IN ('USD', 'KRW')),
    note TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_trades_date ON trades (trade_date);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades (symbol);
CREATE INDEX IF NOT EXISTS idx_cash_flows_date ON cash_flows (flow_date);
CREATE INDEX IF NOT EXISTS idx_dividends_date ON dividends (pay_date);
