# 시스템 설계 (BXM_DESIGN.md)
> 대상: BXM팀 온라인 외부몰 수주/매출 현황 뷰어
> 최종 갱신: 2026-04-22

---

## 1. 아키텍처

```
사용자 브라우저
      ↓
Streamlit (app.py — st.navigation() 라우터)
      ├── pages/사업부.py     ← DESKER 사업부 페이지
      └── pages/bxm.py       ← BXM 페이지
                ↓
          sheets_bxm.py      ← Google Sheets API (gspread + 서비스 계정)
          BXM_채널설정.xlsx   ← 채널·PM 설정 (코드 외부 관리)
```

- **DB 없음**: 사업부와 달리 SQLite 캐시 미사용 — API에서 직접 읽어 session_state에 보관
- **인증**: 사업부 app.py의 secrets.toml 공유 (로그인 세션 공유)
- **app.py**: `st.navigation()` 라우터로 변경 — `st.set_page_config()` 1회 호출 후 페이지 분기

---

## 2. 파일 구조

```
월별마감업무자동화/
├── app.py                  ← st.navigation() 라우터 (신규 — thin router)
├── db.py                   ← 사업부 전용 (수정 없음)
├── sheets.py               ← 사업부 전용 (수정 없음)
├── sheets_bxm.py           ← BXM API 로드·파싱 (gspread 방식)
├── pages/
│   ├── 사업부.py           ← DESKER 사업부 페이지 (기존 app.py 로직 이전)
│   └── bxm.py             ← BXM 뷰어 페이지
├── BXM_채널설정.xlsx        ← 채널·PM 설정 파일 (.gitignore 권장)
├── .streamlit/
│   └── secrets.toml       ← [app] [supabase] [sheets] [bxm_sheets] (git 제외)
├── MD FILE/
│   ├── BXM_REQ.md
│   ├── BXM_DESIGN.md
│   └── BXM_TASK.md
```

---

## 3. 데이터 소스 (sheets_bxm.py)

### Google Sheets API 연결

| 구분 | Spreadsheet ID | GID |
|------|---------------|-----|
| 수주 | `14vEttvIlz-0R1fWqze3UjAQAUwpINI3Z` | `1977937242` |
| 매출 | `1MmL2djqR7F0vLrHm_6BIIlz1TT3_ugTSzKZOkhlcGrU` | `876366879` |

**인증**: `google.oauth2.service_account.Credentials` + `gspread.authorize()`
- `creds_file` 경로: `secrets.toml [bxm_sheets]` 섹션에서 읽기
- Scope: `spreadsheets.readonly`, `drive.readonly`

### 열 구조 (공통)

| 열 인덱스 | 내용 |
|----------|------|
| 0 | 구분 (온라인) |
| 1 | PM / 연도 |
| 2 | 채널명 |
| 3 | 지표명 |
| 4 | 합계 |
| 5~16 | 1월~12월 |

### 동적 파싱 방식 (행 인덱스 고정 사용 안 함)

채널이 추가되면 행 번호가 밀리므로 **고정 인덱스를 사용하지 않는다.**
대신 col2(채널명) + col3(지표명) 조합을 키로 삼아 행을 찾는다.

```
_build_index(df) → { (채널명, 지표명): row_idx, ... }
get_values(df, idx, 채널명, 지표명) → { "합계": float, "m1"~"m12": float|None }
```

- 로드 시 1회 스캔으로 전체 인덱스 구축 → O(1) 조회
- 채널/행 추가·순서 변경에 영향 없음
- col2/col3이 비어 있는 행(헤더·빈 행)은 인덱싱 제외

**수주 시트에서 읽는 (채널명, 지표명) 조합 (참고용)**

| 채널명 | 지표명 |
|--------|--------|
| 온라인합계 | 목표, 수주액, 달성률, 성장률(YOY), 25년 동기 |
| 네이버 | 목표, 수주액, 달성률, 성장률(YOY), 25년 동기 |
| 오늘의집 | 수주액, 달성률, 성장률(YOY), 25년 동기 |
| CJ몰 | 수주액, 달성률, 성장률(YOY), 25년 동기 |
| SSG | 수주액, 달성률, 성장률(YOY), 25년 동기 |
| 쿠팡 | 수주액, 달성률, 성장률(YOY), 25년 동기 |

**매출 시트에서 읽는 (채널명, 지표명) 조합 (참고용)**

