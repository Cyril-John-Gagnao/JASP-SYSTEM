import os
import sqlite3

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")


def _table_columns(cursor, table_name):
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {col[1] for col in cursor.fetchall()}


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
    sales_cols = _table_columns(cursor, "sales")
    if "transaction_id" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN transaction_id TEXT DEFAULT ''")
    if "cashier" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN cashier TEXT DEFAULT ''")
    if "payment_status" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN payment_status TEXT DEFAULT 'Paid'")
    if "payment_received" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN payment_received REAL DEFAULT 0")
    if "change_amount" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN change_amount REAL DEFAULT 0")

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
    chb_cols = _table_columns(cursor, "chb_production")
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
    item_cols = _table_columns(cursor, "items")
    if "category" not in item_cols:
        cursor.execute("ALTER TABLE items ADD COLUMN category TEXT DEFAULT 'Uncategorized'")
    cursor.execute("UPDATE items SET category='Uncategorized' WHERE category IS NULL OR TRIM(category)=''")

    # Expenses table used by the Financial Summary report. Existing tables are
    # adapted by adding missing columns only; no expense data is removed.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            expense_id INTEGER PRIMARY KEY AUTOINCREMENT,
            expense_date TEXT NOT NULL,
            category TEXT,
            description TEXT,
            amount REAL NOT NULL DEFAULT 0,
            source_type TEXT,
            source_id INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    expense_cols = _table_columns(cursor, "expenses")
    expense_migrations = {
        "expense_date": "ALTER TABLE expenses ADD COLUMN expense_date TEXT",
        "category": "ALTER TABLE expenses ADD COLUMN category TEXT",
        "description": "ALTER TABLE expenses ADD COLUMN description TEXT",
        "amount": "ALTER TABLE expenses ADD COLUMN amount REAL NOT NULL DEFAULT 0",
        "source_type": "ALTER TABLE expenses ADD COLUMN source_type TEXT",
        "source_id": "ALTER TABLE expenses ADD COLUMN source_id INTEGER",
        "created_at": "ALTER TABLE expenses ADD COLUMN created_at TEXT DEFAULT CURRENT_TIMESTAMP",
    }
    for col_name, migration_sql in expense_migrations.items():
        if col_name not in expense_cols:
            cursor.execute(migration_sql)
    cursor.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_expenses_source_unique
        ON expenses(source_type, source_id, category)
        WHERE source_type IS NOT NULL
          AND source_id IS NOT NULL
          AND category IS NOT NULL
    """)

    conn.commit()
    conn.close()
