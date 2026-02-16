"""Utility script to run a SQL migration against the Railway database.
Usage: railway run python scripts/run_migration.py scripts/db/012_pending_registrations.sql
Or:    python scripts/run_migration.py scripts/db/012_pending_registrations.sql --url <DATABASE_URL>
"""
import asyncio
import asyncpg
import pathlib
import sys
import os


async def run_migration(sql_path: str, database_url: str):
    sql = pathlib.Path(sql_path).read_text(encoding="utf-8")
    print(f"Connecting to database...")
    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(sql)
        print(f"Migration '{sql_path}' executed successfully.")
        table_name = pathlib.Path(sql_path).stem.split("_", 1)[-1] if "_" in pathlib.Path(sql_path).stem else None
        if table_name:
            row = await conn.fetchrow(
                "SELECT table_name FROM information_schema.tables WHERE table_name = $1",
                table_name,
            )
            if row:
                print(f"Verified: table '{table_name}' exists.")
    finally:
        await conn.close()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_migration.py <sql_file> [--url <DATABASE_URL>]")
        sys.exit(1)

    sql_file = sys.argv[1]
    db_url = None
    if "--url" in sys.argv:
        idx = sys.argv.index("--url")
        db_url = sys.argv[idx + 1]
    else:
        db_url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")

    if not db_url:
        print("Error: No database URL. Use --url or set DATABASE_URL/DATABASE_PUBLIC_URL env var.")
        sys.exit(1)

    asyncio.run(run_migration(sql_file, db_url))
