"""Resolve a working database URL profile before service startup.

This bootstrap is used by container entry commands to support both:
- current Avelon credentials/database
- legacy pre-rebrand credentials/database on persisted Postgres volumes
"""

from __future__ import annotations

import os
import sys
from typing import Iterable

from sqlalchemy import create_engine, text


def _build_legacy_urls() -> tuple[str, str]:
    host = os.getenv("POSTGRES_HOST", "postgres")
    port = os.getenv("POSTGRES_PORT", "5432")
    user = os.getenv("LEGACY_POSTGRES_USER", "aab_user")
    password = os.getenv("LEGACY_POSTGRES_PASSWORD", "aab_password")
    db = os.getenv("LEGACY_POSTGRES_DB", "aab_db")
    async_url = f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
    sync_url = f"postgresql://{user}:{password}@{host}:{port}/{db}"
    return async_url, sync_url


def _candidate_profiles() -> Iterable[tuple[str, str, str]]:
    primary_async = os.getenv("DATABASE_URL", "").strip()
    primary_sync = os.getenv("DATABASE_URL_SYNC", "").strip()
    if primary_async and primary_sync:
        yield ("primary", primary_async, primary_sync)

    legacy_async, legacy_sync = _build_legacy_urls()
    yield ("legacy", legacy_async, legacy_sync)


def _can_connect(sync_url: str) -> tuple[bool, str]:
    try:
        engine = create_engine(sync_url, pool_pre_ping=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return (True, "")
    except Exception as exc:  # pragma: no cover - runtime environment dependent
        return (False, str(exc))


def resolve_working_urls() -> tuple[str, str, str]:
    """Return (profile_name, async_url, sync_url) for the first reachable profile."""
    errors: list[str] = []
    for name, async_url, sync_url in _candidate_profiles():
        ok, err = _can_connect(sync_url)
        if ok:
            return (name, async_url, sync_url)
        errors.append(f"{name}: {err}")
    raise RuntimeError("No reachable database profile: " + " | ".join(errors))


def main() -> int:
    try:
        name, async_url, sync_url = resolve_working_urls()
        print(f'export DATABASE_URL="{async_url}"')
        print(f'export DATABASE_URL_SYNC="{sync_url}"')
        print(f'echo "Using DB profile: {name}"')
        return 0
    except Exception as exc:
        print(f"[db-bootstrap] {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
