"""Clean all client/tenant data from the development database.
Preserves platform config: plan_pricing, coupons.

Usage: python scripts/clean_dev_db.py [--confirm]
"""
import asyncio
import asyncpg
import sys

DB_URL = "postgresql://postgres:IUnCuWxZbyfGFqlychBTsmLdlXvyfdCj@shuttle.proxy.rlwy.net:51510/railway"

# Order matters: children first, then parents (respecting foreign keys)
TABLES_TO_CLEAN = [
    # Leaf tables (no dependents)
    "chat_messages",
    "agent_interactions",
    "quality_issues",
    "prompt_revisions",
    "qa_review_cycles",
    # Bot domain tables
    "reminders",
    "shopping_items",
    "vehicle_reminders",
    "vehicle_services",
    "vehicles",
    # Backend domain tables
    "expenses",
    "events",
    "google_calendar_credentials",
    "pending_registrations",
    # Sessions
    "chat_sessions",
    # Subscriptions (before users/tenants)
    "subscriptions",
    # Users before tenants
    "users",
    # Tenants last
    "tenants",
]


async def main(confirm: bool):
    conn = await asyncpg.connect(DB_URL)
    try:
        # Show what will be deleted
        print("=== Tables to clean ===")
        for t in TABLES_TO_CLEAN:
            try:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {t}")
                count = row["cnt"]
                print(f"  {t}: {count} rows {'(will delete)' if count > 0 else '(empty)'}")
            except Exception:
                print(f"  {t}: (table does not exist, skipping)")

        print("\n=== Preserved (not touched) ===")
        for t in ["plan_pricing", "coupons"]:
            try:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {t}")
                print(f"  {t}: {row['cnt']} rows (preserved)")
            except Exception:
                print(f"  {t}: (does not exist)")

        if not confirm:
            print("\n[DRY RUN] Pass --confirm to actually delete.")
            return

        print("\nDeleting data...")
        for t in TABLES_TO_CLEAN:
            try:
                result = await conn.execute(f"DELETE FROM {t}")
                print(f"  {t}: {result}")
            except Exception as e:
                print(f"  {t}: SKIPPED ({e})")

        print("\n[OK] Development database cleaned successfully.")
    finally:
        await conn.close()


if __name__ == "__main__":
    do_confirm = "--confirm" in sys.argv
    asyncio.run(main(do_confirm))
