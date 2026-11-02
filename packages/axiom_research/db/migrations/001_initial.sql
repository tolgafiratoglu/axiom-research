-- AxiomResearch initial schema: sessions, runs, ledger, event log, traces, eval.
-- JSONB payloads mirror packages/axiom_research/ledger.py contracts.

CREATE TABLE IF NOT EXISTS schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS sessions (
    session_id TEXT PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    memory_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS runs (
    run_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    question TEXT NOT NULL,
    status TEXT NOT NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    fail_reason TEXT,
    token_usage JSONB NOT NULL DEFAULT '{}'::jsonb,
    cost_usd NUMERIC(12, 6),
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS runs_session_id_idx ON runs (session_id);

CREATE TABLE IF NOT EXISTS sources (
    source_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs (run_id) ON DELETE SET NULL,
    identifier TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    revision INT NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS sources_session_id_idx ON sources (session_id);
CREATE INDEX IF NOT EXISTS sources_identifier_idx ON sources (identifier);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs (run_id) ON DELETE SET NULL,
    source_id TEXT NOT NULL REFERENCES sources (source_id),
    kind TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    revision INT NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS evidence_session_id_idx ON evidence (session_id);
CREATE INDEX IF NOT EXISTS evidence_source_id_idx ON evidence (source_id);

CREATE TABLE IF NOT EXISTS claims (
    claim_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs (run_id) ON DELETE SET NULL,
    revision INT NOT NULL,
    fingerprint TEXT NOT NULL,
    verification_status TEXT NOT NULL DEFAULT 'pending',
    verified_revision INT,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS claims_session_id_idx ON claims (session_id);

CREATE TABLE IF NOT EXISTS claim_evidence (
    claim_id TEXT NOT NULL REFERENCES claims (claim_id) ON DELETE CASCADE,
    evidence_id TEXT NOT NULL REFERENCES evidence (evidence_id) ON DELETE CASCADE,
    PRIMARY KEY (claim_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS calculations (
    calculation_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs (run_id) ON DELETE SET NULL,
    fingerprint TEXT NOT NULL,
    revision INT NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS calculations_session_id_idx ON calculations (session_id);

CREATE TABLE IF NOT EXISTS hypotheses (
    hypothesis_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs (run_id) ON DELETE SET NULL,
    fingerprint TEXT NOT NULL,
    revision INT NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS hypotheses_session_id_idx ON hypotheses (session_id);

CREATE TABLE IF NOT EXISTS verifications (
    verification_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    run_id TEXT REFERENCES runs (run_id) ON DELETE SET NULL,
    claim_id TEXT NOT NULL REFERENCES claims (claim_id) ON DELETE CASCADE,
    claim_revision INT NOT NULL,
    claim_fingerprint TEXT NOT NULL,
    status TEXT NOT NULL,
    fingerprint TEXT NOT NULL,
    revision INT NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS verifications_claim_id_idx ON verifications (claim_id);
CREATE INDEX IF NOT EXISTS verifications_session_id_idx ON verifications (session_id);

CREATE TABLE IF NOT EXISTS audit_events (
    audit_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    action TEXT NOT NULL,
    agent_id TEXT,
    fingerprint TEXT NOT NULL,
    revision INT NOT NULL DEFAULT 1,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS audit_events_session_run_idx ON audit_events (session_id, run_id);

CREATE TABLE IF NOT EXISTS ledger_snapshots (
    snapshot_id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL REFERENCES runs (run_id) ON DELETE CASCADE,
    frozen_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    fingerprint TEXT NOT NULL,
    payload JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ledger_snapshots_session_run_idx
    ON ledger_snapshots (session_id, run_id);

CREATE TABLE IF NOT EXISTS event_log (
    seq BIGSERIAL PRIMARY KEY,
    event_id TEXT NOT NULL UNIQUE,
    session_id TEXT NOT NULL REFERENCES sessions (session_id) ON DELETE CASCADE,
    run_id TEXT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL
);

CREATE INDEX IF NOT EXISTS event_log_session_seq_idx ON event_log (session_id, seq);

CREATE TABLE IF NOT EXISTS traces (
    trace_id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions (session_id) ON DELETE SET NULL,
    run_id TEXT REFERENCES runs (run_id) ON DELETE SET NULL,
    started_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    finished_at TIMESTAMPTZ,
    spans JSONB NOT NULL DEFAULT '[]'::jsonb,
    metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS traces_session_id_idx ON traces (session_id);

CREATE TABLE IF NOT EXISTS eval_records (
    eval_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL,
    mode TEXT NOT NULL,
    run_id TEXT,
    scores JSONB NOT NULL DEFAULT '{}'::jsonb,
    report JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS eval_records_case_id_idx ON eval_records (case_id);
