import os
import sqlite3
from datetime import datetime


DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")
CHB_ITEM_NAME = "CHB Blocks"
CHB_STATE_ID = 1


def open_pos_connection():
    return sqlite3.connect(DB_NAME)


def initialize_pos_database():
    conn = open_pos_connection()
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        raw_price REAL DEFAULT 0,
        unit TEXT DEFAULT '',
        status TEXT DEFAULT 'Active'
    )
    """)
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
    cursor.execute("PRAGMA table_info(sales)")
    sales_cols = [col[1] for col in cursor.fetchall()]
    if "transaction_id" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN transaction_id TEXT DEFAULT ''")
    if "cashier" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN cashier TEXT DEFAULT ''")
    if "payment_status" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN payment_status TEXT DEFAULT 'Paid'")
    if "payment_method" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN payment_method TEXT DEFAULT 'Cash'")
    if "receipt_path" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN receipt_path TEXT DEFAULT ''")
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chb_inventory_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_produced INTEGER NOT NULL DEFAULT 0,
            total_sold INTEGER NOT NULL DEFAULT 0,
            available INTEGER NOT NULL DEFAULT 0,
            updated_ts TEXT
        )
    """)
    cursor.execute("PRAGMA table_info(items)")
    item_cols = [col[1] for col in cursor.fetchall()]
    if "unit" not in item_cols:
        cursor.execute("ALTER TABLE items ADD COLUMN unit TEXT DEFAULT ''")
    if "status" not in item_cols:
        cursor.execute("ALTER TABLE items ADD COLUMN status TEXT DEFAULT 'Active'")
        cursor.execute("UPDATE items SET status='Active' WHERE status IS NULL OR status=''")

    cursor.execute("SELECT id FROM chb_inventory_state WHERE id=?", (CHB_STATE_ID,))
    if not cursor.fetchone():
        cursor.execute("SELECT COALESCE(SUM(total_blocks),0) FROM chb_production")
        produced = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(SUM(qty),0) FROM sales WHERE item_name=?", (CHB_ITEM_NAME,))
        sold = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(quantity,0) FROM items WHERE name=? ORDER BY id ASC LIMIT 1", (CHB_ITEM_NAME,))
        row = cursor.fetchone()
        available = row[0] if row else max(produced - sold, 0)
        cursor.execute(
            "INSERT INTO chb_inventory_state (id, total_produced, total_sold, available, updated_ts) VALUES (?, ?, ?, ?, ?)",
            (CHB_STATE_ID, produced, sold, available, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
    conn.commit()
    return conn, cursor

