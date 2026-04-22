import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sheets_bxm
import streamlit as st
from datetime import datetime, timedelta


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

if not st.session_state.get("auth"):
    _, mid, _ = st.columns([1, 1.5, 1])
    with mid:
        st.markdown("## DESKER BXM")
        st.markdown("### 온라인 수주/매출 현황")
        st.markdown("---")
        pwd = st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요")
        if st.button("로그인", use_container_width=True, type="primary", key="bxm_login"):
            if pwd == st.secrets["app"]["password"]:
                st.session_state.auth = True
                st.session_state.login_time = datetime.now()
                st.rerun()
            else:
                st.error("비밀번호가 올바르지 않습니다.")
    st.markdown("""
<div style="text-align:center;font-size:13px;color:#969696;margin-top:48px;padding:16px 0;border-top:1px solid #EBEBEB;">
  개발 및 수정문의: DESKER 김선영 &nbsp;|&nbsp; v1.1.0 &nbsp;|&nbsp; 2026-04-22 KST
</div>
""", unsafe_allow_html=True)
    st.stop()

_SESSION_TIMEOUT = timedelta(minutes=15)
_login_time = st.session_state.get("login_time")
if _login_time and (datetime.now() - _login_time) > _SESSION_TIMEOUT:
    st.session_state.auth = False
    st.session_state.pop("login_time", None)
    st.session_state.pop("bxm_data", None)
    st.warning("세션이 만료되었습니다. 다시 로그인해주세요.")
    st.rerun()

def fmt_won(n):
    if n is None or n == 0:
        return "-"
    v = n / 1e8
    return f"{v:,.1f}억"

def fmt_pct(r):
    if r is None:
        return "-"
    return f"{r * 100:.1f}%"

def fmt_pct_signed(r):
    if r is None:
        return "-"
    sign = "+" if r >= 0 else ""
    return f"{sign}{r * 100:.1f}%"

def fmt_extra(v):
    if v is None or v == 0:
        return "-"
    return f"{v/1e6:+,.0f}백만"

def _show_table(html):
    st.html(f'<div style="overflow-x:auto">{html}</div>')

