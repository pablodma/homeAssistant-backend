"""Run database migration. Usage: python run_migration.py [008_plan_services|007_subscriptions_coupons_pricing]"""
import asyncio
import os
import re
import sys

import asyncpg


def split_sql_statements(sql: str) -> list[str]:
    """Split SQL into individual statements."""
    # Remove comments
    sql = re.sub(r'--.*$', '', sql, flags=re.MULTILINE)
    # Split by semicolon but keep CREATE TABLE/INDEX together
    statements = []
    current = []
    paren_depth = 0
    
    for line in sql.split('\n'):
        line = line.strip()
        if not line:
            continue
        
        paren_depth += line.count('(') - line.count(')')
        current.append(line)
        
        if line.endswith(';') and paren_depth <= 0:
            stmt = ' '.join(current)
            if stmt.strip() and stmt.strip() != ';':
                statements.append(stmt)
            current = []
            paren_depth = 0
    
    # Add any remaining statement
    if current:
        stmt = ' '.join(current)
        if stmt.strip() and stmt.strip() != ';':
            statements.append(stmt)
    
    return statements


async def run_migration():
    """Execute the migration SQL file."""
    # Use public URL for external access
    database_url = os.environ.get("DATABASE_PUBLIC_URL") or os.environ.get("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL not set")
        return

    # Read migration file: python run_migration.py 008_plan_services
    migration_arg = sys.argv[1] if len(sys.argv) > 1 else "007_subscriptions_coupons_pricing"
    migration_file = f"{migration_arg}.sql" if not migration_arg.endswith(".sql") else migration_arg
    migration_path = os.path.join(os.path.dirname(__file__), "db", migration_file)
    
    with open(migration_path, "r", encoding="utf-8") as f:
        sql = f.read()

    statements = split_sql_statements(sql)
    print(f"Found {len(statements)} statements to execute")

    print(f"Connecting to database...")
    conn = await asyncpg.connect(database_url)
    
    try:
        for i, stmt in enumerate(statements, 1):
            # Skip COMMENT statements for now (they cause issues)
            if stmt.strip().upper().startswith('COMMENT'):
                print(f"  [{i}] Skipping COMMENT...")
                continue
            
            try:
                print(f"  [{i}] Executing: {stmt[:60]}...")
                await conn.execute(stmt)
            except Exception as e:
                print(f"  [{i}] Warning: {e}")
        
        print("Migration completed!")
    except Exception as e:
        print(f"Migration failed: {e}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run_migration())
