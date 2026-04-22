# pages/사업부.py  ─  DESKER 사업부 월별마감 관리 시스템
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import db
import sheets

# ─── DESKER 디자인 시스템 ──────────────────────────────────────
st.markdown("""
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard/dist/web/static/pretendard.css');
html, body, [class*="css"] {
    font-family: 'Pretendard', 'Apple SD Gothic Neo', sans-serif;
}
.stApp { background: #FFFFFF; }
h1 { font-size: 22px !important; font-weight: 700 !important; color: #282828 !important; }
h2 { font-size: 18px !important; font-weight: 600 !important; color: #282828 !important; }
h3 { font-size: 15px !important; font-weight: 600 !important; color: #3C3C3C !important; }
.stButton > button {
    background: #282828 !important;
    color: #FFFFFF !important;
    border: none !important;
    border-radius: 4px !important;
    font-size: 13px !important;
}
.stButton > button:hover { background: #515151 !important; }
.stMetric { background: #F5F5F5; border-radius: 4px; padding: 12px; }
[data-testid="stSidebar"] { background: #F5F5F5 !important; }
</style>
""", unsafe_allow_html=True)

# ─── 상수 ─────────────────────────────────────────────────────
INPUT_CHANNELS = ["온라인외부몰", "오프라인", "공식몰+MATE"]
# 합계가 맨 위에 표시되는 순서
ALL_CHANNELS   = ["합계", "온라인외부몰", "오프라인", "B2C 소계", "공식몰+MATE"]
DATA_TYPES     = ["수주", "매출"]
NOW            = datetime.now()
CY, CM         = NOW.year, NOW.month


# ─── 유틸 ─────────────────────────────────────────────────────
def fmt_won(n):
    if n is None or n == 0:
        return "-"
    v = n / 1e8
    return f"{v:,.0f}억"


def fmt_pct(r):
    if r is None:
        return "-"
    return f"{r * 100:.1f}%"


def add_derived(pivot: pd.DataFrame) -> pd.DataFrame:
    """B2C 소계·합계 행 추가 후 ALL_CHANNELS 순서로 반환 (합계 맨 위)"""
    for ch in INPUT_CHANNELS:
        if ch not in pivot.index:
            pivot.loc[ch] = 0
    pivot.loc["B2C 소계"] = (
        pivot.loc["온라인외부몰"] + pivot.loc["오프라인"]
    )
    pivot.loc["합계"] = (
        pivot.loc["온라인외부몰"]
        + pivot.loc["오프라인"]
        + pivot.loc["공식몰+MATE"]
    )
    return pivot.reindex(ALL_CHANNELS, fill_value=0)


