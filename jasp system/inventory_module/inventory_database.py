import sqlite3
from datetime import datetime
import os

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")
CHB_ITEM_NAME = "CHB Blocks"
CHB_STATE_ID = 1
CHB_DEFAULT_UNIT = "pieces"
PREDEFINED_ITEMS = {
    "Nails": "kilograms",
    "CHB Blocks": CHB_DEFAULT_UNIT,
    "Cement": "bag/sack",
    "Fine Sand": "cubic meters"
}
UNIT_OPTIONS = [
    CHB_DEFAULT_UNIT,
    "kilograms",
    "bag/sack",
    "cubic meters",
    "pieces",
    "meters",
    "liters",
    "boxes",
    "sets",
    "rolls",
]


def open_inventory_connection():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    return conn, cursor


def setup_inventory_database(conn, cursor):
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        raw_price REAL DEFAULT 0,
        unit TEXT DEFAULT '',
        status TEXT DEFAULT 'Active',
        date_added TEXT DEFAULT ''
    )
    """)
    conn.commit()

    cursor.execute("PRAGMA table_info(items)")
    columns = [col[1] for col in cursor.fetchall()]
    if "raw_price" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN raw_price REAL DEFAULT 0")
        conn.commit()
    if "unit" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN unit TEXT DEFAULT ''")
        conn.commit()
    if "status" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN status TEXT DEFAULT 'Active'")
        cursor.execute("UPDATE items SET status='Active' WHERE status IS NULL OR status=''")
        conn.commit()
    if "date_added" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN date_added TEXT DEFAULT ''")
        cursor.execute(
            "UPDATE items SET date_added=? WHERE date_added IS NULL OR date_added=''",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
        )
        conn.commit()
    if "fine_sand_bag_price" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN fine_sand_bag_price REAL DEFAULT 0")
        conn.commit()

    ensure_inventory_unit_options(conn, cursor)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        raw_price REAL DEFAULT 0,
        unit TEXT DEFAULT '',
        status TEXT DEFAULT 'Active',
        date_added TEXT DEFAULT ''
    )
    """)
    conn.commit()

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
    cursor.execute("PRAGMA table_info(chb_production)")
    chb_columns = [col[1] for col in cursor.fetchall()]
    if "material_inventory_applied" not in chb_columns:
        cursor.execute("ALTER TABLE chb_production ADD COLUMN material_inventory_applied INTEGER DEFAULT 0")
        conn.commit()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chb_inventory_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_produced INTEGER NOT NULL DEFAULT 0,
            total_sold INTEGER NOT NULL DEFAULT 0,
            available INTEGER NOT NULL DEFAULT 0,
            updated_ts TEXT
        )
    """)
    create_inventory_logs_table(cursor)
    conn.commit()


def ensure_chb_item(conn, cursor):
    cursor.execute("SELECT id FROM items WHERE name=? ORDER BY id ASC", (CHB_ITEM_NAME,))
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
            "INSERT INTO items (name, quantity, price, raw_price, unit, status, date_added) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (CHB_ITEM_NAME, stock, 0, 0, CHB_DEFAULT_UNIT, "Active", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )

    cursor.execute("SELECT id FROM chb_inventory_state WHERE id=?", (CHB_STATE_ID,))
    if not cursor.fetchone():
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


def ensure_chb_material_items(conn, cursor):
    for item_name in ("Cement", "Fine Sand"):
        cursor.execute("SELECT id FROM items WHERE LOWER(name) = LOWER(?) ORDER BY id ASC LIMIT 1", (item_name,))
        row = cursor.fetchone()
        if row:
            unit_expr = "?" if item_name == "Fine Sand" else "CASE WHEN COALESCE(unit, '') = '' THEN ? ELSE unit END"
            cursor.execute(
                f"""
                UPDATE items
                SET name=?,
                    unit={unit_expr},
                    status=CASE WHEN COALESCE(status, '') = '' THEN 'Active' ELSE status END
                WHERE id=?
                """,
                (item_name, PREDEFINED_ITEMS[item_name], row[0])
            )
        else:
            cursor.execute(
                """
                INSERT INTO items (name, quantity, price, raw_price, unit, status, date_added)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item_name,
                    0,
                    0,
                    0,
                    PREDEFINED_ITEMS[item_name],
                    "Active",
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                )
            )
    conn.commit()