def _build_html_monthly(rows):
    month_headers = [f"{m}월" for m in range(1, 13)] + ["합계"]
    html_rows = []
    for metric, values in rows:
        is_ar = metric == "달성률"
        is_gr = metric == "성장률(YOY)"
        row_html = f"<tr><td style='padding:8px 12px;text-align:center;font-weight:600;white-space:nowrap;'>{metric}</td>"
        for val in values:
            cell_style = "padding:8px 12px;text-align:center;"
            if (is_ar or is_gr) and val != "-":
                try:
                    num_val = float(val.replace("%", ""))
                    if is_ar:
                        if num_val >= 100:
                            cell_style += "background:#E8F5E9;color:#00B441;font-weight:600;"
                        elif num_val >= 90:
                            cell_style += "background:#FFF8E1;color:#F57C00;font-weight:600;"
                        else:
                            cell_style += "background:#FFEBEE;color:#F72B35;font-weight:600;"
                    else:
                        cell_style += f"color:{'#00B441' if num_val >= 0 else '#F72B35'};font-weight:600;"
                except:
                    pass
            row_html += f"<td style='{cell_style}'>{val}</td>"
        row_html += "</tr>"
        html_rows.append(row_html)
    return f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
            <tr style="background:#F5F5F5;font-weight:600;">
                <th style="padding:8px 12px;text-align:center;">지표</th>
                {''.join(f"<th style='padding:8px 12px;text-align:center;'>{h}</th>" for h in month_headers)}
            </tr>
        </thead>
        <tbody>{''.join(html_rows)}</tbody>
    </table>
    """

def _render_kpi(df, idx, actual_metric, target_metric, yoy_metric):
    act_vals = sheets_bxm.get_values(df, idx, "온라인합계", actual_metric)
    tgt_vals = sheets_bxm.get_values(df, idx, "온라인합계", target_metric)
    yoy_vals = sheets_bxm.get_values(df, idx, "온라인합계", yoy_metric)

    if not act_vals:
        return None, None

    last_act_m = 0
    for m in range(1, 13):
        if act_vals[f"m{m}"] and act_vals[f"m{m}"] > 0:
            last_act_m = m

    if last_act_m == 0:
        return None, None

    tgt_annual = sum(tgt_vals[f"m{m}"] for m in range(1, 13) if tgt_vals[f"m{m}"]) if tgt_vals else None
    ytd_tgt = 0
    ytd_act = 0
    ytd_yoy = 0

    if tgt_vals:
        for m in range(1, last_act_m + 1):
            if tgt_vals[f"m{m}"]:
                ytd_tgt += tgt_vals[f"m{m}"]

    for m in range(1, last_act_m + 1):
        if act_vals[f"m{m}"]:
            ytd_act += act_vals[f"m{m}"]

    if yoy_vals:
        for m in range(1, last_act_m + 1):
            if yoy_vals[f"m{m}"]:
                ytd_yoy += yoy_vals[f"m{m}"]

    ar = ytd_act / ytd_tgt if ytd_tgt else None
    gr = (ytd_act - ytd_yoy) / abs(ytd_yoy) if ytd_yoy else None

    period_lbl = f"1~{last_act_m}월"

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("연간 목표", fmt_won(tgt_annual))
    k2.metric(f"실적 목표 ({period_lbl})", fmt_won(ytd_tgt))
    k3.metric(f"누적 실적 ({period_lbl})", fmt_won(ytd_act))
    k4.metric("달성률", fmt_pct(ar))
    k5.metric(f"YoY 실적 ({period_lbl})", fmt_won(ytd_yoy))
    k6.metric(f"YoY 성장률 ({period_lbl})", fmt_pct(gr))

    return last_act_m, period_lbl

with st.sidebar:
    st.markdown("## DESKER 월별마감")
    st.markdown("---")
    page = st.radio("메뉴", ["대시보드", "과거실적"], label_visibility="collapsed")
    st.markdown("---")

    st.markdown("**Google Sheets 연동**")
    if st.button("BXM 시트연동 새로고침", use_container_width=True):
        st.session_state.pop("bxm_data", None)
        st.rerun()

    bxm_url = "https://docs.google.com/spreadsheets/d/14vEttvIlz-0R1fWqze3UjAQAUwpINI3Z"
    st.markdown(f'<a href="{bxm_url}" target="_blank" style="font-size:12px;color:#336DFF;">연동 시트 열기</a>', unsafe_allow_html=True)

    last_load = st.session_state.get("bxm_load_time")
    if last_load:
        st.caption(f"최종 로드: {last_load}")

    st.markdown("---")
    if st.button("로그아웃", use_container_width=True):
        st.session_state.auth = False
        st.session_state.pop("login_time", None)
        st.session_state.pop("bxm_data", None)
        st.rerun()

if not st.session_state.get("bxm_data"):
    st.markdown("<br>" * 3, unsafe_allow_html=True)
    _, gate_col, _ = st.columns([1, 1.6, 1])
    with gate_col:
        st.markdown(
            "<div style='text-align:center;padding:40px 32px;background:#F5F5F5;"
            "border-radius:8px;border:1px solid #E0E0E0;'>"
            "<div style='font-size:36px;margin-bottom:12px;'>📊</div>"
            "<div style='font-size:18px;font-weight:700;color:#282828;margin-bottom:8px;'>"
            "데이터 연동이 필요합니다</div>"
            "<div style='font-size:13px;color:#666666;margin-bottom:0px;'>"
            "최신 데이터를 불러오려면 Google Sheets 연동을 실행해주세요.</div>"
            "</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<div style='height:12px'></div>", unsafe_allow_html=True)
        if st.button("시트 연동하기", use_container_width=True, type="primary", key="bxm_gate_sync"):
            with st.spinner("데이터를 가져오는 중..."):
                try:
                    orders_data = sheets_bxm.load_orders()
                    sales_data = sheets_bxm.load_sales()
                    channels = sheets_bxm.load_channel_config()
                    st.session_state.bxm_data = {
                        "orders": orders_data,
                        "sales": sales_data,
                        "channels": channels,
                    }
                    st.session_state.bxm_load_time = datetime.now().strftime("%Y-%m-%d %H:%M")
                    st.rerun()
                except Exception as e:
                    st.error(f"데이터 로드 실패: {str(e)}")
    st.stop()

bxm_data = st.session_state.bxm_data
orders_df, orders_idx = bxm_data["orders"]
sales_df, sales_idx = bxm_data["sales"]
channels = bxm_data["channels"]

if page == "과거실적":
    st.title("과거 실적 (25년)")
    tab_ord_h, tab_sal_h = st.tabs(["수주", "매출"])

    with tab_ord_h:
        st.markdown("### 25년 수주 실적")
        past_rows = []
        for ch_cfg in channels:
            ch_name = ch_cfg["채널명"]
            yoy_v = sheets_bxm.get_values(orders_df, orders_idx, ch_name, "25년 동기")
            if yoy_v:
                total = sum(yoy_v[f"m{m}"] for m in range(1, 13) if yoy_v[f"m{m}"])
                row_vals = [fmt_won(total)] + [fmt_won(yoy_v[f"m{m}"]) for m in range(1, 13)]
                past_rows.append((ch_name, row_vals))
        if past_rows:
            past_headers = ["연간합계"] + [f"{m}월" for m in range(1, 13)]
            html_past_rows = []
            for ch_name, values in past_rows:
                row_html = f"<tr><td style='padding:8px 12px;text-align:center;font-weight:600;white-space:nowrap;'>{ch_name}</td>"
                for val in values:
                    row_html += f"<td style='padding:8px 12px;text-align:center;'>{val}</td>"
                row_html += "</tr>"
                html_past_rows.append(row_html)
            html_past = (
                "<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
                "<thead><tr style='background:#F5F5F5;font-weight:600;'>"
                "<th style='padding:8px 12px;text-align:center;'>채널</th>"
                + "".join(f"<th style='padding:8px 12px;text-align:center;'>{h}</th>" for h in past_headers)
                + "</tr></thead><tbody>"
                + "".join(html_past_rows)
                + "</tbody></table>"
            )
            _show_table(html_past)
        else:
            st.info("25년 수주 데이터 없음")

    with tab_sal_h:
        st.markdown("### 25년 매출 실적")
        past_rows = []
        for ch_cfg in channels:
            ch_name = ch_cfg["채널명"]
            yoy_v = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "25년 동기")
            if yoy_v:
                total = sum(yoy_v[f"m{m}"] for m in range(1, 13) if yoy_v[f"m{m}"])
                row_vals = [fmt_won(total)] + [fmt_won(yoy_v[f"m{m}"]) for m in range(1, 13)]
                past_rows.append((ch_name, row_vals))
        if past_rows:
            past_headers = ["연간합계"] + [f"{m}월" for m in range(1, 13)]
            html_past_rows = []
            for ch_name, values in past_rows:
                row_html = f"<tr><td style='padding:8px 12px;text-align:center;font-weight:600;white-space:nowrap;'>{ch_name}</td>"
                for val in values:
                    row_html += f"<td style='padding:8px 12px;text-align:center;'>{val}</td>"
                row_html += "</tr>"
                html_past_rows.append(row_html)
            html_past = (
                "<table style='width:100%;border-collapse:collapse;font-size:13px;'>"
                "<thead><tr style='background:#F5F5F5;font-weight:600;'>"
                "<th style='padding:8px 12px;text-align:center;'>채널</th>"
                + "".join(f"<th style='padding:8px 12px;text-align:center;'>{h}</th>" for h in past_headers)
                + "</tr></thead><tbody>"
                + "".join(html_past_rows)
                + "</tbody></table>"
            )
            _show_table(html_past)
        else:
            st.info("25년 매출 데이터 없음")

    st.markdown("""
