# 시스템 설계 (사업부_DESIGN.md)
> 대상: DESKER 사업부 전체 월별마감 관리 시스템
> 최종 갱신: 2026-04-21

---

## 1. 아키텍처

```
사용자 브라우저
      ↓
Streamlit app.py
      ├── sheets.py  ← Google Sheets API 연동
      └── db.py      ← SQLite (demo.db) CRUD
```

- **UI/비즈니스 로직**: app.py (단일 파일)
- **데이터 소스**: Google Sheets (원본) → SQLite (로컬 캐시)
- **인증**: .streamlit/secrets.toml (비밀번호, Sheets ID)
- **실행**: `python -m streamlit run app.py --server.headless true`

---

## 2. 데이터베이스 (SQLite — demo.db)

### 테이블 구조

#### targets (연간 목표)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| data_type | TEXT | 수주 / 매출 |
| channel | TEXT | 온라인외부몰 / 오프라인 / 공식몰+MATE |
| year | INTEGER | 연도 |
| month | INTEGER | 1~12 |
| amount | REAL | 금액 (원) |
| UNIQUE | (data_type, channel, year, month) | |

#### actuals (당해 월별 실적 — Sheets 연동)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| data_type | TEXT | 수주 / 매출 |
| channel | TEXT | 입력 채널 3종 |
| year | INTEGER | |
| month | INTEGER | |
| amount | REAL | |
| UNIQUE | (data_type, channel, year, month) | |

#### historical (과거 실적 — 읽기 전용)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| data_type | TEXT | |
| channel | TEXT | |
| year | INTEGER | 2025 이전 |
| month | INTEGER | |
| amount | REAL | |
| locked | INTEGER | 1이면 수정 불가 |

#### extra (EXTRA 조정 데이터)
| 컬럼 | 타입 | 설명 |
|------|------|------|
| data_type | TEXT | |
| channel | TEXT | 합계/B2C온라인/B2C오프라인/B2B(특판/직판) |
| year | INTEGER | |
| month | INTEGER | |
| amount | REAL | ± 조정액 |

---

## 3. 파일 구조

```
월별마감업무자동화/
├── app.py               ← 메인 Streamlit 앱 (사업부 전체)
├── db.py                ← SQLite CRUD 함수
├── sheets.py            ← Google Sheets 동기화
├── demo.db              ← 로컬 SQLite DB
├── schema.sql           ← DB 스키마
├── requirements.txt
├── .streamlit/
│   └── secrets.toml     ← 비밀번호, Sheets ID
├── 사업부_REQ.md
├── 사업부_DESIGN.md
└── 사업부_TASK.md
```

---

## 4. 주요 함수 설계 (app.py)

### 유틸
| 함수 | 역할 |
|------|------|
| `fmt_won(n)` | 원 → 억 단위 포맷 (100억 미만 소수점 1자리) |
| `fmt_pct(r)` | 비율 → % 문자열 |
| `add_derived(pivot)` | B2C소계·합계 행 추가, ALL_CHANNELS 순서 정렬 |
| `to_pivot(df)` | DataFrame → 채널×월 피벗 |
| `filter_type(df, dtype)` | 수주/매출 필터 |
| `_show_table(styler)` | HTML 렌더링 테이블 (overflow-x:auto, 가운데정렬) |

### 대시보드 내부
| 함수/로직 | 역할 |
|---------|------|
| `active_row(pivot)` | 선택 뷰에 맞는 월별 Series 반환 |
| `_donut(vals, total, ...)` | Plotly 도넛 차트 생성 (중앙 합계+증감+성장률) |
| `_fmt_diff(diff)` | ± 억 단위 증감액 포맷 |
| `_style_q(df)` | 분기 테이블 달성률/YoY 색상 조건부 서식 |
| `_style_summary(df)` | 채널 요약 테이블 조건부 서식 |
| `_extra_table(df, label)` | EXTRA 현황 테이블 렌더링 |

---

## 5. 데이터 흐름

### 초기 접속
```
로그인
  ↓
sheets 설정 확인
  ↓ (설정됨)
last_sync 세션 확인
  ↓ (미연동)
연동 게이트 화면 표시 → "시트 연동하기" 클릭
  ↓
sheets.sync_from_sheets() → DB 저장
  ↓
대시보드 표시
```

### 대시보드 렌더링
```
필터 선택 (연도/구분/구분방식/뷰)
  ↓
db.get_targets / get_actuals / get_historical
  ↓
to_pivot → add_derived (B2C소계·합계 계산)
  ↓
active_row() → 선택 뷰의 월별 Series
  ↓
KPI 계산 (YTD 기간 기준)
  ↓
차트·테이블 렌더링
```

---

## 6. UI 구조

```
사이드바
├── DESKER 월별마감
├── 메뉴 (대시보드 / 설정)
├── [Google Sheets 연동]
│   ├── 최종 연동 시각
│   ├── 시트연동 새로고침 버튼
│   └── 연동 시트 열기 링크
└── 로그아웃

대시보드
├── 제목: 2026년 데스커사업부 월별마감
├── 필터 행 (연도 / 구분 / 구분방식 / 뷰)
├── KPI 카드 × 6
├── ── (구분선)
├── 월별 추이 차트 (콤보)
├── 목표 대비 달성률 게이지
├── 채널별 실적 비중 도넛 (2열)  ← BXM·B2B는 metric으로 대체
├── 월별 상세 테이블
│   └── [분기별 현황 expander]
├── 채널별 누적 현황 테이블
│   └── [분기별 현황 expander]
├── EXTRA 현황 테이블 (당해 / 전년)
└── 푸터

설정
├── 연간 목표 설정 탭
└── 과거 실적 입력 탭 (수정 불가)
```

---

## 7. 색상 시스템

| 용도 | 색상 |
|------|------|
| 배경 | #FFFFFF |
| 사이드바 | #F5F5F5 |
| 실적·달성(양호) | #00B441 |
| 미달·감소 | #F72B35 |
| YoY·강조 | #336DFF |
| 주의(90%대) | #F57C00 |
| 텍스트 메인 | #282828 |
| 텍스트 서브 | #3C3C3C |
| 텍스트 보조 | #969696 |

---

## 8. 향후 확장

| 항목 | 내용 |
|------|------|
| BXM 전용 앱 | 사업부_BXM 시리즈 문서 별도 작성 예정 |
| 멀티페이지 구조 | pages/ 디렉토리 분리 검토 (사업부 vs BXM) |
| ERP 자동 연동 | 2단계 계획 (MSSQL) |