def normalize_predefined_units(conn, cursor):
    for item_name, item_unit in PREDEFINED_ITEMS.items():
        if item_name == "Fine Sand":
            cursor.execute("UPDATE items SET unit=? WHERE name=?", (item_unit, item_name))
            continue
        cursor.execute(
            "UPDATE items SET unit=? WHERE name=? AND COALESCE(unit, '') = ''",
            (item_unit, item_name)
        )
    conn.commit()


def ensure_inventory_unit_options(conn, cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_unit_options (
            unit TEXT PRIMARY KEY,
            is_custom INTEGER DEFAULT 0,
            is_deleted INTEGER DEFAULT 0,
            ts TEXT
        )
    """)
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for unit in UNIT_OPTIONS:
        cursor.execute(
            """
            INSERT OR IGNORE INTO inventory_unit_options (unit, is_custom, is_deleted, ts)
            VALUES (?, 0, 0, ?)
            """,
            (unit, now)
        )
    conn.commit()


def fetch_inventory_unit_options(conn, cursor):
    ensure_inventory_unit_options(conn, cursor)
    cursor.execute("""
        SELECT unit
        FROM inventory_unit_options
        WHERE COALESCE(is_deleted, 0) = 0
        ORDER BY is_custom ASC, LOWER(unit) ASC
    """)
    return [row[0] for row in cursor.fetchall()]


def add_inventory_unit_option(conn, cursor, unit):
    ensure_inventory_unit_options(conn, cursor)
    unit = unit.strip()
    if not unit:
        return
    cursor.execute(
        """
        INSERT INTO inventory_unit_options (unit, is_custom, is_deleted, ts)
        VALUES (?, 1, 0, ?)
        ON CONFLICT(unit) DO UPDATE SET is_deleted=0, ts=excluded.ts
        """,
        (unit, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    )
    conn.commit()


def delete_inventory_unit_option(conn, cursor, unit):
    ensure_inventory_unit_options(conn, cursor)
    cursor.execute(
        "UPDATE inventory_unit_options SET is_deleted=1 WHERE unit=?",
        (unit,)
    )
    conn.commit()


def fetch_items(cursor, filter_text="", sort_by="Latest Date"):
    order_clause = "ORDER BY datetime(COALESCE(NULLIF(date_added, ''), '1970-01-01 00:00:00')) DESC, id DESC"
    if sort_by in ("Name", "Item Name"):
        order_clause = "ORDER BY LOWER(name) ASC, id DESC"

    if filter_text:
        cursor.execute(
            f"SELECT id, name, unit, quantity, price, raw_price, COALESCE(status, 'Active'), COALESCE(fine_sand_bag_price, 0) FROM items WHERE name LIKE ? {order_clause}",
            (f"%{filter_text}%",)
        )
    else:
        cursor.execute(f"SELECT id, name, unit, quantity, price, raw_price, COALESCE(status, 'Active'), COALESCE(fine_sand_bag_price, 0) FROM items {order_clause}")
    return cursor.fetchall()


def count_items(cursor, filter_text=""):
    if filter_text:
        cursor.execute("SELECT COUNT(*) FROM items WHERE name LIKE ?", (f"%{filter_text}%",))
    else:
        cursor.execute("SELECT COUNT(*) FROM items")
    return int(cursor.fetchone()[0] or 0)


def create_restocks_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            raw_price REAL DEFAULT 0,
            total_cost REAL NOT NULL,
            ts TEXT NOT NULL
        )
    """)


def create_inventory_logs_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            item_name TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 0,
            action_status TEXT NOT NULL,
            ts TEXT NOT NULL,
            responsible_user TEXT DEFAULT ''
        )
    """)
    cursor.execute("PRAGMA table_info(inventory_logs)")
    columns = [col[1] for col in cursor.fetchall()]
    if "responsible_user" not in columns:
        cursor.execute("ALTER TABLE inventory_logs ADD COLUMN responsible_user TEXT DEFAULT ''")


def log_inventory_action(conn, cursor, item_id, item_name, qty, action_status, ts=None):
    create_inventory_logs_table(cursor)
    try:
        from main_dashboard import session
        responsible_user = session.get_current_username("Admin")
    except Exception:
        responsible_user = "Admin"
    qty_value = float(qty or 0) if str(item_name).strip().lower() == "fine sand" else int(qty or 0)
    cursor.execute(
        """
        INSERT INTO inventory_logs (item_id, item_name, qty, action_status, ts, responsible_user)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            item_id,
            item_name,
            qty_value,
            action_status,
            ts or datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            responsible_user,
        )
    )
    conn.commit()


