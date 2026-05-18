import sqlite3
from datetime import datetime
import os

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")
CHB_ITEM_NAME = "CHB Blocks"
CHB_DEFAULT_UNIT = "pieces"
CHB_STATE_ID = 1
CEMENT_ITEM_NAME = "Cement"
FINE_SAND_ITEM_NAME = "Fine Sand"
RAW_MATERIAL_UNIT = "bag/sack"
FINE_SAND_UNIT = "cubic meters"
FINE_SAND_BAGS_PER_CUBIC_METER = 40

# ================= INIT DB =================
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
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
            material_inventory_applied INTEGER DEFAULT 0,
            ts TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            quantity INTEGER,
            price REAL,
            raw_price REAL,
            unit TEXT DEFAULT ''
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

    # Backfill pay_rate for older databases
    cursor.execute("PRAGMA table_info(chb_production)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    if "pay_rate" not in existing_cols:
        cursor.execute("ALTER TABLE chb_production ADD COLUMN pay_rate REAL DEFAULT 200")
    if "material_inventory_applied" not in existing_cols:
        cursor.execute("ALTER TABLE chb_production ADD COLUMN material_inventory_applied INTEGER DEFAULT 0")
    cursor.execute("PRAGMA table_info(items)")
    item_cols = [col[1] for col in cursor.fetchall()]
    if "unit" not in item_cols:
        cursor.execute("ALTER TABLE items ADD COLUMN unit TEXT DEFAULT ''")

    conn.commit()
    conn.close()


def ensure_chb_inventory(conn, cursor):
    """Ensure CHB inventory rows exist without recalculating away history."""
    cursor.execute("SELECT id, quantity FROM items WHERE name=? ORDER BY id ASC", (CHB_ITEM_NAME,))
    rows = cursor.fetchall()
    if rows:
        keeper_id = rows[0][0]
        cursor.execute(
            "UPDATE items SET unit=? WHERE id=?",
            (CHB_DEFAULT_UNIT, keeper_id)
        )
        if len(rows) > 1:
            cursor.execute(
                "DELETE FROM items WHERE name=? AND id<>?",
                (CHB_ITEM_NAME, keeper_id)
            )
    else:
        cursor.execute("SELECT COALESCE(SUM(total_blocks),0) FROM chb_production")
        produced = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(SUM(qty),0) FROM sales WHERE item_name=?", (CHB_ITEM_NAME,))
        sold = cursor.fetchone()[0] or 0
        stock = max(produced - sold, 0)
        cursor.execute(
            "INSERT INTO items (name, quantity, price, raw_price, unit) VALUES (?, ?, ?, ?, ?)",
            (CHB_ITEM_NAME, stock, 0, 0, CHB_DEFAULT_UNIT)
        )

    cursor.execute("SELECT id, total_produced, total_sold, available FROM chb_inventory_state WHERE id=?", (CHB_STATE_ID,))
    state_row = cursor.fetchone()
    if not state_row:
        cursor.execute("SELECT COALESCE(SUM(total_blocks),0) FROM chb_production")
        produced = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(SUM(qty),0) FROM sales WHERE item_name=?", (CHB_ITEM_NAME,))
        sold = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(quantity,0) FROM items WHERE name=? ORDER BY id ASC LIMIT 1", (CHB_ITEM_NAME,))
        item_row = cursor.fetchone()
        available = item_row[0] if item_row else max(produced - sold, 0)
        cursor.execute(
            "INSERT INTO chb_inventory_state (id, total_produced, total_sold, available, updated_ts) VALUES (?, ?, ?, ?, ?)",
            (CHB_STATE_ID, produced, sold, available, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

    conn.commit()


def adjust_chb_inventory(conn, cursor, produced_delta=0, sold_delta=0):
    """Persist CHB totals without tying them to deletions."""
    ensure_chb_inventory(conn, cursor)

    if produced_delta:
        cursor.execute(
            """
            UPDATE chb_inventory_state
            SET total_produced = total_produced + ?,
                available = MAX(available + ?, 0),
                updated_ts = ?
            WHERE id = ?
            """,
            (produced_delta, produced_delta, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), CHB_STATE_ID)
        )
        cursor.execute(
            "UPDATE items SET quantity = MAX(COALESCE(quantity, 0) + ?, 0) WHERE name=?",
            (produced_delta, CHB_ITEM_NAME)
        )

    if sold_delta:
        cursor.execute(
            """
            UPDATE chb_inventory_state
            SET total_sold = total_sold + ?,
                available = MAX(available - ?, 0),
                updated_ts = ?
            WHERE id = ?
            """,
            (sold_delta, sold_delta, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), CHB_STATE_ID)
        )
        cursor.execute(
            "UPDATE items SET quantity = MAX(COALESCE(quantity, 0) - ?, 0) WHERE name=?",
            (sold_delta, CHB_ITEM_NAME)
        )

    conn.commit()


def fetch_material_stock(cursor, item_name):
    cursor.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM items WHERE LOWER(name) = LOWER(?)",
        (item_name,)
    )
    return float(cursor.fetchone()[0] or 0)


