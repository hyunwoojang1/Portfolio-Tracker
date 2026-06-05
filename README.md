# Portfolio Tracker

개인용 포트폴리오 트래커 (Streamlit + SQLite). [Portfolio Visualizer](https://www.portfoliovisualizer.com/) 느낌의 로컬 앱.

미국주식(USD)과 암호화폐(KRW)를 함께 추적하고, 매매에 따라 원화/달러 현금이 자동으로 움직이며, 벤치마크 대비 성과와 포트폴리오 베타를 분석한다.

## 기능

- **거래 입력** — 매수/매도 기록. 현금 잔고(원화·달러)에 자동 반영, 매도 가능 수량 검증
- **현금 · 환전** — 입금/출금/환전(KRW↔USD) 장부
- **배당금** — 세전/세후 배당 기록, 현금 잔고 반영
- **대시보드** — 총 자산, 평가손익, 보유 종목, 종목별/섹터별 자산배분 (KRW/USD 표시 전환)
- **성과 분석**
  - 벤치마크(SPY, QQQ, KOSPI, BTC 또는 임의 티커) 대비 누적 수익률 — TWR 기준이라 입출금 왜곡 없음
  - 포트폴리오 베타 (주간 수익률 기준)
  - 월별 수익률 히트맵, 총 자산 추이

시세·환율은 [yfinance](https://github.com/ranaroussi/yfinance) (무료, API 키 불필요).

## 실행

```bash
pip install -r requirements.txt
streamlit run app.py
```

## 데이터 보안

**모든 거래 데이터는 `data/portfolio.db` 로컬 파일에만 저장되며 git에 커밋되지 않는다** (`.gitignore` 처리). 이 저장소에는 코드만 올라간다.

## 구조

```
app.py               # Streamlit 진입점 (st.navigation)
db/
  schema.sql         # 테이블 정의 (trades / cash_flows / dividends)
  database.py        # SQLite 연결 + CRUD
core/
  prices.py          # yfinance 시세·환율·섹터 (캐시)
  portfolio.py       # 포지션, 현금잔고, 실현손익 (이동평균법)
  performance.py     # 일별 평가액, TWR, 베타, 월별 수익률
views/
  dashboard.py       # 대시보드
  trades.py          # 거래 입력
  cash.py            # 현금 · 환전
  dividends.py       # 배당금
  performance.py     # 성과 분석
```

## 설계 노트

- DB에는 **사건(거래/입출금/환전/배당)만 저장**하고 잔고·포지션·수익률은 항상 재계산 (불변 원장)
- `trades.external_id` — 증권사 주문번호용 유니크 컬럼. 향후 증권사 API 자동 동기화 시 중복 없는 upsert 키로 사용
- 평단가는 이동평균법 (국내 증권사 방식)
- 수익률은 TWR(시간가중) — 입출금(DEPOSIT/WITHDRAW)만 외부 현금흐름으로 취급
- 베타는 주간 수익률로 계산 — 주식(주5일)과 코인(주7일)의 거래일 차이를 흡수

## 로드맵

- [ ] 증권사 체결내역 자동 동기화 (나무증권 QV Open API 배치 에이전트)
- [ ] CSV 거래내역 일괄 가져오기
- [ ] 손익 캘린더
