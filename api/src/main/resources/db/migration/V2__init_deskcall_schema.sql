-- V2: migrasi yang benar. V1 (percobaan pertama, sudah tercatat di history DB klarfinance) menaruh tabel di `dbo`
-- karena nama tidak dikualifikasi; tabel itu dibiarkan sebagai jejak, tidak dipakai. File V1 dihapus dari repo dan
-- application.yml mengabaikan migrasi lama yang filenya tidak ada (ignore-migration-patterns *:missing).
-- Schema `deskcall` dibuat oleh Flyway (create-schemas). SEMUA objek WAJIB diberi prefix `deskcall.`:
-- di SQL Server, nama tanpa prefix jatuh ke schema default login (dbo) dan mencemari schema klarfinance.
-- Tidak ada FK/JOIN ke schema klarfinance: referensi ke data klarfinance disimpan sebagai ID biasa.
-- Waktu disimpan sebagai UTC (DATETIME2).

CREATE TABLE deskcall.calls (
    id                   BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    call_uid             NVARCHAR(36)   NOT NULL,
    external_customer_id NVARCHAR(100)  NULL,
    external_loan_id     NVARCHAR(100)  NULL,
    customer_name        NVARCHAR(200)  NOT NULL,
    installment_amount   BIGINT         NOT NULL,
    penalty_amount       BIGINT         NOT NULL,
    due_date             DATE           NOT NULL,
    status               NVARCHAR(20)   NOT NULL,
    tag                  NVARCHAR(30)   NULL,
    verified             BIT            NOT NULL DEFAULT 0,
    ptp_date             DATE           NULL,
    note                 NVARCHAR(1000) NULL,
    room_name            NVARCHAR(100)  NOT NULL,
    created_at           DATETIME2      NOT NULL,
    answered_at          DATETIME2      NULL,
    ended_at             DATETIME2      NULL,
    result_received_at   DATETIME2      NULL,
    version              BIGINT         NOT NULL DEFAULT 0,
    CONSTRAINT uq_calls_call_uid UNIQUE (call_uid)
);

CREATE INDEX ix_calls_external_loan ON deskcall.calls (external_loan_id);
CREATE INDEX ix_calls_external_customer ON deskcall.calls (external_customer_id);
CREATE INDEX ix_calls_status_created ON deskcall.calls (status, created_at);
CREATE INDEX ix_calls_tag ON deskcall.calls (tag);

CREATE TABLE deskcall.call_events (
    id          BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    call_id     BIGINT         NOT NULL,
    type        NVARCHAR(40)   NOT NULL,
    detail      NVARCHAR(2000) NULL,
    occurred_at DATETIME2      NOT NULL,
    CONSTRAINT fk_call_events_call FOREIGN KEY (call_id) REFERENCES deskcall.calls (id)
);

CREATE INDEX ix_call_events_call ON deskcall.call_events (call_id);

CREATE TABLE deskcall.call_turns (
    id       BIGINT IDENTITY(1,1) NOT NULL PRIMARY KEY,
    call_id  BIGINT         NOT NULL,
    seq      INT            NOT NULL,
    speaker  NVARCHAR(20)   NOT NULL,
    content  NVARCHAR(4000) NOT NULL,
    state    NVARCHAR(40)   NULL,
    CONSTRAINT fk_call_turns_call FOREIGN KEY (call_id) REFERENCES deskcall.calls (id),
    CONSTRAINT uq_call_turns_call_seq UNIQUE (call_id, seq)
);
