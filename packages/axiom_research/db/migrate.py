"""Apply numbered SQL migrations against Postgres (operator / api startup)."""

from __future__ import annotations

import re
from pathlib import Path

MIGRATIONS_DIR = Path(__file__).resolve().parent / "migrations"
_VERSION_RE = re.compile(r"^(\d+)_.*\.sql$")


def list_migration_files(directory: Path = MIGRATIONS_DIR) -> list[Path]:
    files = [p for p in directory.glob("*.sql") if _VERSION_RE.match(p.name)]
    return sorted(files, key=lambda p: int(_VERSION_RE.match(p.name).group(1)))  # type: ignore[union-attr]


def migration_version(path: Path) -> str:
    match = _VERSION_RE.match(path.name)
    if match is None:
        raise ValueError(f"Invalid migration filename: {path.name}")
    return match.group(1)


def apply_migrations(database_url: str, *, directory: Path = MIGRATIONS_DIR) -> list[str]:
    """Apply pending migrations. Returns applied version ids."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "psycopg is required to apply migrations. Install project dependencies."
        ) from exc

    applied: list[str] = []
    with psycopg.connect(database_url) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )
        conn.commit()
        rows = conn.execute("SELECT version FROM schema_migrations").fetchall()
        done = {row[0] for row in rows}
        for path in list_migration_files(directory):
            version = migration_version(path)
            if version in done:
                continue
            sql = path.read_text(encoding="utf-8")
            with conn.transaction():
                conn.execute(sql)
                conn.execute(
                    "INSERT INTO schema_migrations (version) VALUES (%s)",
                    (version,),
                )
            applied.append(version)
    return applied


def main() -> None:
    import os
    import sys

    url = (os.environ.get("DATABASE_URL") or "").strip()
    if not url:
        print("DATABASE_URL is required", file=sys.stderr)
        raise SystemExit(2)
    applied = apply_migrations(url)
    if applied:
        print("applied:", ", ".join(applied))
    else:
        print("already up to date")


if __name__ == "__main__":
    main()