def to_pivot(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return pd.DataFrame(0, index=INPUT_CHANNELS, columns=range(1, 13))
    p = df.pivot_table(
        index="channel", columns="month",
        values="amount", aggfunc="sum", fill_value=0,
    )
    return p.reindex(columns=range(1, 13), fill_value=0)


def filter_type(df: pd.DataFrame, dtype: str) -> pd.DataFrame:
    if df.empty:
        return df
    return df[df["data_type"] == dtype]


def _show_table(styler, caption: str = None) -> None:
    """HTML 렌더링으로 가운데 정렬 테이블 표시 (st.dataframe 대체)"""
    html = (
        styler
        .hide(names=True)
        .set_table_styles([
            {"selector": "th, td",
             "props": [("text-align", "center"), ("padding", "7px 12px"), ("white-space", "nowrap")]},
            {"selector": "table",
             "props": [("width", "100%"), ("border-collapse", "collapse"), ("font-size", "13px")]},
            {"selector": "thead tr th",
             "props": [("background-color", "#F5F5F5"), ("font-weight", "600")]},
            {"selector": "th.row_heading",
             "props": [("text-align", "center"), ("font-weight", "600")]},
            {"selector": "tbody tr:nth-child(even)",
             "props": [("background-color", "#FAFAFA")]},
        ], overwrite=False)
        .to_html()
    )
    if caption:
        st.caption(caption)
    st.markdown(f'<div style="overflow-x:auto">{html}</div>', unsafe_allow_html=True)


# ─── 로그인 ───────────────────────────────────────────────────
if not st.session_state.get("auth"):
    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        st.markdown("## DESKER 사업부")
        st.markdown("### 월별 마감 관리 시스템")
        st.markdown("---")
        pwd = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        if st.button("로그인", use_container_width=True, type="primary"):
            if pwd == st.secrets["app"]["password"]:
                st.session_state.auth = True
                st.session_state.login_time = datetime.now()
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    st.markdown("""
<div style="text-align:center;font-size:13px;color:#969696;margin-top:48px;padding:16px 0;border-top:1px solid #EBEBEB;">
  개발 및 수정문의: DESKER 김선영 &nbsp;|&nbsp; v1.1.0 &nbsp;|&nbsp; 2026-04-22 15:02 KST
</div>
""", unsafe_allow_html=True)
    st.stop()


# ─── 세션 타임아웃 (15분) ─────────────────────────────────────
_SESSION_TIMEOUT = timedelta(minutes=15)
_login_time = st.session_state.get("login_time")
if _login_time and (datetime.now() - _login_time) > _SESSION_TIMEOUT:
    st.session_state.auth = False
    st.session_state.pop("login_time", None)
    st.session_state.pop("last_sync", None)
    st.warning("세션이 만료되었습니다. 다시 로그인해주세요.")
    st.rerun()

# ─── 사이드바 ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## DESKER 월별마감")
    st.markdown("---")
    page = st.radio(
        "메뉴",
        ["대시보드", "과거실적", "설정"],
        label_visibility="collapsed",
    )
    # ── Google Sheets 연동 ────────────────────────────────────
    if sheets.is_configured():
        st.markdown("---")
        st.markdown("**Google Sheets 연동**")
        last_sync = st.session_state.get("last_sync")
        if last_sync:
            st.caption(f"최종 연동: {last_sync}")
        if st.button("시트연동 새로고침", use_container_width=True, key="sync_btn"):
            with st.spinner("데이터를 가져오는 중..."):
                result = sheets.sync_from_sheets()
            if result["errors"]:
                for err in result["errors"]:
                    st.error(err)
            else:
                st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M")
                st.success("연동 완료")
                st.rerun()
        try:
            sid = st.secrets["sheets"]["spreadsheet_id"]
            sheet_url = f"https://docs.google.com/spreadsheets/d/{sid}"
            st.markdown(f'<a href="{sheet_url}" target="_blank" style="font-size:12px;color:#336DFF;">연동 시트 열기</a>', unsafe_allow_html=True)
        except Exception:
            pass

    st.markdown("---")
    if st.button("로그아웃", use_container_width=True):
        st.session_state.auth = False
        st.rerun()


# ══════════════════════════════════════════════════════════════
# 대시보드
# ══════════════════════════════════════════════════════════════
if page == "대시보드":
    # ── 시트 연동 게이트 (sheets 설정된 경우, 세션 내 연동 필수) ──
    if sheets.is_configured() and not st.session_state.get("last_sync"):
        st.markdown("<br>" * 3, unsafe_allow_html=True)
        _, gate_col, _ = st.columns([1, 1.6, 1])
        with gate_col:
            st.markdown(
                "<div style='text-align:center;padding:40px 32px;background:#F5F5F5;"
                "border-radius:8px;border:1px solid #E0E0E0;'>"
                "<div style='font-size:36px;margin-bottom:12px;'>📊</div>"
                "<div style='font-size:18px;font-weight:700;color:#282828;margin-bottom:8px;'>"
                "데이터 연동이 필요합니다</div>"
                "<div style='font-size:13px;color:#666666;margin-bottom:24px;'>"
                "최신 데이터를 불러오려면 Google Sheets 연동을 실행해주세요.</div>"
                "</div>",
                unsafe_allow_html=True,
            )
            st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
            if st.button("시트 연동하기", use_container_width=True, type="primary", key="gate_sync"):
                with st.spinner("데이터를 가져오는 중..."):
                    result = sheets.sync_from_sheets()
                if result["errors"]:
                    for err in result["errors"]:
                        st.error(err)
                else:
                    st.session_state.last_sync = datetime.now().strftime("%Y-%m-%d %H:%M")
                    st.rerun()
        st.stop()

    st.title("2026년 데스커사업부 월별마감")

    c1, c2, c3, c4, _ = st.columns([1, 1, 1, 1, 1])
    year     = c1.selectbox("연도",      [2026],                        key="dash_year")
    seg_type = c2.selectbox("구분 방식", ["팀 구분", "고객 구분"],      key="dash_seg_type")

    # 구분 방식이 바뀌면 구분을 수주로 초기화
    if st.session_state.get("_prev_seg_type") != seg_type:
        st.session_state["dash_dtype"] = "수주"
        st.session_state["_prev_seg_type"] = seg_type

    dtype    = c3.selectbox("구분",      DATA_TYPES,                    key="dash_dtype")
    if seg_type == "팀 구분":
        view = c4.selectbox("사업부", ["전체", "BXM", "CXM"],  key="dash_view_team")
    else:
        view = c4.selectbox("고객",   ["전체", "B2C", "B2B"],  key="dash_view_cust")

    # 데이터 로드 & 피벗
    t  = add_derived(to_pivot(filter_type(db.get_targets(year),      dtype)))
    a  = add_derived(to_pivot(filter_type(db.get_actuals(year),      dtype)))
    py = add_derived(to_pivot(filter_type(db.get_historical(year-1), dtype)))

    VIEW_LABEL = {
        "전체": "사업부 전체", "BXM": "BXM", "CXM": "CXM",
        "B2C": "B2C", "B2B": "B2B",
    }

    def active_row(pivot: pd.DataFrame) -> pd.Series:
        """선택된 뷰에 맞는 월별 시리즈 반환"""
        if view == "BXM":
            return pivot.loc["온라인외부몰"]
        elif view == "CXM":
            return pivot.loc["오프라인"] + pivot.loc["공식몰+MATE"]
        elif view == "B2C":
            return pivot.loc["온라인외부몰"] + pivot.loc["오프라인"]
        elif view == "B2B":
            return pivot.loc["공식몰+MATE"]
        else:
            return pivot.loc["합계"]

    # ── 고객수 현황 (고객 구분 + 매출 시에만 표시) ───────────
    if seg_type == "고객 구분" and dtype == "매출":
        cc_2026 = db.get_customer_count(year)
        cc_2025 = db.get_customer_count(year - 1)

        _CC_ALL = ["외부몰", "매장", "DESKERS", "BIZ DESKERS"]
        _CC_B2C = ["외부몰", "매장", "DESKERS"]
        _CC_B2B = ["BIZ DESKERS"]

        def _cc_pivot(df_cc: pd.DataFrame) -> pd.DataFrame:
            if df_cc.empty:
                return pd.DataFrame(0, index=_CC_ALL, columns=range(1, 13))
            p = df_cc.pivot_table(
                index="channel", columns="month",
                values="amount", aggfunc="sum", fill_value=0,
            )
            p = p.reindex(columns=range(1, 13), fill_value=0)
            for ch in _CC_ALL:
                if ch not in p.index:
                    p.loc[ch] = 0
            return p.reindex(_CC_ALL, fill_value=0)

        cc_a = _cc_pivot(cc_2026)
        cc_p = _cc_pivot(cc_2025)

        last_cc_m = max(
            (m for m in range(1, 13) if sum(float(cc_a.loc[ch, m]) for ch in _CC_ALL) > 0),
            default=0,
        )
        cc_ytd    = sum(float(cc_a.loc[ch, mm]) for ch in _CC_ALL for mm in range(1, last_cc_m + 1)) if last_cc_m else 0
        cc_py_ytd = sum(float(cc_p.loc[ch, mm]) for ch in _CC_ALL for mm in range(1, last_cc_m + 1)) if last_cc_m else 0
        cc_gr_kpi = (cc_ytd - cc_py_ytd) / abs(cc_py_ytd) if cc_py_ytd else None
        cc_period = f"1~{last_cc_m}월" if last_cc_m else "-"

        st.markdown("### 고객수 현황")
        kc1, *_ = st.columns([1, 5])
        kc1.metric(
            f"누적 고객수 ({cc_period})",
            f"{cc_ytd:,.0f}명",
            delta=f"{cc_gr_kpi * 100:+.1f}% YoY" if cc_gr_kpi is not None else None,
        )

        # 고객수 월별 추이 차트
        cc_tot26   = [sum(float(cc_a.loc[ch, m]) for ch in _CC_ALL) for m in range(1, 13)]
        cc_tot25   = [sum(float(cc_p.loc[ch, m]) for ch in _CC_ALL) for m in range(1, 13)]
        cc_yoy     = [
            (a26 - a25) / abs(a25) * 100 if (a26 > 0 and a25) else None
            for a26, a25 in zip(cc_tot26, cc_tot25)
        ]
        cc_yoy_clr = ["#00B441" if (v is not None and v >= 0) else "#F72B35" for v in cc_yoy]
        months_lbl_cc = [f"{m}월" for m in range(1, 13)]

        def _cc_lbl(v):
            return f"{v:,.0f}" if v else None

        fig_cc = go.Figure()
        fig_cc.add_bar(
            x=months_lbl_cc, y=cc_tot25, name=f"{year - 1}년 고객수",
            marker_color="#BDBDBD", offsetgroup=0,
            text=[_cc_lbl(v) for v in cc_tot25],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=10, color="#444444"),
        )
        fig_cc.add_bar(
            x=months_lbl_cc, y=cc_tot26, name=f"{year}년 고객수",
            marker_color="#336DFF", offsetgroup=1,
            text=[_cc_lbl(v) for v in cc_tot26],
            textposition="inside", insidetextanchor="middle",
            textfont=dict(size=10, color="#FFFFFF"),
        )
        fig_cc.add_scatter(
            x=months_lbl_cc, y=cc_yoy, name="YoY 성장률",
            mode="lines+markers+text", yaxis="y2",
            line=dict(color="#00B441", width=2),
            marker=dict(color=cc_yoy_clr, size=8),
            text=[f"{v:.1f}%" if v is not None else "" for v in cc_yoy],
            textposition="top center", textfont=dict(size=11, color="#282828"),
        )
        fig_cc.update_layout(
            title=dict(text=f"{year}년 고객수 월별 추이", font=dict(size=14, color="#282828")),
            barmode="group",
            yaxis=dict(ticksuffix="명", tickformat=",.0f", showgrid=True,
                       gridcolor="#F0F0F0", tickfont=dict(size=11)),
            yaxis2=dict(overlaying="y", side="right", ticksuffix="%",
                        showgrid=False, tickfont=dict(size=11)),
            xaxis=dict(tickfont=dict(size=12)),
            height=430, plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
            legend=dict(orientation="h", xanchor="center", x=0.5,
                        yanchor="top", y=-0.08, font=dict(size=12)),
            margin=dict(t=80, b=80, l=20, r=80),
            uniformtext=dict(mode="hide", minsize=8),
        )
        st.plotly_chart(fig_cc, use_container_width=True)

        # 채널별 고객수 누적 현황 테이블
        st.markdown(f"#### 채널별 고객수 누적 현황")
        cc_hier = [
            ("합계",          _CC_ALL),
            ("B2C 소계",      _CC_B2C),
            ("  외부몰",      ["외부몰"]),
            ("  매장",        ["매장"]),
            ("  DESKERS",     ["DESKERS"]),
            ("B2B 소계",      _CC_B2B),
            ("  BIZ DESKERS", ["BIZ DESKERS"]),
        ]
        cc_sum_rows = []
        for label, chs in cc_hier:
            ytd_v  = sum(float(cc_a.loc[ch, mm]) for ch in chs for mm in range(1, last_cc_m + 1) if ch in cc_a.index) if last_cc_m else 0
            py_v   = sum(float(cc_p.loc[ch, mm]) for ch in chs for mm in range(1, last_cc_m + 1) if ch in cc_p.index) if last_cc_m else 0
            gr_v   = (ytd_v - py_v) / abs(py_v) if py_v else None
            if gr_v is None:
                gr_str = "-"
            else:
                sign = "+" if gr_v > 0 else ""
                gr_str = f"{sign}{gr_v * 100:.1f}%"
            cc_sum_rows.append({
                "채널":                       label,
                f"누적 고객수 ({cc_period})": f"{ytd_v:,.0f}" if ytd_v else "-",
                f"YoY 고객수 ({cc_period})":  f"{py_v:,.0f}"  if py_v  else "-",
                "YoY 성장률":                 gr_str,
            })
        cc_sum_df = pd.DataFrame(cc_sum_rows).set_index("채널")

        def _style_cc(df: pd.DataFrame) -> pd.DataFrame:
            styles = pd.DataFrame("", index=df.index, columns=df.columns)
            for idx in df.index:
                v_str = str(df.loc[idx, "YoY 성장률"])
                if v_str == "-":
                    continue
                try:
                    v = float(v_str.replace("%", ""))
                except ValueError:
                    continue
                styles.loc[idx, "YoY 성장률"] = (
                    "color:#00B441;font-weight:600" if v >= 0 else "color:#F72B35;font-weight:600"
                )
            return styles

        _show_table(cc_sum_df.style.apply(_style_cc, axis=None))

        # 월별 고객수 상세 테이블 (26년 / 25년 / YoY 3행)
        st.markdown(f"#### 월별 고객수 상세")
        cc_m_rows, cc_m_index = {mo: [] for mo in range(1, 13)}, []
        for label, chs in cc_hier:
            v26 = [sum(float(cc_a.loc[ch, mo]) for ch in chs if ch in cc_a.index) for mo in range(1, 13)]
            v25 = [sum(float(cc_p.loc[ch, mo]) for ch in chs if ch in cc_p.index) for mo in range(1, 13)]
            yoy = [
                (a - b) / abs(b) * 100 if (a > 0 and b) else None
                for a, b in zip(v26, v25)
            ]
            cc_m_index += [label, "  └ 25년", "  └ YoY"]
            for mo in range(1, 13):
                idx = mo - 1
                sign = "+" if (yoy[idx] is not None and yoy[idx] > 0) else ""
                cc_m_rows[mo] += [
                    f"{v26[idx]:,.0f}" if v26[idx] else "-",
                    f"{v25[idx]:,.0f}" if v25[idx] else "-",
                    f"{sign}{yoy[idx]:.1f}%" if yoy[idx] is not None else "-",
                ]
        cc_monthly_df = pd.DataFrame(
            {"채널": cc_m_index, **{f"{mo}월": cc_m_rows[mo] for mo in range(1, 13)}}
        )

        def _style_cc_monthly(df: pd.DataFrame) -> pd.DataFrame:
            styles = pd.DataFrame("", index=df.index, columns=df.columns)
            for i in df.index:
                label = str(df.loc[i, "채널"])
                is_25  = "25년" in label
                is_yoy = "YoY"  in label
                for col in df.columns:
                    if is_25:
                        styles.loc[i, col] = "color:#AAAAAA;font-size:11px;"
                    elif is_yoy:
                        v_str = str(df.loc[i, col])
                        if v_str == "-" or col == "채널":
                            continue
                        try:
                            v = float(v_str.replace("%", "").replace("+", ""))
                        except ValueError:
                            continue
                        styles.loc[i, col] = (
                            "color:#00B441;font-weight:600" if v >= 0 else "color:#F72B35;font-weight:600"
                        )
                    else:  # 26년 실적
                        styles.loc[i, col] = "font-weight:700;"
            return styles

        _show_table(
            cc_monthly_df.style
                .hide(axis="index")
                .apply(_style_cc_monthly, axis=None)
        )

        st.markdown("---")

    # ── KPI 카드 ─────────────────────────────────────────────
    act_s = active_row(a)
    py_s  = active_row(py)
    t_s   = active_row(t)

    # YoY: 실적이 있는 마지막 월까지만 같은 기간으로 비교
    last_act_m = max((m for m in range(1, 13) if float(act_s[m]) > 0), default=0)
    period_lbl = f"1~{last_act_m}월" if last_act_m else "-"

    tgt     = float(t_s.sum())
    ytd_tgt = sum(float(t_s[m])   for m in range(1, last_act_m + 1)) if last_act_m else 0
    act     = sum(float(act_s[m]) for m in range(1, last_act_m + 1)) if last_act_m else 0
    prev    = sum(float(py_s[m])  for m in range(1, last_act_m + 1)) if last_act_m else 0

    ar = act / ytd_tgt            if ytd_tgt else None
    gr = (act - prev) / abs(prev) if prev    else None

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("연간 목표",                  fmt_won(tgt))
    k2.metric(f"실적 목표 ({period_lbl})",  fmt_won(ytd_tgt))
    k3.metric(f"누적 실적 ({period_lbl})",  fmt_won(act))
    k4.metric("달성률",                     fmt_pct(ar))
    k5.metric(f"YoY 실적 ({period_lbl})",   fmt_won(prev))
    k6.metric(f"YoY 성장률 ({period_lbl})", fmt_pct(gr))
    st.markdown("---")

    _QUARTERS = [("Q1",[1,2,3]),("Q2",[4,5,6]),("Q3",[7,8,9]),("Q4",[10,11,12])]

    # ── 1. 월별 추이 콤보 차트 ───────────────────────────────
    st.markdown("### 월별 추이")
    months_lbl  = [f"{m}월" for m in range(1, 13)]
    act_monthly = [float(act_s[m]) / 1e6 for m in range(1, 13)]
    py_monthly  = [float(py_s[m])  / 1e6 for m in range(1, 13)]

    gr_monthly = []
    for av, pv in zip(act_monthly, py_monthly):
        if av > 0 and pv and pv != 0:
            gr_monthly.append((av - pv) / abs(pv) * 100)
        else:
            gr_monthly.append(None)

    gr_marker_colors = [
        "#00B441" if (v is not None and v >= 0) else "#F72B35"
        for v in gr_monthly
    ]

    def _bar_lbl(v):
        if not v:
            return None
        return f"{v:,.0f}백만"

    fig_monthly = go.Figure()
    fig_monthly.add_bar(
        x=months_lbl, y=py_monthly,
        name=f"{year - 1}년 실적",
        marker_color="#BDBDBD",
        text=[_bar_lbl(v) for v in py_monthly],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=11, color="#444444"),
        offsetgroup=0,
    )
    fig_monthly.add_bar(
        x=months_lbl, y=act_monthly,
        name=f"{year}년 실적",
        marker_color="#00B441",
        text=[_bar_lbl(v) for v in act_monthly],
        textposition="inside",
        insidetextanchor="middle",
        textfont=dict(size=11, color="#FFFFFF"),
        offsetgroup=1,
    )
    fig_monthly.add_scatter(
        x=months_lbl, y=gr_monthly,
        name="YoY 성장률",
        mode="lines+markers+text",
        yaxis="y2",
        line=dict(color="#336DFF", width=2),
        marker=dict(color=gr_marker_colors, size=8),
        text=[f"{v:.1f}%" if v is not None else "" for v in gr_monthly],
        textposition="top center",
        textfont=dict(size=12, color="#282828"),
    )
    fig_monthly.update_layout(
        title=dict(text=f"{year}년 {dtype} 월별 추이 ({VIEW_LABEL[view]})",
                   font=dict(size=14, color="#282828")),
        barmode="group",
        yaxis=dict(ticksuffix="백만", tickformat=",.0f",
                   showgrid=True, gridcolor="#F0F0F0", tickfont=dict(size=11)),
        yaxis2=dict(overlaying="y", side="right", ticksuffix="%",
                    showgrid=False, tickfont=dict(size=11)),
        xaxis=dict(tickfont=dict(size=12)),
        height=480, plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
        legend=dict(orientation="h", xanchor="center", x=0.5,
                    yanchor="top", y=-0.08, font=dict(size=12)),
        margin=dict(t=60, b=80, l=20, r=70),
    )
    st.plotly_chart(fig_monthly, use_container_width=True)
    if dtype == "수주":
        st.markdown(
            "<p style='font-size:13px;font-weight:700;color:#3C3C3C;margin-top:-8px;'>"
            "※ 데이터 기준: ERP 수주일보&nbsp;&nbsp;|&nbsp;&nbsp;"
            "단, &#39;25년 1~3월은 Extra 조정 수치 포함&nbsp;&nbsp;|&nbsp;&nbsp;"
            "&#39;25년 4월부터는 네이버 결제가 수집 기준 변경으로 ERP 수치 적용"
            "</p>",
            unsafe_allow_html=True,
        )
    st.markdown("---")

    # ── 2-A. 목표 대비 달성률 ────────────────────────────────
    st.markdown(f"### {VIEW_LABEL[view]} 목표 대비 달성률")
    if tgt > 0:
        tgt_m = tgt / 1e6
        act_m = act / 1e6
        fig_gauge = go.Figure()
        annual_pct = act / tgt if tgt else None
        act_lbl = (
            f"{act_m:,.0f}백만  ({annual_pct*100:.1f}%)"
            if annual_pct else f"{act_m:,.0f}백만"
        )
        q_cum = {
            "Q1": sum(float(t_s[m]) for m in [1,2,3])         / 1e6,
            "Q2": sum(float(t_s[m]) for m in range(1,7))      / 1e6,
            "Q3": sum(float(t_s[m]) for m in range(1,10))     / 1e6,
            "Q4": sum(float(t_s[m]) for m in range(1,13))     / 1e6,
        }
        fig_gauge.add_bar(
            x=[tgt_m], y=[""], orientation="h",
            name="연간 목표", marker_color="#E0E0E0", width=0.5,
        )
        fig_gauge.add_bar(
            x=[act_m], y=[""], orientation="h",
            name="누적 실적", marker_color="#00B441", width=0.5,
            text=[act_lbl],
            textposition="outside",
            textfont=dict(size=13, color="#00B441"),
        )
        q_shapes, q_annotations = [], []
        for q_name, q_val in q_cum.items():
            if q_val <= 0:
                continue
            q_shapes.append(dict(
                type="line",
                x0=q_val, x1=q_val, y0=-0.5, y1=0.5,
                xref="x", yref="y",
                line=dict(color="#336DFF", width=2, dash="dot"),
            ))
            q_annotations.append(dict(
                x=q_val, y=0.55,
                xref="x", yref="y",
                text=f"<b>{q_name}</b><br>{q_val:,.0f}백만",
                showarrow=False,
                font=dict(size=11, color="#336DFF"),
                align="center",
            ))
        fig_gauge.update_layout(
            barmode="overlay", height=180,
            shapes=q_shapes,
            annotations=q_annotations,
            xaxis=dict(ticksuffix="백만", tickformat=",.0f",
                       range=[0, tgt_m * 1.05], showgrid=False,
                       tickfont=dict(size=11)),
            yaxis=dict(showticklabels=False, range=[-0.6, 1.0]),
            showlegend=True,
            legend=dict(orientation="h", xanchor="center", x=0.5,
                        yanchor="top", y=-0.35, font=dict(size=12)),
            plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
            margin=dict(t=10, b=70, l=10, r=60),
        )
        st.plotly_chart(fig_gauge, use_container_width=True)
    st.markdown("---")

    # ── 2-B. 채널별 실적 비중 ────────────────────────────────
    if view in ("BXM", "B2B"):
        st.markdown(f"### {VIEW_LABEL[view]} 실적 요약")
        m1, m2, _ = st.columns([1, 1, 4])
        m1.metric("YoY 성장률",         fmt_pct(gr))
        m2.metric(f"{year - 1}년 동기", fmt_won(prev))
    else:
        if view == "전체":
            st.markdown("### 채널별 실적 비중")
            if seg_type == "고객 구분":
                donut_labels = ["B2C", "B2B"]
                donut_colors = ["#336DFF", "#282828"]
                _b2c_chs = ["온라인외부몰", "오프라인"]
                act_ch = [
                    sum(float(a.loc[ch, m]) for ch in _b2c_chs for m in range(1, last_act_m + 1)) if last_act_m else 0,
                    sum(float(a.loc["공식몰+MATE", m]) for m in range(1, last_act_m + 1)) if last_act_m else 0,
                ]
                py_ch = [
                    sum(float(py.loc[ch, m]) for ch in _b2c_chs for m in range(1, last_act_m + 1)) if last_act_m else 0,
                    sum(float(py.loc["공식몰+MATE", m]) for m in range(1, last_act_m + 1)) if last_act_m else 0,
                ]
            else:
                donut_chs    = ["온라인외부몰", "오프라인", "공식몰+MATE"]
                donut_labels = ["BXM", "CXM 오프라인", "CXM 공식몰"]
                donut_colors = ["#336DFF", "#282828", "#969696"]
                act_ch = [sum(float(a.loc[ch, m])  for m in range(1, last_act_m + 1)) if last_act_m else 0 for ch in donut_chs]
                py_ch  = [sum(float(py.loc[ch, m]) for m in range(1, last_act_m + 1)) if last_act_m else 0 for ch in donut_chs]
        elif view == "CXM":
            donut_chs    = ["오프라인", "공식몰+MATE"]
            donut_labels = ["오프라인", "공식몰+MATE"]
            donut_colors = ["#282828", "#969696"]
            st.markdown("### CXM 채널별 실적 비중")
            act_ch = [sum(float(a.loc[ch, m])  for m in range(1, last_act_m + 1)) if last_act_m else 0 for ch in donut_chs]
            py_ch  = [sum(float(py.loc[ch, m]) for m in range(1, last_act_m + 1)) if last_act_m else 0 for ch in donut_chs]
        else:  # B2C
            donut_chs    = ["온라인외부몰", "오프라인"]
            donut_labels = ["온라인외부몰", "오프라인"]
            donut_colors = ["#336DFF", "#282828"]
            st.markdown("### B2C 채널별 실적 비중")
            act_ch = [sum(float(a.loc[ch, m])  for m in range(1, last_act_m + 1)) if last_act_m else 0 for ch in donut_chs]
            py_ch  = [sum(float(py.loc[ch, m]) for m in range(1, last_act_m + 1)) if last_act_m else 0 for ch in donut_chs]

        act_tot = sum(act_ch)
        py_tot  = sum(py_ch)

        def _fmt_diff(diff: float) -> str:
            if diff == 0:
                return "±0"
            sign = "+" if diff > 0 else ""
            v = diff / 1e8
            return f"{sign}{v:,.1f}억" if abs(v) < 100 else f"{sign}{v:,.0f}억"

        def _donut(vals, total, title_str, compare_vals=None, compare_total=None):
            if total == 0:
                return None
            pct = [v / total * 100 for v in vals]
            texts = []
            for i in range(len(vals)):
                if compare_vals and compare_total:
                    prev_pct  = compare_vals[i] / compare_total * 100 if compare_total else 0
                    delta     = pct[i] - prev_pct
                    pct_sign  = "+" if delta >= 0 else ""
                    amt_diff  = vals[i] - compare_vals[i]
                    texts.append(
                        f"{donut_labels[i]}<br>{fmt_won(vals[i])} ({_fmt_diff(amt_diff)})<br>"
                        f"{pct[i]:.1f}% ({pct_sign}{delta:.1f}%p)"
                    )
                else:
                    texts.append(
                        f"{donut_labels[i]}<br>{fmt_won(vals[i])}<br>{pct[i]:.1f}%"
                    )
            fig_d = go.Figure(go.Pie(
                labels=donut_labels, values=vals,
                hole=0.55, marker=dict(colors=donut_colors),
                text=texts, textinfo="text",
                textposition="outside",
                insidetextorientation="horizontal",
                textfont=dict(size=12),
                hovertemplate="%{label}: %{value:,.0f}원<extra></extra>",
            ))
            if compare_vals and compare_total:
                diff = total - compare_total
                gr_c = (total - compare_total) / abs(compare_total) * 100 if compare_total else 0
                diff_str = _fmt_diff(diff)
                gr_sign = "+" if gr_c >= 0 else ""
                center_color = "#00B441" if diff >= 0 else "#F72B35"
                center_text = (
                    f"<b>{fmt_won(total)}</b><br>"
                    f"<span style='font-size:11px;color:{center_color}'>"
                    f"{diff_str} ({gr_sign}{gr_c:.1f}%)</span>"
                )
            else:
                center_text = f"<b>{fmt_won(total)}</b>"
                center_color = "#282828"
            fig_d.update_layout(
                title=dict(text=title_str, font=dict(size=14, color="#282828")),
                height=380, showlegend=False,
                annotations=[dict(
                    text=center_text, x=0.5, y=0.5,
                    font=dict(size=14, color="#282828"), showarrow=False,
                )],
                plot_bgcolor="#FFFFFF", paper_bgcolor="#FFFFFF",
                margin=dict(t=50, b=40, l=80, r=80),
            )
            return fig_d

        dc1, dc2 = st.columns(2)
        with dc1:
            fd = _donut(act_ch, act_tot, f"{year}년 YTD",
                        compare_vals=py_ch, compare_total=py_tot)
            if fd:
                st.plotly_chart(fd, use_container_width=True)
            else:
                st.info("실적 데이터 없음")
        with dc2:
            fd2 = _donut(py_ch, py_tot, f"{year - 1}년 동기")
            if fd2:
                st.plotly_chart(fd2, use_container_width=True)
            else:
                st.info("전년 데이터 없음")

    st.markdown("---")

    # ── 3. 월별 상세 테이블 ──────────────────────────────────
    st.markdown(f"### 월별 상세 ({VIEW_LABEL[view]})")
    tgt_row = [float(active_row(t)[m])  for m in range(1, 13)]
    act_row = [float(active_row(a)[m])  for m in range(1, 13)]
    py_row  = [float(active_row(py)[m]) for m in range(1, 13)]

    tbl_data: dict = {"구분": ["목표", "실적", f"{year - 1}년 실적", "달성률", "YoY 성장률"]}
    for i, m in enumerate(range(1, 13)):
        ar_m = act_row[i] / tgt_row[i]              if tgt_row[i]            else None
        gr_m = (act_row[i] - py_row[i]) / abs(py_row[i]) if (act_row[i] > 0 and py_row[i]) else None
        tbl_data[f"{m}월"] = [
            fmt_won(tgt_row[i]),
            fmt_won(act_row[i]),
            fmt_won(py_row[i]),
            fmt_pct(ar_m),
            fmt_pct(gr_m),
        ]
    tgt_sum     = sum(tgt_row)
    act_sum_ytd = sum(act_row[:last_act_m]) if last_act_m else 0
    py_sum_all  = sum(py_row)
    py_sum_ytd  = sum(py_row[:last_act_m])  if last_act_m else 0
    tbl_data["총합"] = [
        fmt_won(tgt_sum),
        fmt_won(act_sum_ytd),
        fmt_won(py_sum_all),
        fmt_pct(act_sum_ytd / tgt_sum if tgt_sum else None),
        fmt_pct((act_sum_ytd - py_sum_ytd) / abs(py_sum_ytd) if py_sum_ytd else None),
    ]

    tbl_df   = pd.DataFrame(tbl_data).set_index("구분")

    def _highlight_total(col):
        if col.name == "총합":
            return ["background-color:#FFF3F3;font-weight:bold;border-left:2px solid #F72B35;"] * len(col)
        return [""] * len(col)

    _show_table(
        tbl_df.style.apply(_highlight_total, axis=0)
    )

    def _style_q(df: pd.DataFrame) -> pd.DataFrame:
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for idx in df.index:
            is_ar = "달성률" in str(idx)
            is_gr = "YoY"    in str(idx)
            if not (is_ar or is_gr):
                continue
            for col in df.columns:
                v_str = str(df.loc[idx, col])
                if v_str == "-":
                    continue
                try:
                    v = float(v_str.replace("%", ""))
                except ValueError:
                    continue
                if is_ar:
                    if v >= 100:
                        styles.loc[idx, col] = "background-color:#E8F5E9;color:#00B441;font-weight:600"
                    elif v >= 90:
                        styles.loc[idx, col] = "background-color:#FFF8E1;color:#F57C00;font-weight:600"
                    else:
                        styles.loc[idx, col] = "background-color:#FFEBEE;color:#F72B35;font-weight:600"
                else:
                    if v >= 0:
                        styles.loc[idx, col] = "color:#00B441;font-weight:600"
                    else:
                        styles.loc[idx, col] = "color:#F72B35;font-weight:600"
        return styles

    with st.expander("분기별 현황 펼치기"):
        q_idx   = ["목표", "실적", "달성률", "YoY 성장률"]
        q_cols  = [q for q, _ in _QUARTERS] + ["연간"]
        q_data  = {c: [] for c in q_cols}
        for q_name, q_months in _QUARTERS:
            q_tgt = sum(tgt_row[m-1] for m in q_months)
            q_act = sum(act_row[m-1] for m in q_months if m <= last_act_m) if last_act_m else 0
            q_py  = sum(py_row[m-1]  for m in q_months)
            q_ar  = q_act / q_tgt      if (q_tgt  and q_act > 0) else None
            q_gr  = (q_act - q_py) / abs(q_py) if (q_act > 0 and q_py) else None
            q_data[q_name] = [fmt_won(q_tgt), fmt_won(q_act), fmt_pct(q_ar), fmt_pct(q_gr)]
        ann_tgt = sum(tgt_row)
        ann_act = sum(act_row[:last_act_m]) if last_act_m else 0
        ann_py  = sum(py_row[:last_act_m])  if last_act_m else 0
        q_data["연간"] = [
            fmt_won(ann_tgt),
            fmt_won(ann_act),
            fmt_pct(ann_act / ytd_tgt if ytd_tgt else None),
            fmt_pct((ann_act - ann_py) / abs(ann_py) if ann_py else None),
        ]
        q_monthly_df = pd.DataFrame(q_data, index=q_idx)
        q_monthly_df.index.name = "구분"
        _show_table(q_monthly_df.style.apply(_style_q, axis=None))
    st.markdown("---")

    # ── 4. 채널별 누적 현황 테이블 ───────────────────────────
    st.markdown(f"### 채널별 누적 현황 ({VIEW_LABEL[view]})")

    if view == "전체":
        if seg_type == "고객 구분":
            tbl_chs = [
                ("사업부 전체",    "_전체"),
                ("B2C",           "_B2C"),
                ("  온라인외부몰", "온라인외부몰"),
                ("  오프라인",     "오프라인"),
                ("B2B",           "공식몰+MATE"),
            ]
        else:
            tbl_chs = [
                ("사업부 전체",   "_전체"),
                ("BXM",          "온라인외부몰"),
                ("CXM",          "_CXM"),
                ("  오프라인",    "오프라인"),
                ("  공식몰+MATE", "공식몰+MATE"),
            ]
    elif view == "BXM":
        tbl_chs = [("BXM", "온라인외부몰")]
    elif view == "CXM":
        tbl_chs = [
            ("CXM",          "_CXM"),
            ("  오프라인",    "오프라인"),
            ("  공식몰+MATE", "공식몰+MATE"),
        ]
    elif view == "B2C":
        tbl_chs = [
            ("B2C",            "_B2C"),
            ("  온라인외부몰", "온라인외부몰"),
            ("  오프라인",     "오프라인"),
        ]
    else:  # B2B
        tbl_chs = [("B2B", "공식몰+MATE")]

    def _get_series(pivot, ch_key):
        if ch_key == "_전체":
            return pivot.loc["합계"]
        elif ch_key == "_CXM":
            return pivot.loc["오프라인"] + pivot.loc["공식몰+MATE"]
        elif ch_key == "_B2C":
            return pivot.loc["온라인외부몰"] + pivot.loc["오프라인"]
        else:
            return pivot.loc[ch_key] if ch_key in pivot.index else pivot.loc["합계"] * 0

    ch_stats = []
    for label, ch in tbl_chs:
        s_a  = _get_series(a,  ch)
        s_t  = _get_series(t,  ch)
        s_py = _get_series(py, ch)

        ch_a_ytd    = sum(float(s_a[m])  for m in range(1, last_act_m + 1)) if last_act_m else 0
        ch_t_annual = float(s_t.sum())
        ch_ytd_tgt  = sum(float(s_t[m])  for m in range(1, last_act_m + 1)) if last_act_m else 0
        ch_py_ytd   = sum(float(s_py[m]) for m in range(1, last_act_m + 1)) if last_act_m else 0
        ch_ar       = ch_a_ytd / ch_t_annual  if ch_t_annual else None
        ch_ar_ytd   = ch_a_ytd / ch_ytd_tgt   if ch_ytd_tgt  else None
        ch_gr = (ch_a_ytd - ch_py_ytd) / abs(ch_py_ytd) if ch_py_ytd else None

        quarters = {}
        for q_name, q_months in _QUARTERS:
            q_tgt = sum(float(s_t[m])  for m in q_months)
            q_act = sum(float(s_a[m])  for m in q_months if m <= last_act_m) if last_act_m else 0
            q_py  = sum(float(s_py[m]) for m in q_months)
            q_ar  = q_act / q_tgt      if (q_tgt and q_act > 0) else None
            q_gr  = (q_act - q_py) / abs(q_py) if (q_act > 0 and q_py) else None
            quarters[q_name] = dict(tgt=q_tgt, act=q_act, py=q_py, ar=q_ar, gr=q_gr)

        ch_stats.append(dict(
            label=label, t_annual=ch_t_annual,
            a_ytd=ch_a_ytd, ytd_tgt=ch_ytd_tgt,
            py_ytd=ch_py_ytd, ar=ch_ar, ar_ytd=ch_ar_ytd, gr=ch_gr,
            quarters=quarters,
        ))

    summary_rows = [{
        "채널":                        s["label"],
        "연간 목표":                   fmt_won(s["t_annual"]),
        f"누적 실적 ({period_lbl})":   fmt_won(s["a_ytd"]),
        f"기간 달성률 ({period_lbl})": fmt_pct(s["ar_ytd"]),
        "연간 달성률":                 fmt_pct(s["ar"]),
        f"YoY 실적 ({period_lbl})":    fmt_won(s["py_ytd"]),
        "YoY 성장률":                  fmt_pct(s["gr"]),
    } for s in ch_stats]

    def _style_summary(df: pd.DataFrame) -> pd.DataFrame:
        styles = pd.DataFrame("", index=df.index, columns=df.columns)
        for col in df.columns:
            is_ar = "달성률" in str(col)
            is_gr = "YoY 성장률" in str(col)
            if not (is_ar or is_gr):
                continue
            for idx in df.index:
                v_str = str(df.loc[idx, col])
                if v_str == "-":
                    continue
                try:
                    v = float(v_str.replace("%", ""))
                except ValueError:
                    continue
                if is_ar:
                    if v >= 100:
                        styles.loc[idx, col] = "background-color:#E8F5E9;color:#00B441;font-weight:600"
                    elif v >= 90:
                        styles.loc[idx, col] = "background-color:#FFF8E1;color:#F57C00;font-weight:600"
                    else:
                        styles.loc[idx, col] = "background-color:#FFEBEE;color:#F72B35;font-weight:600"
                else:
                    if v >= 0:
                        styles.loc[idx, col] = "color:#00B441;font-weight:600"
                    else:
                        styles.loc[idx, col] = "color:#F72B35;font-weight:600"
        return styles

    _show_table(
        pd.DataFrame(summary_rows).set_index("채널").style.apply(_style_summary, axis=None)
    )

    with st.expander("분기별 현황 펼치기"):
        ch_labels = [s["label"] for s in ch_stats]
        row_index, cell_data = [], {lbl: [] for lbl in ch_labels}
        for q_name, _ in _QUARTERS:
            for metric, fmt_fn_key in [("목표","tgt"),("실적","act"),("달성률","ar"),("YoY","gr")]:
                row_index.append(f"{q_name} {metric}")
                for s in ch_stats:
                    q = s["quarters"][q_name]
                    if fmt_fn_key in ("tgt","act"):
                        cell_data[s["label"]].append(fmt_won(q[fmt_fn_key]))
                    else:
                        cell_data[s["label"]].append(fmt_pct(q[fmt_fn_key]))
        q_df = pd.DataFrame(cell_data, index=row_index)
        q_df.index.name = "구분"
        _show_table(q_df.style.apply(_style_q, axis=None))

    st.markdown("---")
    st.markdown(f"### EXTRA 현황 ({dtype})")
    ex_cur  = db.get_extra(year)
    ex_prev = db.get_extra(year - 1)

    def _extra_table(ex_df: pd.DataFrame, label: str):
        if ex_df.empty:
            st.info(f"{label} EXTRA 데이터 없음 (시트 연동 필요)")
            return
        sub = ex_df[ex_df["data_type"] == dtype]
        if sub.empty:
            st.info(f"{label} EXTRA 데이터 없음")
            return
        pvt = sub.pivot_table(index="channel", columns="month",
                              values="amount", aggfunc="sum", fill_value=0)
        pvt = pvt.reindex(columns=range(1, 13), fill_value=0)
        ch_order = [c for c in ["합계", "B2C온라인", "B2C오프라인", "B2B(특판/직판)"] if c in pvt.index]
        pvt = pvt.reindex(ch_order, fill_value=0)
        pvt.columns = [f"{m}월" for m in pvt.columns]
        pvt.insert(0, "합계", pvt.sum(axis=1))
        pvt_fmt = pvt.map(lambda v: f"{v/1e6:+,.0f}백만" if v != 0 else "-")
        _show_table(pvt_fmt.style, caption=label)

    _extra_table(ex_cur,  f"{year}년")
    _extra_table(ex_prev, f"{year - 1}년")

    st.markdown("""
<div style="text-align:center;font-size:13px;color:#969696;margin-top:48px;padding:16px 0;border-top:1px solid #EBEBEB;">
  개발 및 수정문의: DESKER 김선영 &nbsp;|&nbsp; v1.1.0 &nbsp;|&nbsp; 2026-04-22 15:02 KST
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 과거실적
# ══════════════════════════════════════════════════════════════
elif page == "과거실적":
    st.title("과거 실적")
    st.warning("한 번 저장하면 수정·삭제가 불가능합니다. 정확하게 입력해주세요.")
    c1, c2, _ = st.columns([1, 1, 4])
    hist_year = c1.selectbox("과거 연도", [2025, 2024], key="hist_year")
    dtype_h   = c2.selectbox("구분",      DATA_TYPES,         key="hist_dtype")

    locked = db.is_historical_locked(hist_year, dtype_h)

    if locked:
        st.success(f"{hist_year}년 {dtype_h} 실적이 저장되어 있습니다 (수정 불가).")
        hdf = db.get_historical(hist_year)
        if not hdf.empty:
            sub = hdf[hdf["data_type"] == dtype_h]
            if not sub.empty:
                p = sub.pivot_table(
                    index="channel", columns="month",
                    values="amount", fill_value=0,
                )
                p = p.reindex(INPUT_CHANNELS, fill_value=0)
                p.columns = [f"{m}월" for m in p.columns]
                p.insert(0, "연간합계", p.sum(axis=1))
                p.loc["합계"] = p.sum()

                def _style_hist(df):
                    s = pd.DataFrame("", index=df.index, columns=df.columns)
                    s.loc["합계"] = "font-weight:700;background-color:#F5F5F5;"
                    s["연간합계"] = "font-weight:700;background-color:#F0F4FF;color:#336DFF;"
                    s.loc["합계", "연간합계"] = "font-weight:700;background-color:#E8F0FF;color:#336DFF;"
                    return s

                _show_table(p.style.format("{:,.0f}").apply(_style_hist, axis=None))
    else:
        st.markdown(f"**{hist_year}년 {dtype_h} 실적 입력 (단위: 원)**")
        hist_inputs: dict = {ch: {} for ch in INPUT_CHANNELS}

        for ch in INPUT_CHANNELS:
            st.markdown(f"**{ch}**")
            for half, months in [("상반기", range(1, 7)), ("하반기", range(7, 13))]:
                st.caption(half)
                cols = st.columns(6)
                for idx, m in enumerate(months):
                    with cols[idx]:
                        hist_inputs[ch][m] = st.number_input(
                            f"{m}월",
                            min_value=0,
                            value=0,
                            step=1_000_000,
                            format="%d",
                            key=f"hist_{dtype_h}_{ch}_{hist_year}_{m}",
                        )
                fmt_cols = st.columns(6)
                for idx, m in enumerate(months):
                    with fmt_cols[idx]:
                        v = hist_inputs[ch][m]
                        st.caption(f"{v:,}" if v else "-")
            ch_total = sum(hist_inputs[ch][m] for m in range(1, 13))
            st.markdown(
                f"<div style='text-align:right;font-size:13px;color:#336DFF;font-weight:700;"
                f"padding:4px 8px;background:#F0F4FF;border-radius:4px;margin-bottom:12px;'>"
                f"연간 합계: {ch_total:,}원 &nbsp;({ch_total/1e8:,.2f}억)</div>",
                unsafe_allow_html=True,
            )

        if st.button(
            "저장 (이후 수정 불가)",
            type="primary",
            use_container_width=True,
            key="save_hist",
        ):
            records = [
                {
                    "data_type": dtype_h,
                    "channel":   ch,
                    "year":      hist_year,
                    "month":     m,
                    "amount":    hist_inputs[ch][m],
                }
                for ch in INPUT_CHANNELS
                for m in range(1, 13)
            ]
            db.insert_historical_bulk(records)
            st.success(f"{hist_year}년 {dtype_h} 과거 실적이 저장되었습니다.")
            st.rerun()

    st.markdown("""
<div style="text-align:center;font-size:13px;color:#969696;margin-top:48px;padding:16px 0;border-top:1px solid #EBEBEB;">
  개발 및 수정문의: DESKER 김선영 &nbsp;|&nbsp; v1.1.0 &nbsp;|&nbsp; 2026-04-22 15:02 KST
</div>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════
# 설정
# ══════════════════════════════════════════════════════════════
elif page == "설정":
    st.title("설정")
    st.info("연초에 한 번 설정합니다. 이후에도 수정할 수 있습니다.")
    c1, c2, _ = st.columns([1, 1, 4])
    year_t  = c1.selectbox("연도", range(CY, CY - 4, -1), key="tgt_year")
    dtype_t = c2.selectbox("구분", DATA_TYPES,             key="tgt_dtype")

    tdf = db.get_targets(year_t)

    def get_existing_target(ch: str, m: int) -> int:
        if tdf.empty:
            return 0
        sub = tdf[
            (tdf["data_type"] == dtype_t) &
            (tdf["channel"]   == ch) &
            (tdf["month"]     == m)
        ]
        return int(sub["amount"].values[0]) if not sub.empty else 0

    st.markdown(f"**{year_t}년 {dtype_t} 목표 입력 (단위: 원, 100백만 원 단위)**")
    all_inputs: dict = {ch: {} for ch in INPUT_CHANNELS}

    for ch in INPUT_CHANNELS:
        st.markdown(f"**{ch}**")
        for half, months in [("상반기", range(1, 7)), ("하반기", range(7, 13))]:
            st.caption(half)
            cols = st.columns(6)
            for idx, m in enumerate(months):
                with cols[idx]:
                    all_inputs[ch][m] = st.number_input(
                        f"{m}월",
                        min_value=0,
                        value=get_existing_target(ch, m),
                        step=100_000_000,
                        format="%d",
                        key=f"tgt_{dtype_t}_{ch}_{year_t}_{m}",
                    )
            fmt_cols = st.columns(6)
            for idx, m in enumerate(months):
                with fmt_cols[idx]:
                    v = all_inputs[ch][m]
                    st.caption(f"{v:,}" if v else "-")
        ch_total = sum(all_inputs[ch][m] for m in range(1, 13))
        st.markdown(
            f"<div style='text-align:right;font-size:13px;color:#336DFF;font-weight:700;"
            f"padding:4px 8px;background:#F0F4FF;border-radius:4px;margin-bottom:12px;'>"
            f"연간 합계: {ch_total:,}원 &nbsp;({ch_total/1e8:,.2f}억)</div>",
            unsafe_allow_html=True,
        )

    if st.button("목표 저장", type="primary", use_container_width=True, key="save_tgt"):
        for ch in INPUT_CHANNELS:
            for m in range(1, 13):
                db.upsert_target(dtype_t, ch, year_t, m, all_inputs[ch][m])
        st.success(f"{year_t}년 {dtype_t} 목표가 저장되었습니다.")

    st.markdown("""
<div style="text-align:center;font-size:13px;color:#969696;margin-top:48px;padding:16px 0;border-top:1px solid #EBEBEB;">
  개발 및 수정문의: DESKER 김선영 &nbsp;|&nbsp; v1.1.0 &nbsp;|&nbsp; 2026-04-22 15:02 KST
</div>
""", unsafe_allow_html=True)
