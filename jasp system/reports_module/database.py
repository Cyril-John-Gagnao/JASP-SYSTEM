import os
import sqlite3

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "jasp.db")


def init_database():
    """Initialize database tables for reporting."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Sales table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            raw_price REAL DEFAULT 0,
            total REAL NOT NULL,
            ts TEXT NOT NULL
        )
    """)

    # Expenses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            ts TEXT NOT NULL
        )
    """)

    # CHB Production table (aligned with chb_dashboard.py schema)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chb_production (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_date TEXT,
            worker_name TEXT,
            cement_bags INTEGER,
            fine_sand REAL,
            total_blocks INTEGER,
            pay REAL,
            pay_rate REAL DEFAULT 200,
            ts TEXT
        )
    """)

    # Backfill columns for older databases created by previous report versions.
    cursor.execute("PRAGMA table_info(chb_production)")
    chb_cols = {col[1] for col in cursor.fetchall()}
    chb_migrations = {
        "production_date": "ALTER TABLE chb_production ADD COLUMN production_date TEXT",
        "worker_name": "ALTER TABLE chb_production ADD COLUMN worker_name TEXT",
        "cement_bags": "ALTER TABLE chb_production ADD COLUMN cement_bags INTEGER",
        "fine_sand": "ALTER TABLE chb_production ADD COLUMN fine_sand REAL",
        "total_blocks": "ALTER TABLE chb_production ADD COLUMN total_blocks INTEGER",
        "pay": "ALTER TABLE chb_production ADD COLUMN pay REAL",
        "pay_rate": "ALTER TABLE chb_production ADD COLUMN pay_rate REAL DEFAULT 200",
        "ts": "ALTER TABLE chb_production ADD COLUMN ts TEXT",
    }
    for col_name, migration_sql in chb_migrations.items():
        if col_name not in chb_cols:
            cursor.execute(migration_sql)

    # Inventory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            raw_price REAL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()