<div style="text-align:center;font-size:13px;color:#969696;margin-top:48px;padding:16px 0;border-top:1px solid #EBEBEB;">
  개발 및 수정문의: DESKER 김선영 &nbsp;|&nbsp; v1.1.0 &nbsp;|&nbsp; 2026-04-22 KST
</div>
""", unsafe_allow_html=True)
    st.stop()

st.title("2026년 BXM 온라인 수주/매출 현황")

tab_orders, tab_sales = st.tabs(["수주", "매출"])

with tab_orders:
    st.markdown("### 수주 KPI")
    _render_kpi(orders_df, orders_idx, "수주액", "목표", "25년 동기")
    st.markdown("---")

    st.markdown("### 채널별 현황")

    def get_last_month_with_data(df, idx, metric):
        last_m = 0
        for ch_cfg in channels:
            ch_name = ch_cfg["채널명"]
            vals = sheets_bxm.get_values(df, idx, ch_name, metric)
            if vals:
                for m in range(1, 13):
                    if vals[f"m{m}"] and vals[f"m{m}"] > 0:
                        last_m = m
        return last_m

    last_m = get_last_month_with_data(orders_df, orders_idx, "수주액")
    period_lbl = f"1~{last_m}월" if last_m else "-"

    table_rows = []
    for ch_cfg in channels:
        ch_name = ch_cfg["채널명"]
        pm = ch_cfg["PM"]
        has_target = ch_cfg["목표여부"] == "Y"

        act_vals = sheets_bxm.get_values(orders_df, orders_idx, ch_name, "수주액")
        yoy_vals = sheets_bxm.get_values(orders_df, orders_idx, ch_name, "25년 동기")
        tgt_vals = sheets_bxm.get_values(orders_df, orders_idx, ch_name, "목표") if has_target else None

        tgt_annual = sum(tgt_vals[f"m{m}"] for m in range(1, 13) if tgt_vals[f"m{m}"]) if tgt_vals else None
        ytd_act = sum(act_vals[f"m{m}"] for m in range(1, last_m + 1) if act_vals[f"m{m}"]) if act_vals and last_m else 0
        ytd_yoy = sum(yoy_vals[f"m{m}"] for m in range(1, last_m + 1) if yoy_vals[f"m{m}"]) if yoy_vals and last_m else 0
        ytd_tgt = sum(tgt_vals[f"m{m}"] for m in range(1, last_m + 1) if tgt_vals[f"m{m}"]) if tgt_vals and last_m else 0

        gr = (ytd_act - ytd_yoy) / abs(ytd_yoy) if ytd_yoy else None
        ar = ytd_act / ytd_tgt if (has_target and ytd_tgt) else None

        gr_color = "#00B441" if (gr is not None and gr >= 0) else "#F72B35"

        ar_str = fmt_pct(ar) if ar is not None else "-"
        if ar is not None:
            if ar >= 1.0:
                ar_bg = "#E8F5E9"
                ar_color = "#00B441"
            elif ar >= 0.9:
                ar_bg = "#FFF8E1"
                ar_color = "#F57C00"
            else:
                ar_bg = "#FFEBEE"
                ar_color = "#F72B35"
        else:
            ar_bg = "#FFFFFF"
            ar_color = "#282828"

        table_rows.append({
            "ch_name": ch_name,
            "pm": pm,
            "tgt_annual": fmt_won(tgt_annual) if has_target else "-",
            "ytd_tgt": fmt_won(ytd_tgt) if has_target else "-",
            "ytd_act": fmt_won(ytd_act),
            "ytd_yoy": fmt_won(ytd_yoy),
            "gr_str": fmt_pct(gr),
            "gr_color": gr_color,
            "ar_str": ar_str,
            "ar_bg": ar_bg,
            "ar_color": ar_color,
        })

    html_rows = []
    for row in table_rows:
        html_rows.append(f"""
        <tr>
            <td style="padding:8px 12px;text-align:center;">{row['ch_name']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['pm']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['tgt_annual']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['ytd_tgt']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['ytd_act']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['ytd_yoy']}</td>
            <td style="padding:8px 12px;text-align:center;color:{row['gr_color']};font-weight:600;">{row['gr_str']}</td>
            <td style="padding:8px 12px;text-align:center;background:{row['ar_bg']};color:{row['ar_color']};font-weight:600;">{row['ar_str']}</td>
        </tr>
        """)

    html_table = f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
            <tr style="background:#F5F5F5;font-weight:600;">
                <th style="padding:8px 12px;text-align:center;">채널</th>
                <th style="padding:8px 12px;text-align:center;">PM</th>
                <th style="padding:8px 12px;text-align:center;">전체 목표</th>
                <th style="padding:8px 12px;text-align:center;">YTD 목표</th>
                <th style="padding:8px 12px;text-align:center;">YTD 실적</th>
                <th style="padding:8px 12px;text-align:center;">전년 동기</th>
                <th style="padding:8px 12px;text-align:center;">YoY 성장률</th>
                <th style="padding:8px 12px;text-align:center;">달성률</th>
            </tr>
        </thead>
        <tbody>
            {''.join(html_rows)}
        </tbody>
    </table>
    """
    _show_table(html_table)
    st.markdown("---")

    st.markdown("### 월별 상세")

    def _orders_monthly_html(ch_name, has_target):
        tgt_v = sheets_bxm.get_values(orders_df, orders_idx, ch_name, "목표") if has_target else None
        act_v = sheets_bxm.get_values(orders_df, orders_idx, ch_name, "수주액")
        yoy_v = sheets_bxm.get_values(orders_df, orders_idx, ch_name, "25년 동기")
        rows = []
        if has_target and tgt_v:
            rows.append(("목표", [fmt_won(tgt_v[f"m{m}"]) for m in range(1, 13)] + [fmt_won(tgt_v["합계"])]))
        if act_v:
            rows.append(("수주액", [fmt_won(act_v[f"m{m}"]) for m in range(1, 13)] + [fmt_won(act_v["합계"])]))
        if has_target and tgt_v and act_v:
            ar_row = [fmt_pct(act_v[f"m{m}"] / tgt_v[f"m{m}"] if (act_v[f"m{m}"] and tgt_v[f"m{m}"]) else None) for m in range(1, 13)]
            ar_row.append(fmt_pct(act_v["합계"] / tgt_v["합계"] if (act_v["합계"] and tgt_v["합계"]) else None))
            rows.append(("달성률", ar_row))
        elif has_target:
            rows.append(("달성률", ["-"] * 13))
        if act_v and yoy_v:
            gr_row = [fmt_pct_signed((act_v[f"m{m}"] - yoy_v[f"m{m}"]) / abs(yoy_v[f"m{m}"]) if (act_v[f"m{m}"] is not None and yoy_v[f"m{m}"]) else None) for m in range(1, 13)]
            a_s = sum(act_v[f"m{m}"] for m in range(1, last_m + 1) if act_v[f"m{m}"]) if last_m else None
            y_s = sum(yoy_v[f"m{m}"] for m in range(1, last_m + 1) if yoy_v[f"m{m}"]) if last_m else None
            gr_row.append(fmt_pct_signed((a_s - y_s) / abs(y_s) if (a_s is not None and y_s) else None))
            rows.append(("성장률(YOY)", gr_row))
        if yoy_v:
            rows.append(("25년 동기", [fmt_won(yoy_v[f"m{m}"]) for m in range(1, 13)] + [fmt_won(yoy_v["합계"])]))
        return _build_html_monthly(rows)

    st.markdown("**온라인합계**")
    _show_table(_orders_monthly_html("온라인합계", True))

    with st.expander("채널별로 보기"):
        for ch_cfg in channels:
            ch_name = ch_cfg["채널명"]
            if ch_name == "온라인합계":
                continue
            has_tgt = ch_cfg["목표여부"] == "Y"
            st.markdown(f"**{ch_name}**")
            _show_table(_orders_monthly_html(ch_name, has_tgt))