| 채널명 | 지표명 |
|--------|--------|
| 온라인합계 | 목표, 매출액, 엑스트라, 달성률, 성장률(YOY), 25년 동기, 25년 엑스트라, 24년 동기, 24년 엑스트라 |
| 네이버 | 목표, 매출액, 엑스트라, 달성률, 성장률(YOY), 25년 동기, 25년 엑스트라 |
| 오늘의집 | 매출액, 엑스트라, 달성률, 성장률(YOY), 25년 동기, 25년 엑스트라 |
| CJ몰 | 매출액, 엑스트라, 달성률, 성장률(YOY), 25년 동기, 25년 엑스트라 |
| SSG | 매출액, 엑스트라, 달성률, 성장률(YOY), 25년 동기, 25년 엑스트라 |
| 쿠팡 | 매출액, 엑스트라, 달성률, 성장률(YOY), 25년 동기, 25년 엑스트라 |

---

## 4. 데이터 흐름

```
pages/bxm.py 진입
  ↓
세션 로그인 확인 → 미로그인 시 로그인 화면
  ↓
session_state["bxm_data"] 확인
  ↓ (없거나 새로고침 클릭)
sheets_bxm.load_orders() / load_sales()
  → _get_client(): secrets.toml[bxm_sheets][creds_file] 로 서비스 계정 로드
  → _load_sheet(): gspread로 워크시트 가져와 DataFrame 변환
  ↓
파싱: 행 인덱스로 채널·지표 추출, 월별 금액 클린징 (#REF → None, 쉼표·공백 제거)
  ↓
BXM_채널설정.xlsx 읽기 → 채널 순서·PM 정보
  ↓
session_state["bxm_data"] 저장
  ↓
대시보드 렌더링
```

---

## 5. 주요 함수 설계

### sheets_bxm.py

