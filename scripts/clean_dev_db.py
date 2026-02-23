"""Clean all client/tenant data from the development database.
Preserves platform config: plan_pricing, coupons.

Usage (Railway CLI):
  cd homeai-api
  railway link   # select project + environment that has DATABASE_URL (e.g. homeAssistant-backend)
  railway run python scripts/clean_dev_db.py           # dry run
  railway run python scripts/clean_dev_db.py --confirm # delete all tenants and conversations
"""
import asyncio
import os
import sys

import asyncpg

DB_URL = os.environ.get("DATABASE_URL")
if not DB_URL:
    print("ERROR: DATABASE_URL is not set. Use: railway run python scripts/clean_dev_db.py [--confirm]")
    sys.exit(1)

# Order matters: children first, then parents (respecting foreign keys)
TABLES_TO_CLEAN = [
    # Conversations (backend LLM memory)
    "conversation_messages",
    "conversations",
    # Chat (bot)
    "chat_messages",
    "agent_interactions",
    "quality_issues",
    "prompt_revisions",
    "qa_review_cycles",
    "user_agent_onboarding",
    # Bot domain
    "reminders",
    "shopping_items",
    "shopping_lists",
    "vehicle_reminders",
    "vehicle_services",
    "vehicles",
    # Backend domain
    "expenses",
    "events",
    "google_calendar_credentials",
    "pending_registrations",
    "audit_logs",
    "chat_sessions",
    # Subscriptions
    "subscription_payments",
    "coupon_redemptions",
    "subscriptions",
    # Tenant-scoped
    "invitations",
    "budget_categories",
    "users",
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