with tab_sales:
    st.markdown("### 매출 KPI")
    _render_kpi(sales_df, sales_idx, "매출액", "목표", "25년 동기")
    st.markdown("---")

    st.markdown("### 채널별 현황")

    last_m = get_last_month_with_data(sales_df, sales_idx, "매출액")
    period_lbl = f"1~{last_m}월" if last_m else "-"

    table_rows = []
    for ch_cfg in channels:
        ch_name = ch_cfg["채널명"]
        pm = ch_cfg["PM"]
        has_target = ch_cfg["목표여부"] == "Y"

        act_vals = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "매출액")
        ext_vals = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "엑스트라")
        yoy_vals = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "25년 동기")
        tgt_vals = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "목표") if has_target else None

        tgt_annual = sum(tgt_vals[f"m{m}"] for m in range(1, 13) if tgt_vals[f"m{m}"]) if tgt_vals else None
        ytd_act = sum(act_vals[f"m{m}"] for m in range(1, last_m + 1) if act_vals[f"m{m}"]) if act_vals and last_m else 0
        ytd_ext = sum(ext_vals[f"m{m}"] for m in range(1, last_m + 1) if ext_vals[f"m{m}"]) if ext_vals and last_m else 0
        ytd_yoy = sum(yoy_vals[f"m{m}"] for m in range(1, last_m + 1) if yoy_vals[f"m{m}"]) if yoy_vals and last_m else 0
        ytd_tgt = sum(tgt_vals[f"m{m}"] for m in range(1, last_m + 1) if tgt_vals[f"m{m}"]) if tgt_vals and last_m else 0

        gr = (ytd_act - ytd_yoy) / abs(ytd_yoy) if ytd_yoy else None
        ar = ytd_act / ytd_tgt if (has_target and ytd_tgt) else None

        gr_color = "#00B441" if (gr is not None and gr >= 0) else "#F72B35"

        ar_str = fmt_pct(ar) if ar is not None else "-"
        if ar is not None:
            if ar >= 1.0:
                ar_bg = "#E8F5E9"
                ar_color = "#00B441"
            elif ar >= 0.9:
                ar_bg = "#FFF8E1"
                ar_color = "#F57C00"
            else:
                ar_bg = "#FFEBEE"
                ar_color = "#F72B35"
        else:
            ar_bg = "#FFFFFF"
            ar_color = "#282828"

        table_rows.append({
            "ch_name": ch_name,
            "pm": pm,
            "tgt_annual": fmt_won(tgt_annual) if has_target else "-",
            "ytd_tgt": fmt_won(ytd_tgt) if has_target else "-",
            "ytd_act": fmt_won(ytd_act),
            "ytd_ext": fmt_won(ytd_ext),
            "ytd_yoy": fmt_won(ytd_yoy),
            "gr_str": fmt_pct(gr),
            "gr_color": gr_color,
            "ar_str": ar_str,
            "ar_bg": ar_bg,
            "ar_color": ar_color,
        })

    html_rows = []
    for row in table_rows:
        html_rows.append(f"""
        <tr>
            <td style="padding:8px 12px;text-align:center;">{row['ch_name']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['pm']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['tgt_annual']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['ytd_tgt']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['ytd_act']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['ytd_ext']}</td>
            <td style="padding:8px 12px;text-align:center;">{row['ytd_yoy']}</td>
            <td style="padding:8px 12px;text-align:center;color:{row['gr_color']};font-weight:600;">{row['gr_str']}</td>
            <td style="padding:8px 12px;text-align:center;background:{row['ar_bg']};color:{row['ar_color']};font-weight:600;">{row['ar_str']}</td>
        </tr>
        """)

    html_table = f"""
    <table style="width:100%;border-collapse:collapse;font-size:13px;">
        <thead>
            <tr style="background:#F5F5F5;font-weight:600;">
                <th style="padding:8px 12px;text-align:center;">채널</th>
                <th style="padding:8px 12px;text-align:center;">PM</th>
                <th style="padding:8px 12px;text-align:center;">전체 목표</th>
                <th style="padding:8px 12px;text-align:center;">YTD 목표</th>
                <th style="padding:8px 12px;text-align:center;">YTD 실적</th>
                <th style="padding:8px 12px;text-align:center;">YTD 엑스트라</th>
                <th style="padding:8px 12px;text-align:center;">전년 동기</th>
                <th style="padding:8px 12px;text-align:center;">YoY 성장률</th>
                <th style="padding:8px 12px;text-align:center;">달성률</th>
            </tr>
        </thead>
        <tbody>
            {''.join(html_rows)}
        </tbody>
    </table>
    """
    _show_table(html_table)
    st.markdown("---")

    st.markdown("### 월별 상세")

    def _sales_monthly_html(ch_name, has_target):
        tgt_v = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "목표") if has_target else None
        act_v = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "매출액")
        ext_v = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "엑스트라")
        yoy_v = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "25년 동기")
        yoy_ext_v = sheets_bxm.get_values(sales_df, sales_idx, ch_name, "25년 엑스트라")
        rows = []
        if has_target and tgt_v:
            rows.append(("목표", [fmt_won(tgt_v[f"m{m}"]) for m in range(1, 13)] + [fmt_won(tgt_v["합계"])]))
        if act_v:
            rows.append(("매출액", [fmt_won(act_v[f"m{m}"]) for m in range(1, 13)] + [fmt_won(act_v["합계"])]))
        if ext_v:
            rows.append(("엑스트라", [fmt_extra(ext_v[f"m{m}"]) for m in range(1, 13)] + [fmt_extra(ext_v["합계"])]))
        if has_target and tgt_v and act_v:
            ar_row = [fmt_pct(act_v[f"m{m}"] / tgt_v[f"m{m}"] if (act_v[f"m{m}"] and tgt_v[f"m{m}"]) else None) for m in range(1, 13)]
            ar_row.append(fmt_pct(act_v["합계"] / tgt_v["합계"] if (act_v["합계"] and tgt_v["합계"]) else None))
            rows.append(("달성률", ar_row))
        elif has_target:
            rows.append(("달성률", ["-"] * 13))
        if act_v and yoy_v:
            gr_row = [fmt_pct_signed((act_v[f"m{m}"] - yoy_v[f"m{m}"]) / abs(yoy_v[f"m{m}"]) if (act_v[f"m{m}"] is not None and yoy_v[f"m{m}"]) else None) for m in range(1, 13)]
            a_s = sum(act_v[f"m{m}"] for m in range(1, last_m + 1) if act_v[f"m{m}"]) if last_m else None
            y_s = sum(yoy_v[f"m{m}"] for m in range(1, last_m + 1) if yoy_v[f"m{m}"]) if last_m else None
            gr_row.append(fmt_pct_signed((a_s - y_s) / abs(y_s) if (a_s is not None and y_s) else None))
            rows.append(("성장률(YOY)", gr_row))
        if yoy_v:
            rows.append(("25년 동기", [fmt_won(yoy_v[f"m{m}"]) for m in range(1, 13)] + [fmt_won(yoy_v["합계"])]))
        if yoy_ext_v:
            rows.append(("25년 엑스트라", [fmt_extra(yoy_ext_v[f"m{m}"]) for m in range(1, 13)] + [fmt_extra(yoy_ext_v["합계"])]))
        return _build_html_monthly(rows)

    st.markdown("**온라인합계**")
    _show_table(_sales_monthly_html("온라인합계", True))

    with st.expander("채널별로 보기"):
        for ch_cfg in channels:
            ch_name = ch_cfg["채널명"]
            if ch_name == "온라인합계":
                continue
            has_tgt = ch_cfg["목표여부"] == "Y"
            st.markdown(f"**{ch_name}**")
            _show_table(_sales_monthly_html(ch_name, has_tgt))

    st.markdown("---")
    st.markdown("### EXTRA 요약")

    extra_data_26 = sheets_bxm.get_values(sales_df, sales_idx, "온라인합계", "엑스트라")
    extra_data_25 = sheets_bxm.get_values(sales_df, sales_idx, "온라인합계", "25년 엑스트라")

    extra_rows = []
    if extra_data_26:
        extra_row_26 = [fmt_extra(extra_data_26["합계"])] + [fmt_extra(extra_data_26[f"m{m}"]) for m in range(1, 13)]
        extra_rows.append(("26년 EXTRA", extra_row_26))

    if extra_data_25:
        extra_row_25 = [fmt_extra(extra_data_25["합계"])] + [fmt_extra(extra_data_25[f"m{m}"]) for m in range(1, 13)]
        extra_rows.append(("25년 EXTRA", extra_row_25))

    if extra_rows:
        extra_headers = ["합계"] + [f"{m}월" for m in range(1, 13)]
        html_extra_rows = []
        for metric, values in extra_rows:
            row_html = f"<tr><td style='padding:8px 12px;text-align:center;font-weight:600;'>{metric}</td>"
            for val in values:
                row_html += f"<td style='padding:8px 12px;text-align:center;'>{val}</td>"
            row_html += "</tr>"
            html_extra_rows.append(row_html)

        html_extra = f"""
        <table style="width:100%;border-collapse:collapse;font-size:13px;">
            <thead>
                <tr style="background:#F5F5F5;font-weight:600;">
                    <th style="padding:8px 12px;text-align:center;">항목</th>
                    {''.join(f"<th style='padding:8px 12px;text-align:center;'>{h}</th>" for h in extra_headers)}
                </tr>
            </thead>
            <tbody>
                {''.join(html_extra_rows)}
            </tbody>
        </table>
        """
        _show_table(html_extra)

st.markdown("""
<div style="text-align:center;font-size:13px;color:#969696;margin-top:48px;padding:16px 0;border-top:1px solid #EBEBEB;">
  개발 및 수정문의: DESKER 김선영 &nbsp;|&nbsp; v1.1.0 &nbsp;|&nbsp; 2026-04-22 KST
</div>
""", unsafe_allow_html=True)