def material_unit(item_name):
    return FINE_SAND_UNIT if str(item_name).strip().lower() == FINE_SAND_ITEM_NAME.lower() else RAW_MATERIAL_UNIT


def ensure_material_item(cursor, item_name):
    cursor.execute("SELECT id FROM items WHERE LOWER(name) = LOWER(?) ORDER BY id ASC LIMIT 1", (item_name,))
    row = cursor.fetchone()
    if row:
        if str(item_name).strip().lower() == FINE_SAND_ITEM_NAME.lower():
            cursor.execute("UPDATE items SET unit=? WHERE id=?", (FINE_SAND_UNIT, row[0]))
    else:
        cursor.execute(
            "INSERT INTO items (name, quantity, price, raw_price, unit) VALUES (?, ?, ?, ?, ?)",
            (item_name, 0, 0, 0, material_unit(item_name))
        )


def adjust_material_inventory(cursor, item_name, quantity_delta):
    """Adjust raw material stock. Negative values consume inventory."""
    if not quantity_delta:
        return

    ensure_material_item(cursor, item_name)

    if quantity_delta > 0:
        cursor.execute(
            """
            UPDATE items
            SET quantity = COALESCE(quantity, 0) + ?,
                unit = CASE WHEN COALESCE(unit, '') = '' THEN ? ELSE unit END
            WHERE id = (
                SELECT id FROM items WHERE LOWER(name) = LOWER(?) ORDER BY id ASC LIMIT 1
            )
            """,
            (quantity_delta, material_unit(item_name), item_name)
        )
        return

    needed = abs(quantity_delta)
    available = fetch_material_stock(cursor, item_name)
    if available < needed:
        raise ValueError(f"Not enough {item_name}. Available: {available}, needed: {needed}.")

    cursor.execute(
        "SELECT id, COALESCE(quantity, 0) FROM items WHERE LOWER(name) = LOWER(?) ORDER BY id ASC",
        (item_name,)
    )
    for item_id, current_qty in cursor.fetchall():
        if needed <= 0:
            break
        deduction = min(float(current_qty or 0), needed)
        if deduction:
            cursor.execute(
                "UPDATE items SET quantity = COALESCE(quantity, 0) - ? WHERE id=?",
                (deduction, item_id)
            )
            needed -= deduction


def fetch_production_summary(cursor, start=None, end=None):
    q = """
        SELECT production_date, worker_name, COALESCE(SUM(total_blocks),0) AS blocks, COALESCE(SUM(pay),0) AS pay
        FROM chb_production
    """
    params = []
    if start and end:
        q += " WHERE DATE(COALESCE(NULLIF(production_date, ''), ts)) BETWEEN ? AND ?"
        params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
    q += " GROUP BY production_date, worker_name ORDER BY DATE(COALESCE(NULLIF(production_date, ''), ts)) DESC, worker_name ASC"
    cursor.execute(q, params)
    return cursor.fetchall()


def fetch_latest_production_date(cursor):
    cursor.execute("SELECT COALESCE(NULLIF(production_date, ''), ts) FROM chb_production ORDER BY DATE(COALESCE(NULLIF(production_date, ''), ts)) DESC, ts DESC LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None


if __name__ == "__main__":
    import tkinter as tk
    from chb_module.gui import open_chb_dashboard

    root = tk.Tk()
    root.withdraw()
    open_chb_dashboard()
    root.mainloop()
