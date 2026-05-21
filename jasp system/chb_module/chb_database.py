import sqlite3
from datetime import datetime
import os

# Store shared database path and CHB/material constants used by this module.
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
    # Open the SQLite database connection for CHB table setup.
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create the production records table for CHB batches and worker pay.
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
            responsible_user TEXT DEFAULT '',
            ts TEXT
        )
    """)

    # Create the shared inventory table if it does not exist yet.
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

    # Create the single-row CHB stock state table used by dashboards and stock updates.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chb_inventory_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_produced INTEGER NOT NULL DEFAULT 0,
            total_sold INTEGER NOT NULL DEFAULT 0,
            available INTEGER NOT NULL DEFAULT 0,
            updated_ts TEXT
        )
    """)

    # Create the table that records manual CHB stock adjustments.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chb_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            adjustment_date TEXT NOT NULL,
            adjustment_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            reason TEXT NOT NULL,
            responsible_user TEXT DEFAULT '',
            ts TEXT NOT NULL
        )
    """)

    # Create the sales table if the POS module has not created it yet.
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

    # Backfill missing CHB production columns for older database files.
    cursor.execute("PRAGMA table_info(chb_production)")
    existing_cols = [col[1] for col in cursor.fetchall()]
    if "pay_rate" not in existing_cols:
        cursor.execute("ALTER TABLE chb_production ADD COLUMN pay_rate REAL DEFAULT 200")
    if "material_inventory_applied" not in existing_cols:
        cursor.execute("ALTER TABLE chb_production ADD COLUMN material_inventory_applied INTEGER DEFAULT 0")
    if "responsible_user" not in existing_cols:
        cursor.execute("ALTER TABLE chb_production ADD COLUMN responsible_user TEXT DEFAULT ''")

    # Backfill the inventory unit column for older database files.
    cursor.execute("PRAGMA table_info(items)")
    item_cols = [col[1] for col in cursor.fetchall()]
    if "unit" not in item_cols:
        cursor.execute("ALTER TABLE items ADD COLUMN unit TEXT DEFAULT ''")

    # Save schema changes and close the setup connection.
    conn.commit()
    conn.close()


def ensure_chb_inventory(conn, cursor):
    """Ensure CHB inventory rows exist without recalculating away history."""
    # Find existing CHB inventory rows so only one official item row remains.
    cursor.execute("SELECT id, quantity FROM items WHERE name=? ORDER BY id ASC", (CHB_ITEM_NAME,))
    rows = cursor.fetchall()
    if rows:
        # Keep the oldest CHB item row and make sure its unit is pieces.
        keeper_id = rows[0][0]
        cursor.execute(
            "UPDATE items SET unit=? WHERE id=?",
            (CHB_DEFAULT_UNIT, keeper_id)
        )
        if len(rows) > 1:
            # Remove duplicate CHB item rows to avoid double-counted inventory.
            cursor.execute(
                "DELETE FROM items WHERE name=? AND id<>?",
                (CHB_ITEM_NAME, keeper_id)
            )
    else:
        # Create the CHB item from production minus sales when it is missing.
        cursor.execute("SELECT COALESCE(SUM(total_blocks),0) FROM chb_production")
        produced = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(SUM(qty),0) FROM sales WHERE item_name=?", (CHB_ITEM_NAME,))
        sold = cursor.fetchone()[0] or 0
        stock = max(produced - sold, 0)
        cursor.execute(
            "INSERT INTO items (name, quantity, price, raw_price, unit) VALUES (?, ?, ?, ?, ?)",
            (CHB_ITEM_NAME, stock, 0, 0, CHB_DEFAULT_UNIT)
        )

    # Check whether the CHB stock state row already exists.
    cursor.execute("SELECT id, total_produced, total_sold, available FROM chb_inventory_state WHERE id=?", (CHB_STATE_ID,))
    state_row = cursor.fetchone()
    if not state_row:
        # Create the initial CHB stock state from existing production, sales, and item quantity.
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

    # Save any item cleanup or state creation changes.
    conn.commit()


def adjust_chb_inventory(conn, cursor, produced_delta=0, sold_delta=0):
    """Persist CHB totals without tying them to deletions."""
    # Make sure the CHB item and stock state exist before applying changes.
    ensure_chb_inventory(conn, cursor)

    if produced_delta:
        # Add newly produced blocks to total produced and available stock.
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
        # Keep the shared inventory item quantity in sync with CHB production.
        cursor.execute(
            "UPDATE items SET quantity = MAX(COALESCE(quantity, 0) + ?, 0) WHERE name=?",
            (produced_delta, CHB_ITEM_NAME)
        )

    if sold_delta:
        # Add sold blocks to total sold and remove them from available stock.
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
        # Keep the shared inventory item quantity in sync with CHB sales.
        cursor.execute(
            "UPDATE items SET quantity = MAX(COALESCE(quantity, 0) - ?, 0) WHERE name=?",
            (sold_delta, CHB_ITEM_NAME)
        )

    # Save CHB stock changes after all requested adjustments are applied.
    conn.commit()


def fetch_material_stock(cursor, item_name):
    # Return the total available stock for a raw material across matching item rows.
    cursor.execute(
        "SELECT COALESCE(SUM(quantity), 0) FROM items WHERE LOWER(name) = LOWER(?)",
        (item_name,)
    )
    return float(cursor.fetchone()[0] or 0)


def material_unit(item_name):
    # Use cubic meters for fine sand and bag/sack for other CHB materials.
    return FINE_SAND_UNIT if str(item_name).strip().lower() == FINE_SAND_ITEM_NAME.lower() else RAW_MATERIAL_UNIT


def ensure_material_item(cursor, item_name):
    # Find or create the raw material item used by CHB production.
    cursor.execute("SELECT id FROM items WHERE LOWER(name) = LOWER(?) ORDER BY id ASC LIMIT 1", (item_name,))
    row = cursor.fetchone()
    if row:
        if str(item_name).strip().lower() == FINE_SAND_ITEM_NAME.lower():
            # Keep fine sand unit consistent when the item already exists.
            cursor.execute("UPDATE items SET unit=? WHERE id=?", (FINE_SAND_UNIT, row[0]))
    else:
        # Insert missing material with zero stock so future adjustments can update it.
        cursor.execute(
            "INSERT INTO items (name, quantity, price, raw_price, unit) VALUES (?, ?, ?, ?, ?)",
            (item_name, 0, 0, 0, material_unit(item_name))
        )


def adjust_material_inventory(cursor, item_name, quantity_delta):
    """Adjust raw material stock. Negative values consume inventory."""
    # Ignore zero adjustments because they do not change material stock.
    if not quantity_delta:
        return

    # Make sure the material exists before adding or deducting stock.
    ensure_material_item(cursor, item_name)

    if quantity_delta > 0:
        # Add restocked material quantity to the first matching material item.
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

    # Check that enough material exists before consuming it for CHB production.
    needed = abs(quantity_delta)
    available = fetch_material_stock(cursor, item_name)
    if available < needed:
        raise ValueError(f"Not enough {item_name}. Available: {available}, needed: {needed}.")

    # Deduct material from matching rows in order until the needed amount is consumed.
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
    # Build the CHB production summary query grouped by date, worker, and user.
    q = """
        SELECT production_date,
               worker_name,
               COALESCE(NULLIF(responsible_user, ''), 'Admin') AS responsible_user,
               COALESCE(SUM(total_blocks),0) AS blocks,
               COALESCE(SUM(pay),0) AS pay
        FROM chb_production
    """
    params = []
    if start and end:
        # Limit the production summary to the selected date range when provided.
        q += " WHERE DATE(COALESCE(NULLIF(production_date, ''), ts)) BETWEEN ? AND ?"
        params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
    # Sort newest production records first for report display.
    q += " GROUP BY production_date, worker_name, COALESCE(NULLIF(responsible_user, ''), 'Admin') ORDER BY DATE(COALESCE(NULLIF(production_date, ''), ts)) DESC, worker_name ASC, responsible_user ASC"
    cursor.execute(q, params)
    return cursor.fetchall()


def fetch_chb_adjustment_summary(cursor, start=None, end=None):
    # Ensure the adjustment history table exists before reading summary data.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chb_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            adjustment_date TEXT NOT NULL,
            adjustment_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            reason TEXT NOT NULL,
            responsible_user TEXT DEFAULT '',
            ts TEXT NOT NULL
        )
    """)
    # Build the CHB adjustment summary query for manual stock changes.
    q = """
        SELECT adjustment_date,
               adjustment_type,
               quantity,
               reason,
               COALESCE(NULLIF(responsible_user, ''), 'Admin') AS responsible_user
        FROM chb_adjustments
    """
    params = []
    if start and end:
        # Limit adjustment history to the selected date range when provided.
        q += " WHERE DATE(COALESCE(NULLIF(adjustment_date, ''), ts)) BETWEEN ? AND ?"
        params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
    # Sort newest adjustment records first for report display.
    q += " ORDER BY DATE(COALESCE(NULLIF(adjustment_date, ''), ts)) DESC, ts DESC, id DESC"
    cursor.execute(q, params)
    return cursor.fetchall()


def fetch_latest_production_date(cursor):
    # Return the newest CHB production date for dashboard or summary defaults.
    cursor.execute("SELECT COALESCE(NULLIF(production_date, ''), ts) FROM chb_production ORDER BY DATE(COALESCE(NULLIF(production_date, ''), ts)) DESC, ts DESC LIMIT 1")
    row = cursor.fetchone()
    return row[0] if row else None


if __name__ == "__main__":
    # Allow this module to be run directly for opening the CHB dashboard.
    import tkinter as tk
    from chb_module.gui import open_chb_dashboard

    # Start a hidden root window and launch the CHB dashboard.
    root = tk.Tk()
    root.withdraw()
    open_chb_dashboard()
    root.mainloop()
