#!/usr/bin/env python3
"""Run init.sql on Railway PostgreSQL."""

import psycopg2

conn = psycopg2.connect(
    host='nozomi.proxy.rlwy.net',
    port=25188,
    user='postgres',
    password='WhJXHLOPxCZtTlIQgpMLDdMeiqcDEWuu',
    dbname='railway'
)
conn.autocommit = True
cur = conn.cursor()

print("Running init.sql...")
with open('scripts/db/init.sql', 'r', encoding='utf-8') as f:
    sql = f.read()

cur.execute(sql)
print('Schema created successfully!')

print("Inserting initial data...")
cur.execute("""
INSERT INTO tenants (id, name, settings) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Tenant Demo', '{"timezone": "America/Argentina/Buenos_Aires"}'::jsonb)
ON CONFLICT DO NOTHING;
""")

cur.execute("""
INSERT INTO budget_categories (tenant_id, name, monthly_limit) VALUES 
    ('00000000-0000-0000-0000-000000000001', 'Supermercado', 100000),
    ('00000000-0000-0000-0000-000000000001', 'Transporte', 30000),
    ('00000000-0000-0000-0000-000000000001', 'Entretenimiento', 50000)
ON CONFLICT DO NOTHING;
""")
print('Initial data inserted!')

conn.close()
print("Done!")
