"""CLI entrypoint for running DB migrations manually or in container startup."""

from sqlalchemy import create_engine

from app.migrations.bootstrap import resolve_working_urls
from app.migrations.runner import MIGRATION_VERSION, run_migrations_in_connection


def main() -> None:
    profile_name, _, sync_url = resolve_working_urls()
    engine = create_engine(sync_url, pool_pre_ping=True)
    with engine.begin() as conn:
        run_migrations_in_connection(conn)
    print(f"Applied migrations up to: {MIGRATION_VERSION} (profile: {profile_name})")


if __name__ == "__main__":
    main()
