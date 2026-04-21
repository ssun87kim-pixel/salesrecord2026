# sheets.py  ─  Google Sheets CSV 연동 (읽기 전용)
#               secrets.toml [sheets] 섹션 필요
#               시트는 공개(뷰어) 공유 상태여야 합니다
import io
import streamlit as st
import pandas as pd
import db

# ── 시트 구조 상수 (load_sample.py 와 동일) ───────────────────
# 채널별 행 번호 (0-based): (목표행, 실적행, 2025년행, 2024년행)
_CHANNEL_ROWS = {
    "온라인외부몰": (10, 11, 14, 15),
    "오프라인":     (16, 17, 20, 21),
    "공식몰+MATE":  (28, 29, 32, 33),
}
_COL_OFFSET = 3   # col 3 = 1월, col 4 = 2월, ..., col 14 = 12월
_MONTHS     = list(range(1, 13))

# 고객수 행 번호 (0-based): {channel: (2026_row, 2025_row)}
_CUSTOMER_ROWS = {
    "외부몰":      (66, 67),
    "매장":        (68, 69),
    "DESKERS":     (70, 71),
    "BIZ DESKERS": (72, 73),
}

# EXTRA 행 번호 (0-based): {year: {channel: row_index}}
_EXTRA_ROWS = {
    2026: {
        "합계":          38,
        "B2C온라인":     39,
        "B2C오프라인":   40,
        "B2B(특판/직판)": 41,
    },
    2025: {
        "합계":          45,
        "B2C온라인":     46,
        "B2C오프라인":   47,
        "B2B(특판/직판)": 48,
    },
}


# ── 내부 헬퍼 ─────────────────────────────────────────────────

def _csv_url(gid: str) -> str:
    sid = st.secrets["sheets"]["spreadsheet_id"]
    return (
        f"https://docs.google.com/spreadsheets/d/{sid}"
        f"/export?format=csv&gid={gid}"
    )


def _safe_int(val) -> int:
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return 0
        return int(float(str(val).replace(",", "").replace(" ", "")))
    except (ValueError, TypeError):
        return 0


def _parse_extra(df: pd.DataFrame, data_type: str) -> list:
    """EXTRA 행을 파싱해 레코드 리스트 반환 (amount는 음수 가능)"""
    records = []
    for year, ch_rows in _EXTRA_ROWS.items():
        for ch, row_idx in ch_rows.items():
            if row_idx >= len(df):
                continue
            for m_idx, m in enumerate(_MONTHS):
                col = _COL_OFFSET + m_idx
                if col >= len(df.columns):
                    continue
                val = _safe_int(df.iloc[row_idx, col])
                records.append({
                    "data_type": data_type, "channel": ch,
                    "year": year, "month": m, "amount": val,
                })
    return records


def _parse_customer(df: pd.DataFrame) -> list:
    records = []
    for ch, (row_26, row_25) in _CUSTOMER_ROWS.items():
        for yr, row_idx in [(2026, row_26), (2025, row_25)]:
            if row_idx >= len(df):
                continue
            for m_idx, m in enumerate(_MONTHS):
                col = _COL_OFFSET + m_idx
                if col >= len(df.columns):
                    continue
                val = _safe_int(df.iloc[row_idx, col])
                records.append({"channel": ch, "year": yr, "month": m, "amount": val})
    return records


def _parse(df: pd.DataFrame, data_type: str) -> tuple[list, list, list]:
    targets, actuals, historical = [], [], []
    for ch, (row_tgt, row_act, row_25, row_24) in _CHANNEL_ROWS.items():
        for m_idx, m in enumerate(_MONTHS):
            col = _COL_OFFSET + m_idx
            tgt_val = _safe_int(df.iloc[row_tgt, col])
            act_val = _safe_int(df.iloc[row_act, col])
            h25_val = _safe_int(df.iloc[row_25,  col])
            h24_val = _safe_int(df.iloc[row_24,  col]) if row_24 < len(df) else 0
            targets.append({
                "data_type": data_type, "channel": ch,
                "year": 2026, "month": m, "amount": tgt_val,
            })
            if act_val > 0:
                actuals.append({
                    "data_type": data_type, "channel": ch,
                    "year": 2026, "month": m, "amount": act_val,
                })
            historical.append({
                "data_type": data_type, "channel": ch,
                "year": 2025, "month": m, "amount": h25_val,
            })
            historical.append({
                "data_type": data_type, "channel": ch,
                "year": 2024, "month": m, "amount": h24_val,
            })
    return targets, actuals, historical


# ── 공개 API ──────────────────────────────────────────────────

def is_configured() -> bool:
    """secrets.toml에 유효한 [sheets] 설정이 있는지 확인"""
    try:
        sid = st.secrets["sheets"]["spreadsheet_id"]
        return bool(sid) and not sid.startswith("your-")
    except Exception:
        return False


def sync_from_sheets() -> dict:
    """
    Google Sheets에서 데이터를 읽어 DB에 upsert.
    반환: {"targets": int, "actuals": int, "historical": int, "errors": list}
    """
    import requests

    gid_sales  = st.secrets["sheets"]["gid_sales"]
    gid_orders = st.secrets["sheets"]["gid_orders"]

    stats = {"targets": 0, "actuals": 0, "historical": 0, "extra": 0, "customers": 0, "errors": []}

    for gid, data_type in [(gid_sales, "매출"), (gid_orders, "수주")]:
        url = _csv_url(gid)
        try:
            resp = requests.get(url, timeout=15)
            resp.raise_for_status()
            df = pd.read_csv(io.StringIO(resp.text), header=None)
        except Exception as e:
            stats["errors"].append(f"{data_type} 시트 읽기 실패: {e}")
            continue

        targets, actuals, historical = _parse(df, data_type)

        for rec in targets:
            try:
                db.upsert_target(
                    rec["data_type"], rec["channel"],
                    rec["year"], rec["month"], rec["amount"],
                )
                stats["targets"] += 1
            except Exception as e:
                stats["errors"].append(f"targets upsert 오류: {e}")

        for rec in actuals:
            try:
                db.upsert_actual(
                    rec["data_type"], rec["channel"],
                    rec["year"], rec["month"], rec["amount"],
                )
                stats["actuals"] += 1
            except Exception as e:
                stats["errors"].append(f"actuals upsert 오류: {e}")

        try:
            db.insert_historical_bulk(historical)
            stats["historical"] += len(historical)
        except Exception as e:
            stats["errors"].append(f"historical 저장 오류: {e}")

        extra_records = _parse_extra(df, data_type)
        for rec in extra_records:
            try:
                db.upsert_extra(
                    rec["data_type"], rec["channel"],
                    rec["year"], rec["month"], rec["amount"],
                )
                stats["extra"] += 1
            except Exception as e:
                stats["errors"].append(f"extra upsert 오류: {e}")

        if data_type == "매출":
            cc_records = _parse_customer(df)
            for rec in cc_records:
                try:
                    db.upsert_customer_count(
                        rec["channel"], rec["year"], rec["month"], rec["amount"],
                    )
                    stats["customers"] += 1
                except Exception as e:
                    stats["errors"].append(f"customer_count upsert 오류: {e}")

    return stats