def log_restock(conn, cursor, name, qty_added, price, raw_price, item_id=None, action_status="Restock"):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_cost = raw_price * qty_added
    create_restocks_table(cursor)
    cursor.execute(
        "INSERT INTO restocks (item_name, qty, price, raw_price, total_cost, ts) VALUES (?, ?, ?, ?, ?, ?)",
        (name, qty_added, price, raw_price, total_cost, ts)
    )
    log_inventory_action(conn, cursor, item_id, name, qty_added, action_status, ts)
    conn.commit()


def product_name_exists(cursor, name, exclude_item_id=None):
    if exclude_item_id is None:
        cursor.execute(
            "SELECT 1 FROM items WHERE LOWER(TRIM(name)) = LOWER(TRIM(?)) LIMIT 1",
            (name,),
        )
    else:
        cursor.execute(
            """
            SELECT 1
            FROM items
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
              AND id <> ?
            LIMIT 1
            """,
            (name, exclude_item_id),
        )
    return cursor.fetchone() is not None


def fetch_existing_item_for_stack(cursor, name, price_val):
    cursor.execute("SELECT id, quantity FROM items WHERE name = ? AND price = ?", (name, price_val))
    return cursor.fetchone()


def update_stacked_item(cursor, item_id, new_qty, raw_val, unit):
    cursor.execute(
        "UPDATE items SET quantity = ?, raw_price = ?, unit = ?, date_added = ? WHERE id = ?",
        (new_qty, raw_val, unit, datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id)
    )


def fetch_fine_sand_bag_price(cursor, item_id):
    cursor.execute("SELECT COALESCE(fine_sand_bag_price, 0) FROM items WHERE id=?", (item_id,))
    row = cursor.fetchone()
    return float(row[0] or 0) if row else 0


def insert_item(cursor, name, quantity_val, price_val, raw_val, unit, status="Active"):
    cursor.execute(
        "INSERT INTO items (name, quantity, price, raw_price, unit, status, date_added) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (name, quantity_val, price_val, raw_val, unit, status, datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
    )
    return cursor.lastrowid


def update_item_record(cursor, item_id, name, quantity_val, price_val, raw_val, unit, status="Active"):
    cursor.execute("UPDATE items SET name=?, quantity=?, price=?, raw_price=?, unit=?, status=? WHERE id=?",
                   (name, quantity_val, price_val, raw_val, unit, status, item_id))


def update_fine_sand_item_record(cursor, item_id, name, quantity_val, cubic_price, bag_price, raw_val, unit, status="Active"):
    cursor.execute(
        "UPDATE items SET name=?, quantity=?, price=?, fine_sand_bag_price=?, raw_price=?, unit=?, status=? WHERE id=?",
        (name, quantity_val, cubic_price, bag_price, raw_val, unit, status, item_id)
    )


def restock_item_record(conn, cursor, item_id, qty_added):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "SELECT name, quantity, price, raw_price, COALESCE(status, 'Active') FROM items WHERE id=?",
        (item_id,)
    )
    row = cursor.fetchone()
    if not row:
        return None

    name, current_qty, price, raw_price, status = row
    if status != "Active":
        return "inactive"

    current_qty = float(current_qty or 0) if str(name).strip().lower() == "fine sand" else int(current_qty or 0)
    new_qty = current_qty + qty_added
    cursor.execute(
        "UPDATE items SET quantity=?, date_added=? WHERE id=?",
        (new_qty, ts, item_id)
    )

    if name == CHB_ITEM_NAME:
        cursor.execute(
            """
            UPDATE chb_inventory_state
            SET total_produced = total_produced + ?,
                available = available + ?,
                updated_ts = ?
            WHERE id = ?
            """,
            (qty_added, qty_added, ts, CHB_STATE_ID)
        )

    log_restock(conn, cursor, name, qty_added, float(price or 0), float(raw_price or 0), item_id, "Restock")
    conn.commit()
    return name, current_qty, new_qty


def delete_item_record(conn, cursor, item_id):
    cursor.execute("SELECT name, quantity FROM items WHERE id=?", (item_id,))
    row = cursor.fetchone()
    if row:
        item_name, quantity = row
        log_inventory_action(conn, cursor, item_id, item_name, quantity, "Remove")
    cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
    conn.commit()
