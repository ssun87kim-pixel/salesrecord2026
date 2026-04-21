# db.py  ─  Supabase 데이터베이스 연동 레이어
#           Supabase 미연결 시 로컬 SQLite(demo.db)로 자동 폴백
import os
import sqlite3
import streamlit as st
import pandas as pd

_EMPTY_COLS = ["data_type", "channel", "year", "month", "amount"]
_DB_PATH    = os.path.join(os.path.dirname(__file__), "demo.db")


# ── 모드 판별 ─────────────────────────────────────────────────

def _is_local() -> bool:
    """secrets.toml에 실제 Supabase 자격증명이 없으면 로컬 모드"""
    try:
        url = st.secrets["supabase"]["url"]
        return "xxxxxxxxxxxx" in url or url.startswith("https://your")
    except Exception:
        return True


# ── SQLite 헬퍼 ───────────────────────────────────────────────

def _conn() -> sqlite3.Connection:
    return sqlite3.connect(_DB_PATH)


def _init_local() -> None:
    """테이블이 없으면 생성"""
    with _conn() as con:
        cur = con.cursor()
        for tbl in ("targets", "actuals", "historical", "extra"):
            cur.execute(f"""
                CREATE TABLE IF NOT EXISTS {tbl} (
                    data_type TEXT NOT NULL,
                    channel   TEXT NOT NULL,
                    year      INTEGER NOT NULL,
                    month     INTEGER NOT NULL,
                    amount    BIGINT  NOT NULL DEFAULT 0,
                    UNIQUE(data_type, channel, year, month)
                )
            """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS customer_count (
                channel TEXT NOT NULL,
                year    INTEGER NOT NULL,
                month   INTEGER NOT NULL,
                amount  BIGINT  NOT NULL DEFAULT 0,
                UNIQUE(channel, year, month)
            )
        """)
        con.commit()


def _empty() -> pd.DataFrame:
    return pd.DataFrame(columns=_EMPTY_COLS)


def _read(table: str, year: int) -> pd.DataFrame:
    _init_local()
    with _conn() as con:
        df = pd.read_sql(
            f"SELECT data_type, channel, year, month, amount FROM {table} WHERE year=?",
            con, params=(year,),
        )
    return df if not df.empty else _empty()


# ── Supabase 클라이언트 (실제 배포용) ─────────────────────────

@st.cache_resource
def _client():
    from supabase import create_client  # noqa: 로컬 모드에서는 호출 안 됨
    return create_client(
        st.secrets["supabase"]["url"],
        st.secrets["supabase"]["key"],
    )


# ── 조회 ──────────────────────────────────────────────────────

def get_targets(year: int) -> pd.DataFrame:
    if _is_local():
        return _read("targets", year)
    r = _client().table("targets").select("*").eq("year", year).execute()
    return pd.DataFrame(r.data) if r.data else _empty()


def get_actuals(year: int) -> pd.DataFrame:
    if _is_local():
        return _read("actuals", year)
    r = _client().table("actuals").select("*").eq("year", year).execute()
    return pd.DataFrame(r.data) if r.data else _empty()


def get_historical(year: int) -> pd.DataFrame:
    if _is_local():
        return _read("historical", year)
    r = _client().table("historical").select("*").eq("year", year).execute()
    return pd.DataFrame(r.data) if r.data else _empty()


def is_historical_locked(year: int, data_type: str) -> bool:
    if _is_local():
        _init_local()
        with _conn() as con:
            cur = con.execute(
                "SELECT 1 FROM historical WHERE year=? AND data_type=? LIMIT 1",
                (year, data_type),
            )
            return cur.fetchone() is not None
    r = (
        _client()
        .table("historical")
        .select("id")
        .eq("year", year)
        .eq("data_type", data_type)
        .limit(1)
        .execute()
    )
    return len(r.data) > 0


# ── 저장 ──────────────────────────────────────────────────────

def upsert_target(data_type: str, channel: str, year: int, month: int, amount: int) -> None:
    if _is_local():
        _init_local()
        with _conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO targets(data_type,channel,year,month,amount) VALUES(?,?,?,?,?)",
                (data_type, channel, year, month, amount),
            )
        return
    _client().table("targets").upsert(
        {"data_type": data_type, "channel": channel,
         "year": year, "month": month, "amount": amount},
        on_conflict="data_type,channel,year,month",
    ).execute()


def upsert_actual(data_type: str, channel: str, year: int, month: int, amount: int) -> None:
    if _is_local():
        _init_local()
        with _conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO actuals(data_type,channel,year,month,amount) VALUES(?,?,?,?,?)",
                (data_type, channel, year, month, amount),
            )
        return
    _client().table("actuals").upsert(
        {"data_type": data_type, "channel": channel,
         "year": year, "month": month, "amount": amount},
        on_conflict="data_type,channel,year,month",
    ).execute()


def get_customer_count(year: int) -> pd.DataFrame:
    if _is_local():
        _init_local()
        with _conn() as con:
            df = pd.read_sql(
                "SELECT channel, year, month, amount FROM customer_count WHERE year=?",
                con, params=(year,),
            )
        return df if not df.empty else pd.DataFrame(columns=["channel", "year", "month", "amount"])
    r = _client().table("customer_count").select("*").eq("year", year).execute()
    return pd.DataFrame(r.data) if r.data else pd.DataFrame(columns=["channel", "year", "month", "amount"])


def upsert_customer_count(channel: str, year: int, month: int, amount: int) -> None:
    if _is_local():
        _init_local()
        with _conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO customer_count(channel,year,month,amount) VALUES(?,?,?,?)",
                (channel, year, month, amount),
            )
        return
    _client().table("customer_count").upsert(
        {"channel": channel, "year": year, "month": month, "amount": amount},
        on_conflict="channel,year,month",
    ).execute()


def get_extra(year: int) -> pd.DataFrame:
    if _is_local():
        return _read("extra", year)
    r = _client().table("extra").select("*").eq("year", year).execute()
    return pd.DataFrame(r.data) if r.data else _empty()


def upsert_extra(data_type: str, channel: str, year: int, month: int, amount: int) -> None:
    if _is_local():
        _init_local()
        with _conn() as con:
            con.execute(
                "INSERT OR REPLACE INTO extra(data_type,channel,year,month,amount) VALUES(?,?,?,?,?)",
                (data_type, channel, year, month, amount),
            )
        return
    _client().table("extra").upsert(
        {"data_type": data_type, "channel": channel,
         "year": year, "month": month, "amount": amount},
        on_conflict="data_type,channel,year,month",
    ).execute()


def insert_historical_bulk(records: list) -> None:
    if _is_local():
        _init_local()
        with _conn() as con:
            for rec in records:
                try:
                    con.execute(
                        "INSERT OR IGNORE INTO historical(data_type,channel,year,month,amount) VALUES(?,?,?,?,?)",
                        (rec["data_type"], rec["channel"], rec["year"], rec["month"], rec["amount"]),
                    )
                except Exception:
                    pass
        return
    client = _client()
    for rec in records:
        try:
            client.table("historical").insert(rec).execute()
        except Exception:
            pass
