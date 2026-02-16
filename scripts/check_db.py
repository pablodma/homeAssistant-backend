"""Check row counts in all tables of the development database."""
import asyncio
import asyncpg
import sys

DB_URL = sys.argv[1] if len(sys.argv) > 1 else "postgresql://postgres:IUnCuWxZbyfGFqlychBTsmLdlXvyfdCj@shuttle.proxy.rlwy.net:51510/railway"

TABLES = [
    "tenants", "users", "subscriptions", "expenses", "budgets",
    "events", "google_calendar_credentials",
    "agent_interactions", "chat_sessions", "chat_messages",
    "reminders", "shopping_items", "vehicles", "vehicle_services", "vehicle_reminders",
    "quality_issues", "qa_review_cycles", "prompt_revisions",
    "pending_registrations", "plan_pricing", "plan_services", "coupons",
]


async def main():
    conn = await asyncpg.connect(DB_URL)
    try:
        print("=== Row counts (development) ===")
        for t in TABLES:
            try:
                row = await conn.fetchrow(f"SELECT COUNT(*) as cnt FROM {t}")
                count = row["cnt"]
                marker = " <-- has data" if count > 0 else ""
                print(f"  {t}: {count}{marker}")
            except Exception as e:
                print(f"  {t}: ERROR - {e}")

        # Show tenants detail
        print("\n=== Tenants ===")
        rows = await conn.fetch("SELECT id, name, created_at FROM tenants ORDER BY created_at")
        for r in rows:
            print(f"  {r['id']} | {r['name']} | {r['created_at']}")

        # Show users detail
        print("\n=== Users ===")
        rows = await conn.fetch("SELECT id, email, phone, display_name, role, tenant_id FROM users ORDER BY created_at")
        for r in rows:
            print(f"  {r['id']} | {r['email']} | {r['phone']} | {r['display_name']} | {r['role']} | tenant={r['tenant_id']}")
    finally:
        await conn.close()


asyncio.run(main())
