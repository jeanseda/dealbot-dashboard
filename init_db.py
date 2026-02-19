#!/usr/bin/env python3
"""
Initialize the PostgreSQL database on first deploy.
Run via: python init_db.py
Called from build.sh during Render build.
"""

import os
import sys

DATABASE_URL = os.getenv("DATABASE_URL", "")

if not DATABASE_URL:
    print("No DATABASE_URL set — skipping DB init (SQLite dev mode).")
    sys.exit(0)

# Render uses postgres://, psycopg2 needs postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

try:
    import psycopg2
except ImportError:
    print("psycopg2 not installed — skipping DB init.")
    sys.exit(0)

SCHEMA_PATH = os.path.join(os.path.dirname(__file__), "schema.sql")

print("Connecting to PostgreSQL...")
conn = psycopg2.connect(DATABASE_URL)
conn.autocommit = True
cur = conn.cursor()

print(f"Running schema from {SCHEMA_PATH}...")
with open(SCHEMA_PATH) as f:
    sql = f.read()

cur.execute(sql)
print("✅ Database initialized successfully.")

cur.close()
conn.close()
