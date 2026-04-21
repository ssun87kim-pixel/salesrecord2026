-- DESKER 사업부 월별마감 관리 시스템 - DB 스키마
-- Supabase > SQL Editor 에서 한 번만 실행하세요

-- 1. 연간 목표 테이블 (연초 설정, 수정 가능)
CREATE TABLE IF NOT EXISTS targets (
    id        BIGSERIAL PRIMARY KEY,
    data_type TEXT    NOT NULL,   -- '수주' 또는 '매출'
    channel   TEXT    NOT NULL,   -- 채널명
    year      INTEGER NOT NULL,
    month     INTEGER NOT NULL,
    amount    BIGINT  NOT NULL DEFAULT 0,
    UNIQUE(data_type, channel, year, month)
);

-- 2. 월별 실적 테이블 (매달 입력, 수정 가능)
CREATE TABLE IF NOT EXISTS actuals (
    id         BIGSERIAL PRIMARY KEY,
    data_type  TEXT        NOT NULL,
    channel    TEXT        NOT NULL,
    year       INTEGER     NOT NULL,
    month      INTEGER     NOT NULL,
    amount     BIGINT      NOT NULL DEFAULT 0,
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(data_type, channel, year, month)
);

-- 3. 과거 실적 테이블 (1회 입력 후 수정/삭제 불가)
CREATE TABLE IF NOT EXISTS historical (
    id        BIGSERIAL PRIMARY KEY,
    data_type TEXT    NOT NULL,
    channel   TEXT    NOT NULL,
    year      INTEGER NOT NULL,
    month     INTEGER NOT NULL,
    amount    BIGINT  NOT NULL DEFAULT 0,
    UNIQUE(data_type, channel, year, month)
);

-- 과거 실적 수정/삭제 방지 트리거
CREATE OR REPLACE FUNCTION prevent_historical_change()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION '과거 실적 데이터는 수정하거나 삭제할 수 없습니다.';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS no_historical_update ON historical;
CREATE TRIGGER no_historical_update
    BEFORE UPDATE ON historical
    FOR EACH ROW EXECUTE FUNCTION prevent_historical_change();

DROP TRIGGER IF EXISTS no_historical_delete ON historical;
CREATE TRIGGER no_historical_delete
    BEFORE DELETE ON historical
    FOR EACH ROW EXECUTE FUNCTION prevent_historical_change();
