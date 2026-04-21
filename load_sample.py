# load_sample.py  ─  샘플 엑셀 데이터를 demo.db(SQLite)에 로드
import sys
import os
import sqlite3
import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")

EXCEL_PATH = os.path.join(
    os.path.dirname(__file__),
    "SAMPLE DATA",
    "26\ub144_\ub370\uc2a4\ucee4_\uc6d4\ubcc4\ub9c8\uac10\uc591\uc2dd.xlsx",
)
DB_PATH = os.path.join(os.path.dirname(__file__), "demo.db")

# 시트명
SHEET_SALES  = "26\ub144\ub9e4\ucd9c(\uc5d1\uc2a4\ud2b8\ub77c\ubc18\uc601)"
SHEET_ORDERS = "26\ub144\uc218\uc8fc(1_3\uc6d4\uc628\ub77c\uc778\uc5d1\uc2a4\ud2b8\ub77c_4\uc6d4ERP)"

MONTHS = list(range(1, 13))  # 1~12월

# 엑셀 컬럼 인덱스: 3=1월, 4=2월, ..., 14=12월
COL_OFFSET = 3

# 채널별 행 번호 (0-based): [목표행, 실적행, 25년행]
CHANNEL_ROWS = {
    "\uc628\ub77c\uc778\uc678\ubd80\ubaf0": (10, 11, 14),   # 온라인외부몰
    "\uc624\ud504\ub77c\uc778":             (16, 17, 20),   # 오프라인
    "\uacf5\uc2dd\ubaf0+MATE":             (28, 29, 32),   # 공식몰+MATE
}


def safe_int(val) -> int:
    """NaN/None → 0, 나머지는 int 변환"""
    try:
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return 0
        return int(val)
    except (ValueError, TypeError):
        return 0


def parse_sheet(df: pd.DataFrame, data_type: str) -> tuple[list, list, list]:
    """시트 DataFrame을 (targets, actuals, historical_25) 레코드 리스트로 파싱"""
    targets    = []
    actuals    = []
    historical = []

    for ch, (row_tgt, row_act, row_25) in CHANNEL_ROWS.items():
        for m_idx, m in enumerate(MONTHS):
            col = COL_OFFSET + m_idx

            tgt_val = safe_int(df.iloc[row_tgt, col])
            act_val = safe_int(df.iloc[row_act, col])
            h25_val = safe_int(df.iloc[row_25,  col])

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

    return targets, actuals, historical


def init_db(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    for tbl in ("targets", "actuals", "historical"):
        cur.execute(f"DROP TABLE IF EXISTS {tbl}")
        cur.execute(f"""
            CREATE TABLE {tbl} (
                data_type TEXT NOT NULL,
                channel   TEXT NOT NULL,
                year      INTEGER NOT NULL,
                month     INTEGER NOT NULL,
                amount    BIGINT  NOT NULL DEFAULT 0,
                UNIQUE(data_type, channel, year, month)
            )
        """)
    con.commit()


def insert_records(con: sqlite3.Connection, table: str, records: list) -> None:
    cur = con.cursor()
    for r in records:
        cur.execute(
            f"INSERT OR REPLACE INTO {table}(data_type,channel,year,month,amount) VALUES(?,?,?,?,?)",
            (r["data_type"], r["channel"], r["year"], r["month"], r["amount"]),
        )
    con.commit()
    print(f"  {table}: {len(records)}건 저장")


def main():
    print(f"엑셀 읽는 중: {EXCEL_PATH}")
    df_sales  = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_SALES,  header=None)
    df_orders = pd.read_excel(EXCEL_PATH, sheet_name=SHEET_ORDERS, header=None)

    tgt_s, act_s, h25_s = parse_sheet(df_sales,  "\ub9e4\ucd9c")   # 매출
    tgt_o, act_o, h25_o = parse_sheet(df_orders, "\uc218\uc8fc")   # 수주

    print(f"DB 초기화: {DB_PATH}")
    con = sqlite3.connect(DB_PATH)
    init_db(con)

    print("targets 저장 중...")
    insert_records(con, "targets",    tgt_s + tgt_o)

    print("actuals 저장 중...")
    insert_records(con, "actuals",    act_s + act_o)

    print("historical(25년) 저장 중...")
    insert_records(con, "historical", h25_s + h25_o)

    con.close()
    print("\n완료. demo.db 에 샘플 데이터가 로드되었습니다.")


if __name__ == "__main__":
    main()
