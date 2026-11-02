"""2.1 — migration SQL defines required Postgres tables (no live DB)."""

from pathlib import Path

from axiom_research.db import MIGRATIONS_DIR, list_migration_files
from axiom_research.db.migrate import migration_version

REQUIRED_TABLES = (
    "schema_migrations",
    "sessions",
    "runs",
    "sources",
    "evidence",
    "claims",
    "claim_evidence",
    "calculations",
    "hypotheses",
    "verifications",
    "audit_events",
    "ledger_snapshots",
    "event_log",
    "traces",
    "eval_records",
)


def test_initial_migration_lists_required_tables() -> None:
    files = list_migration_files()
    assert files, "expected at least one migration under packages/axiom_research/db/migrations"
    assert migration_version(files[0]) == "001"
    sql = files[0].read_text(encoding="utf-8").lower()
    for table in REQUIRED_TABLES:
        assert f"create table if not exists {table}" in sql, table


def test_migrations_dir_is_packaged() -> None:
    assert MIGRATIONS_DIR.is_dir()
    assert (MIGRATIONS_DIR / "001_initial.sql").is_file()
    assert Path(MIGRATIONS_DIR).as_posix().endswith("axiom_research/db/migrations")
