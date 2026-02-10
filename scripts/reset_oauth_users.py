#!/usr/bin/env python3
"""Reset OAuth users for testing - removes Google users and their tenants."""
import asyncio
import os

import asyncpg


async def main():
    database_url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL or DATABASE_PUBLIC_URL not set")
        return 1

    print("Connecting to database...")
    conn = await asyncpg.connect(database_url)
    try:
        async with conn.transaction():
            await conn.execute("""
                UPDATE plan_pricing SET updated_by = NULL 
                WHERE updated_by IN (
                  SELECT id FROM users 
                  WHERE auth_provider = 'google' AND phone LIKE 'oauth:%'
                )
            """)
            await conn.execute("""
                UPDATE coupons SET created_by = NULL 
                WHERE created_by IN (
                  SELECT id FROM users 
                  WHERE auth_provider = 'google' AND phone LIKE 'oauth:%'
                )
            """)
            await conn.execute("""
                UPDATE tenants t
                SET owner_user_id = NULL
                FROM users u
                WHERE t.owner_user_id = u.id
                  AND u.auth_provider = 'google'
                  AND u.phone LIKE 'oauth:%'
            """)
            await conn.execute("""
                DELETE FROM tenants
                WHERE id IN (
                  SELECT tenant_id FROM users 
                  WHERE auth_provider = 'google' 
                    AND phone LIKE 'oauth:%'
                    AND tenant_id != '00000000-0000-0000-0000-000000000001'
                )
            """)
        print("OAuth users and tenants reset successfully.")
        print("Cierra sesión en la app y prueba el onboarding de nuevo.")
    except Exception as e:
        print(f"Error: {e}")
        return 1
    finally:
        await conn.close()

    return 0


if __name__ == "__main__":
    exit(asyncio.run(main()))
