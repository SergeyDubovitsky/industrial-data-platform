from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Protocol


class MigrationError(RuntimeError):
    """Raised when migration state is invalid or applying a migration fails."""


class ClickHouseClient(Protocol):
    def execute(self, sql: str) -> str:
        """Execute SQL and return ClickHouse response text."""


@dataclass(frozen=True)
class Migration:
    version: str
    path: Path
    sql: str
    checksum: str


@dataclass(frozen=True)
class MigrationStatus:
    version: str
    path: Path
    checksum: str
    state: str


METADATA_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS schema_migrations
(
    version String,
    checksum String,
    applied_at DateTime64(3, 'UTC')
)
ENGINE = MergeTree
ORDER BY version
""".strip()


def load_migrations(migrations_dir: Path) -> list[Migration]:
    if not migrations_dir.exists():
        raise MigrationError(f"Migrations directory does not exist: {migrations_dir}")

    migrations: list[Migration] = []
    for path in sorted(migrations_dir.glob("*.sql")):
        sql = path.read_text(encoding="utf-8")
        migrations.append(
            Migration(
                version=path.stem,
                path=path,
                sql=sql,
                checksum=sha256(sql.encode("utf-8")).hexdigest(),
            )
        )

    return migrations


def ensure_metadata_table(client: ClickHouseClient) -> None:
    client.execute(METADATA_TABLE_SQL)


def load_applied(client: ClickHouseClient) -> dict[str, str]:
    raw = client.execute(
        "SELECT version, checksum FROM schema_migrations ORDER BY version FORMAT TSV"
    )
    applied: dict[str, str] = {}
    for line in raw.splitlines():
        if not line.strip():
            continue
        version, checksum = line.split("\t", maxsplit=1)
        applied[version] = checksum
    return applied


def migration_statuses(
    client: ClickHouseClient,
    migrations_dir: Path,
) -> list[MigrationStatus]:
    ensure_metadata_table(client)
    migrations = load_migrations(migrations_dir)
    applied = load_applied(client)
    return [_status_for(migration, applied) for migration in migrations]


def apply_pending_migrations(
    client: ClickHouseClient,
    migrations_dir: Path,
) -> list[Migration]:
    ensure_metadata_table(client)
    migrations = load_migrations(migrations_dir)
    applied = load_applied(client)
    applied_now: list[Migration] = []

    for migration in migrations:
        status = _status_for(migration, applied)
        if status.state == "checksum_mismatch":
            raise MigrationError(
                f"Applied migration checksum mismatch for {migration.version}: "
                f"{migration.path}"
            )
        if status.state == "applied":
            continue

        client.execute(migration.sql)
        client.execute(_record_migration_sql(migration))
        applied[migration.version] = migration.checksum
        applied_now.append(migration)

    return applied_now


def _status_for(
    migration: Migration,
    applied: dict[str, str],
) -> MigrationStatus:
    applied_checksum = applied.get(migration.version)
    if applied_checksum is None:
        state = "pending"
    elif applied_checksum == migration.checksum:
        state = "applied"
    else:
        state = "checksum_mismatch"
    return MigrationStatus(
        version=migration.version,
        path=migration.path,
        checksum=migration.checksum,
        state=state,
    )


def _record_migration_sql(migration: Migration) -> str:
    return (
        "INSERT INTO schema_migrations (version, checksum, applied_at) VALUES "
        f"('{_quote(migration.version)}', '{_quote(migration.checksum)}', now64(3))"
    )


def _quote(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")