| 함수 | 역할 |
|------|------|
| `_get_client()` | secrets.toml에서 creds_file 경로 읽어 gspread 클라이언트 반환 |
| `_load_sheet(spreadsheet_id, gid)` | gspread로 시트 로드 → DataFrame 반환 |
| `_clean_val(v)` | 단일 셀 값 클린징 (#REF!→None, " - "→None, 쉼표·공백 제거 후 float) |
| `_build_index(df)` | col2+col3 복합키로 전체 행 스캔 → `{(채널명, 지표명): row_idx}` 반환 |
| `get_values(df, idx, ch, metric)` | 인덱스에서 행 찾기 → `{"합계": float, "m1"~"m12": float\|None}` 반환 |
| `load_orders()` | 수주 시트 → _load_sheet → _build_index → (df, idx) 반환 |
| `load_sales()` | 매출 시트 → _load_sheet → _build_index → (df, idx) 반환 |
| `load_channel_config()` | BXM_채널설정.xlsx 읽기 → 채널 목록·PM·목표여부·순서 반환 |

> 목표 없는 채널(오늘의집·CJ몰·SSG·쿠팡)은 수주/매출 모두 목표·달성률 없음. get_values → None 반환 → UI "-" 표시. 온라인합계·네이버만 목표 있음.

> 달성률·성장률은 시트 수식이 아닌 코드에서 직접 계산: 달성률 = act/tgt, 성장률 = (act-yoy)/abs(yoy)

### pages/bxm.py (사업부 app.py에서 복제 재사용)

| 함수 | 역할 |
|------|------|
| `fmt_won(n)` | 원 → 억 단위 포맷 (소수점 없음 `:.0f`, KPI 카드 잘림 방지) |
| `fmt_pct(r)` | 비율 → % 문자열 (사업부와 동일 로직) |
| `fmt_pct_signed(r)` | 비율 → % 문자열, 양수에 `+` 부호 — YOY 성장률 전용 |
| `_show_table(html)` | HTML 테이블 렌더링 (overflow-x:auto) |
| `_build_html_monthly(...)` | 채널 월별 상세 HTML 테이블 생성 — `is_gr = metric == "성장률(YOY)"` 조건부 색상 |
| `_orders_monthly_html(ch, ...)` | 수주 채널 월별 HTML 반환 — `tgt_annual` m1~m12 직접 합산 |
| `_sales_monthly_html(ch, ...)` | 매출 채널 월별 HTML 반환 — `tgt_annual` m1~m12 직접 합산 |

---

## 6. UI 구조

```
사이드바
├── DESKER 월별마감
├── ── (구분선)
├── 페이지 라디오 (대시보드 / 과거실적)  ← label_visibility="collapsed"
├── ── (구분선)
├── [Google Sheets 연동]
│   ├── [BXM 시트연동 새로고침] 버튼
│   ├── 연동 시트 열기 (링크)
│   └── 최종 로드 시각
├── ── (구분선)
└── 로그아웃

과거실적 페이지 (page == "과거실적" → st.stop() 격리)
├── 제목: 25년 BXM 채널별 수주/매출 현황
├── 수주 / 매출 탭
│   ├── [수주 탭] 25년 채널별 월별 수주 테이블 (HTML)
│   └── [매출 탭] 25년 채널별 월별 매출 테이블 (HTML)
└── (st.stop() — 아래 대시보드 코드 실행 안 함)

대시보드 (page == "대시보드")
├── 제목: 2026년 BXM 온라인 수주/매출 현황
├── 수주 / 매출 탭
│
├── [수주 탭]
│   ├── KPI 카드 × 6 (온라인합계 기준)
│   │   연간목표 / YTD목표 / 누적실적 / 달성률 / YoY실적 / YoY성장률
│   ├── 채널별 현황 테이블
│   │   행: 온라인합계 · 네이버 · 오늘의집 · CJ몰 · SSG · 쿠팡
│   │   열: PM / YTD실적 / 전년동기 / YoY성장률(YOY) / 달성률
│   └── 월별 상세 테이블 (채널 선택 드롭다운)
│       행: 목표 / 수주액 / 달성률 / 성장률(YOY) / 25년 동기
│       열: 1월~12월 + 합계(YTD 누적 기준)
│
├── [매출 탭]
│   ├── KPI 카드 × 6 (온라인합계 기준)
│   │   연간목표(m1~m12 직접합산) / YTD목표 / 누적실적 / 달성률 / YoY실적 / YoY성장률
│   ├── 채널별 현황 테이블
│   │   열: PM / YTD실적 / 엑스트라 / 전년동기 / YoY성장률(YOY) / 달성률
│   ├── 월별 상세 테이블 (채널 선택 드롭다운)
│   │   행: 목표 / 매출액 / 엑스트라 / 달성률 / 성장률(YOY) / 25년 동기 / 25년 엑스트라
│   └── 엑스트라 요약 테이블
│       26년 / 25년 월별 EXTRA
│
└── 푸터 (개발 및 수정문의: DESKER 김선영 / 버전 / KST)
```

> **`tgt_annual` 계산**: `tgt_vals["합계"]` (시트 합계 셀) 대신 `sum(tgt_vals[f"m{m}"] for m in range(1, 13) if tgt_vals[f"m{m}"])` — 시트 합계 셀이 YTD까지만 합산할 수 있어 전체 연간 목표가 YTD값으로 왜곡되는 버그 방지 (3곳 동일 적용)

---

## 7. 색상 시스템 (사업부와 동일)

| 용도 | 색상 |
|------|------|
| 배경 | #FFFFFF |
| 실적·달성(양호) | #00B441 |
| 미달·감소 | #F72B35 |
| YoY·강조 | #336DFF |
| 텍스트 메인 | #282828 |
| 텍스트 서브 | #3C3C3C |
| 텍스트 보조 | #969696 |

---

## 8. 데이터 클린징 규칙

| 원본 값 | 처리 |
|---------|------|
| `#REF!` | `None` (달성률 표시 시 "-") |
| `"  - "` | `None` (미입력 월) |
| 쉼표·공백 포함 숫자 | strip 후 float 변환 |
| 음수 (` - 926,934,359`) | 앞뒤 공백 제거 후 음수 float |

---

## 9. BXM_채널설정.xlsx 구조

| 컬럼 | 예시 |
|------|------|
| 채널명 | 네이버 |
| PM | 유지원/이유정 |
| 목표여부 | Y |
| 순서 | 1 |

> 채널 추가·PM 변경 시 이 파일만 수정하면 코드 변경 불필요

---

## 10. 보안 고려사항

| 항목 | 처리 방법 |
|------|----------|
| 서비스 계정 JSON | 프로젝트 디렉토리 외부에 저장, git 추적 제외 |
| secrets.toml | `.streamlit/` 내 Streamlit 기본 .gitignore 패턴으로 제외 |
| creds_file 경로 | secrets.toml `[bxm_sheets]` 섹션에서 읽기 — 코드에 하드코딩 안 함 |

---

## 11. 향후 전환 고려사항

| 단계 | 변경 범위 |
|------|----------|
| 2단계 (MSSQL) | sheets_bxm.py 전체 교체, BXM_채널설정 DB 이관, UI 변경 없음 |
