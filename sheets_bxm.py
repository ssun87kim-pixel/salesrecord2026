import io
import pandas as pd
import streamlit as st
import requests
import google.auth.transport.requests
from pathlib import Path
from google.oauth2.service_account import Credentials

SPREADSHEET_ID = "14vEttvIlz-0R1fWqze3UjAQAUwpINI3Z"
ORDERS_GID = 1862118927
SALES_GID = 1977937242

_SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def _get_credentials():
    creds_path = st.secrets["bxm_sheets"]["creds_file"]
    creds = Credentials.from_service_account_file(creds_path, scopes=_SCOPES)
    return creds


def _load_sheet(spreadsheet_id: str, gid: int) -> pd.DataFrame:
    creds = _get_credentials()
    creds.refresh(google.auth.transport.requests.Request())

    url = (
        f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}"
        f"/export?format=csv&gid={gid}"
    )
    headers = {"Authorization": f"Bearer {creds.token}"}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()

    return pd.read_csv(io.BytesIO(resp.content), header=None, dtype=str, encoding="utf-8")


def _clean_val(v):
    if v is None:
        return None

    s = str(v).strip()

    if s in ("nan", "", "#REF!", "#N/A", " - ", "-"):
        return None

    if s.startswith("#"):
        return None

    if s.endswith("%"):
        try:
            return float(s[:-1]) / 100
        except ValueError:
            return None

    s_cleaned = s.replace(",", "").strip()

    if s_cleaned.startswith("- "):
        try:
            return -float(s_cleaned[2:])
        except ValueError:
            return None

    try:
        return float(s_cleaned)
    except ValueError:
        return None


def _build_index(df):
    idx = {}
    current_channel = None

    for row_idx, row in df.iterrows():
        col2 = str(row.iloc[2]).strip()
        col3 = str(row.iloc[3]).strip()

        if col2 not in ("nan", ""):
            current_channel = col2

        if current_channel is None or col3 in ("nan", ""):
            continue

        idx[(current_channel, col3)] = row_idx

    return idx


def get_values(df, idx, channel, metric):
    key = (channel, metric)
    if key not in idx:
        return None

    row_idx = idx[key]
    row = df.iloc[row_idx]

    result = {
        "합계": _clean_val(row.iloc[4])
    }

    for month_num in range(1, 13):
        col_idx = 4 + month_num
        result[f"m{month_num}"] = _clean_val(row.iloc[col_idx])

    return result


def load_orders():
    df = _load_sheet(SPREADSHEET_ID, ORDERS_GID)
    return (df, _build_index(df))


def load_sales():
    df = _load_sheet(SPREADSHEET_ID, SALES_GID)
    return (df, _build_index(df))


def load_channel_config():
    config_path = Path(__file__).parent / "BXM_채널설정.xlsx"

    if not config_path.exists():
        return [
            {"채널명": "온라인합계", "PM": "-", "목표여부": "Y", "순서": 0},
            {"채널명": "네이버", "PM": "유지원/이유정", "목표여부": "Y", "순서": 1},
            {"채널명": "오늘의집", "PM": "김도경", "목표여부": "N", "순서": 2},
            {"채널명": "CJ몰", "PM": "김은지", "목표여부": "N", "순서": 3},
            {"채널명": "SSG", "PM": "김도경", "목표여부": "N", "순서": 4},
            {"채널명": "쿠팡", "PM": "유지원/이유정", "목표여부": "N", "순서": 5},
        ]

    df = pd.read_excel(config_path, dtype={"목표여부": str})
    df = df.sort_values("순서")
    return df.to_dict("records")
