# 구현 태스크 (BXM_TASK.md)
> 대상: BXM팀 온라인 외부몰 수주/매출 현황 뷰어
> 최종 갱신: 2026-04-22

---

## 완료

### 환경 준비
- [x] `pages/` 디렉토리 생성
- [x] `gspread`, `google-auth` 패키지 설치 (`python -m pip install gspread google-auth`)
- [x] 서비스 계정 JSON 준비 (GCP desker-bxm-kgi-2026 프로젝트)
- [x] `.streamlit/secrets.toml` — `[bxm_sheets] creds_file` 섹션 추가

### app.py 라우터 전환
- [x] `app.py` → `st.navigation()` 라우터로 재작성 (사이드바 이름: DESKER 사업부 / BXM)
- [x] `pages/사업부.py` — 기존 app.py 로직 이전 (`st.set_page_config()` 제거)
- [x] `pages/bxm.py` — `st.set_page_config()` 제거 (라우터로 이전)

### sheets_bxm.py (데이터 레이어)
- [x] `_get_client()` — secrets.toml에서 creds_file 읽어 gspread 클라이언트 반환
- [x] `_load_sheet(spreadsheet_id, gid)` — gspread로 워크시트 로드 → DataFrame 반환
- [x] `_clean_val(v)` — 단일 셀 클린징 (#REF→None, " - "→None, 쉼표·공백→float)
- [x] `_build_index(df)` — col2(채널명)+col3(지표명) 복합키로 {(채널,지표):행인덱스} 구축
- [x] `get_values(df, idx, 채널, 지표)` — 인덱스 조회 → 합계+월별 Dict 반환 (없으면 None)
- [x] `load_orders()` — 수주 시트 (ID: `14vEttvIlz-0R1fWqze3UjAQAUwpINI3Z`, gid: `1977937242`)
- [x] `load_sales()` — 매출 시트 (ID: `1MmL2djqR7F0vLrHm_6BIIlz1TT3_ugTSzKZOkhlcGrU`, gid: `876366879`)
- [x] `load_channel_config()` — BXM_채널설정.xlsx → 채널 목록·PM·목표여부·순서 반환
- [x] 목표 없는 채널(오늘의집·CJ몰·SSG·쿠팡) 달성률: #REF→None → UI에서 "-" 처리

### pages/bxm.py (UI 레이어)
- [x] 로그인 세션 확인 (미로그인 시 로그인 화면)
- [x] 사이드바: "Google Sheets 연동" 섹션 — BXM 시트연동 새로고침 버튼 + 연동 시트 열기 링크 + 최종 로드 시각
- [x] 수주 / 매출 탭 전환
- [x] KPI 카드 × 6 (온라인합계 기준, 사업부와 동일 구조)
- [x] 채널별 현황 테이블 (수주·매출 탭)
- [x] 월별 상세 테이블 (채널 선택 드롭다운)
- [x] 달성률·성장률 코드에서 직접 계산 (시트 수식 셀 읽지 않음)
- [x] 엑스트라 요약 테이블 (매출 탭)
- [x] `fmt_won()` / `fmt_pct()` / `_show_table()` (사업부 로직 복제)
- [x] DESKER 디자인 시스템 CSS (Pretendard, 색상 동일)

### 2026-04-22 — UX·버그 수정

#### app.py
- [x] 네비게이션 명칭 `"BXM"` → `"BXM(온라인외부몰)"` (`st.Page` title 파라미터)

#### pages/bxm.py — 기능 추가
- [x] 사이드바 페이지 라디오 `["대시보드", "과거실적"]` 추가 (`label_visibility="collapsed"`)
- [x] 과거실적 페이지 신설: 25년 수주·매출 탭 HTML 테이블 + `st.stop()` 격리
- [x] tab_orders / tab_sales 하단 과거실적 섹션 삭제 (독립 페이지로 이동)

#### pages/bxm.py — 지표 명칭·계산 수정
- [x] "성장률" → "성장률(YOY)" 명칭 변경 (수주·매출 월별 상세 테이블)
- [x] `_build_html_monthly`: `is_gr = metric == "성장률(YOY)"` 조건 수정 (이름 변경에 맞게)
- [x] YOY 합계 컬럼: `act_v["합계"]` → `sum(act_v[f"m{m}"] for m in range(1, last_m+1))` (동기간 누적 비교)
- [x] `fmt_pct_signed(r)` 신규 함수 — 양수 YOY에 `+` 부호 표시

#### pages/bxm.py — KPI 카드 버그 수정
- [x] 연간목표 KPI 잘림 수정: `fmt_won` `.1f` → `.0f` ("1,200억" 정상 표시)
- [x] 매출 연간목표 왜곡 수정: `tgt_annual = tgt_vals["합계"]` → `sum(tgt_vals[f"m{m}"] for m in range(1,13))` (3곳, replace_all)

### MD 파일 업데이트
- [x] BXM_REQ.md — gspread API 방식, 새 스프레드시트 ID/GID, 완료 기능 반영
- [x] BXM_DESIGN.md — 아키텍처·파일구조·데이터소스 업데이트
- [x] BXM_TASK.md — 태스크 상태 업데이트

---

## 미완료 / 향후 작업

| 항목 | 우선순위 | 비고 |
|------|---------|------|
| `BXM_채널설정.xlsx` 초기 파일 생성 | 높음 | 채널 6개, PM, 목표여부, 순서 입력 필요 |
| 실제 연동 테스트 | 높음 | 서비스 계정 공유 권한 확인 후 앱 실행 |
| 2단계: ERP MSSQL 연동 | 낮음 | 사내 서버 이관 시 진행 |

---

## 보안 체크리스트

- [x] 서비스 계정 JSON은 프로젝트 디렉토리 **외부** 보관
- [x] `.streamlit/secrets.toml` — git 커밋 제외 (Streamlit 기본 .gitignore 패턴)
- [x] BXM 관련 변경사항 — git push 보류 (커밋/푸시 전 별도 검토 예정)

---

## 변경 이력

| 날짜 | 내용 |
|------|------|
| 2026-04-22 | BXM_TASK.md 초안 작성 |
| 2026-04-22 | gspread API 전환 완료, 사이드바 UI 추가, 라우터 전환 — 태스크 상태 업데이트 |
| 2026-04-22 | app.py 네비 명칭 "BXM" → "BXM(온라인외부몰)" |
| 2026-04-22 | 사이드바 페이지 라디오 추가 (대시보드/과거실적) |
| 2026-04-22 | 과거실적 독립 페이지 신설 (25년 수주·매출, st.stop() 격리) |
| 2026-04-22 | "성장률" → "성장률(YOY)" 명칭 변경 + YOY 합계 동기간 누적 계산 수정 |
| 2026-04-22 | fmt_pct_signed() 신규 함수 (양수 + 부호) |
| 2026-04-22 | 연간목표 KPI 잘림 수정 (fmt_won .0f), tgt_annual 전체연간 합산 수정 (3곳) |
