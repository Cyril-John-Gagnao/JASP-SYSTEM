import sqlite3
from datetime import datetime
import os

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")


def init_delivery_db():
    """Initialize delivery tables in database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chb_delivery'")
    table_exists = cursor.fetchone()

    if not table_exists:
        # Create the table if it doesn't exist
        cursor.execute("""
            CREATE TABLE chb_delivery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                transaction_date TEXT,
                delivery_date TEXT,
                worker_name TEXT,
                driver_name TEXT,
                address TEXT,
                blocks_delivered INTEGER,
                delivery_fee REAL DEFAULT 0,
                payment_per_block REAL DEFAULT 2.0,
                total_payment REAL,
                ts TEXT
            )
        """)
        conn.commit()
    else:
        # Check if columns exist and add them if missing
        cursor.execute("PRAGMA table_info(chb_delivery)")
        columns = {row[1] for row in cursor.fetchall()}

        # Add missing columns
        if 'transaction_date' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN transaction_date TEXT")
        if 'delivery_date' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN delivery_date TEXT")
        if 'driver_name' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN driver_name TEXT")
        if 'address' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN address TEXT")
        if 'delivery_fee' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN delivery_fee REAL DEFAULT 0")
        if 'payment_per_block' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN payment_per_block REAL DEFAULT 2.0")
        if 'total_payment' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN total_payment REAL")
        if 'ts' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN ts TEXT")

        cursor.execute("UPDATE chb_delivery SET transaction_date = COALESCE(transaction_date, delivery_date, '')")
        cursor.execute("UPDATE chb_delivery SET driver_name = COALESCE(driver_name, '')")
        cursor.execute("UPDATE chb_delivery SET address = COALESCE(address, '')")
        cursor.execute("UPDATE chb_delivery SET delivery_fee = COALESCE(delivery_fee, 0)")

        conn.commit()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS other_items_delivery (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            transaction_date TEXT,
            delivery_date TEXT,
            item_name TEXT,
            quantity INTEGER,
            unit_of_measurement TEXT,
            delivery_address TEXT,
            delivery_driver TEXT,
            helper TEXT,
            delivery_fee REAL DEFAULT 0,
            delivery_datetime TEXT,
            ts TEXT
        )
    """)

    cursor.execute("PRAGMA table_info(other_items_delivery)")
    other_columns = {row[1] for row in cursor.fetchall()}
    if "transaction_date" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN transaction_date TEXT")
    if "delivery_date" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN delivery_date TEXT")
    if "item_name" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN item_name TEXT")
    if "quantity" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN quantity INTEGER")
    if "unit_of_measurement" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN unit_of_measurement TEXT")
    if "delivery_address" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN delivery_address TEXT")
    if "delivery_driver" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN delivery_driver TEXT")
    if "helper" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN helper TEXT")
    if "delivery_fee" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN delivery_fee REAL DEFAULT 0")
    if "delivery_datetime" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN delivery_datetime TEXT")
    if "ts" not in other_columns:
        cursor.execute("ALTER TABLE other_items_delivery ADD COLUMN ts TEXT")

    cursor.execute("UPDATE other_items_delivery SET transaction_date = COALESCE(transaction_date, delivery_datetime, '')")
    cursor.execute("UPDATE other_items_delivery SET delivery_date = COALESCE(delivery_date, delivery_datetime, transaction_date, '')")
    cursor.execute("UPDATE other_items_delivery SET delivery_fee = COALESCE(delivery_fee, 0)")

    conn.commit()
    conn.close()


def open_delivery_connection():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    return conn, cursor


def insert_delivery(conn, cursor, transaction_date, date, worker, driver_name, address, blocks, delivery_fee, payment_per, total):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO chb_delivery
        (transaction_date, delivery_date, worker_name, driver_name, address, blocks_delivered, delivery_fee, payment_per_block, total_payment, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (transaction_date, date, worker, driver_name, address, blocks, delivery_fee, payment_per, total, ts))

    conn.commit()


def insert_other_item_delivery(conn, cursor, transaction_date, delivery_date, item_name, quantity, unit_of_measurement, delivery_address, delivery_driver, helper, delivery_fee):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute("""
        INSERT INTO other_items_delivery
        (transaction_date, delivery_date, item_name, quantity, unit_of_measurement, delivery_address, delivery_driver, helper, delivery_fee, delivery_datetime, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (transaction_date, delivery_date, item_name, quantity, unit_of_measurement, delivery_address, delivery_driver, helper, delivery_fee, delivery_date, ts))
    conn.commit()


def update_other_item_delivery_record(conn, cursor, selected_id, transaction_date, delivery_date, item_name, quantity, unit_of_measurement, delivery_address, delivery_driver, helper, delivery_fee):
    cursor.execute("""
        UPDATE other_items_delivery
        SET transaction_date=?, delivery_date=?, item_name=?, quantity=?, unit_of_measurement=?, delivery_address=?, delivery_driver=?, helper=?, delivery_fee=?, delivery_datetime=?
        WHERE id=?
    """, (transaction_date, delivery_date, item_name, quantity, unit_of_measurement, delivery_address, delivery_driver, helper, delivery_fee, delivery_date, selected_id))
    conn.commit()


def delete_other_item_delivery_record(conn, cursor, selected_id):
    cursor.execute("DELETE FROM other_items_delivery WHERE id=?", (selected_id,))
    conn.commit()


def update_delivery_record(conn, cursor, selected_id, transaction_date, date, worker, driver_name, address, blocks, delivery_fee, payment_per, total):
    cursor.execute("""
        UPDATE chb_delivery
        SET transaction_date=?, delivery_date=?, worker_name=?, driver_name=?, address=?, blocks_delivered=?, delivery_fee=?, payment_per_block=?, total_payment=?
        WHERE id=?
    """, (
        transaction_date,
        date,
        worker,
        driver_name, address,
        blocks, delivery_fee, payment_per, total,
        selected_id
    ))

    conn.commit()


def delete_delivery_record(conn, cursor, selected_id):
    cursor.execute("DELETE FROM chb_delivery WHERE id=?", (selected_id,))
    conn.commit()


def fetch_delivery_rows(cursor, keyword, sort_option, delivery_date=None):
    query = """
        SELECT id,
               COALESCE(transaction_date, ''),
               COALESCE(delivery_date, ''),
               COALESCE(worker_name, ''),
               COALESCE(driver_name, ''),
               COALESCE(address, ''),
               COALESCE(blocks_delivered, 0),
               COALESCE(delivery_fee, 0),
               COALESCE(total_payment, 0)
        FROM chb_delivery
    """

    params = []
    where_clauses = []

    if delivery_date:
        where_clauses.append("DATE(COALESCE(NULLIF(delivery_date, ''), transaction_date, ts)) = ?")
        params.append(delivery_date)

    if keyword:
        where_clauses.append("(LOWER(worker_name) LIKE ? OR delivery_date LIKE ? OR transaction_date LIKE ? OR LOWER(driver_name) LIKE ? OR LOWER(address) LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    if sort_option == "Worker Name":
        query += " ORDER BY worker_name ASC"
    else:
        query += " ORDER BY DATE(COALESCE(NULLIF(delivery_date, ''), transaction_date, ts)) DESC, ts DESC"

    cursor.execute(query, params)
    return cursor.fetchall()


def fetch_other_item_delivery_rows(cursor, keyword, sort_option, delivery_date=None):
    query = """
        SELECT id,
               COALESCE(transaction_date, delivery_datetime, ''),
               COALESCE(delivery_date, delivery_datetime, transaction_date, ''),
               COALESCE(item_name, ''),
               COALESCE(quantity, 0),
               COALESCE(unit_of_measurement, ''),
               COALESCE(delivery_address, ''),
               COALESCE(delivery_driver, ''),
               COALESCE(helper, ''),
               COALESCE(delivery_fee, 0)
        FROM other_items_delivery
    """

    params = []
    where_clauses = []

    if delivery_date:
        where_clauses.append("DATE(COALESCE(NULLIF(delivery_date, ''), transaction_date, delivery_datetime, ts)) = ?")
        params.append(delivery_date)

    if keyword:
        where_clauses.append("(LOWER(item_name) LIKE ? OR LOWER(delivery_address) LIKE ? OR LOWER(delivery_driver) LIKE ? OR LOWER(helper) LIKE ? OR delivery_date LIKE ? OR transaction_date LIKE ?)")
        params.extend([f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%", f"%{keyword}%"])

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)

    if sort_option == "Worker Name":
        query += " ORDER BY item_name ASC"
    else:
        query += " ORDER BY DATE(COALESCE(NULLIF(delivery_date, ''), transaction_date, delivery_datetime, ts)) DESC, ts DESC"

    cursor.execute(query, params)
    return cursor.fetchall()


def fetch_delivery_summary(cursor, start=None, end=None):
    q = """
        SELECT COALESCE(transaction_date, delivery_date, '') AS transaction_date,
               COALESCE(delivery_date, '') AS delivery_date,
               COALESCE(worker_name, '') AS worker_name,
               COALESCE(driver_name, '') AS driver_name,
               COALESCE(address, '') AS address,
               COALESCE(SUM(blocks_delivered), 0) AS blocks,
               COALESCE(SUM(delivery_fee), 0) AS delivery_fee,
               COALESCE(SUM(total_payment), 0) AS total_payment
        FROM chb_delivery
    """
    params = []
    if start and end:
        q += " WHERE DATE(COALESCE(NULLIF(delivery_date, ''), transaction_date, ts)) BETWEEN ? AND ?"
        params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
    q += """
        GROUP BY COALESCE(transaction_date, delivery_date, ''), delivery_date, worker_name, driver_name, address
        ORDER BY DATE(COALESCE(NULLIF(delivery_date, ''), transaction_date, ts)) DESC, delivery_date DESC, worker_name ASC
    """
    cursor.execute(q, params)
    return cursor.fetchall()


def fetch_other_item_delivery_summary(cursor, start=None, end=None):
    q = """
        SELECT COALESCE(transaction_date, delivery_datetime, '') AS transaction_date,
               COALESCE(delivery_date, delivery_datetime, transaction_date, '') AS delivery_date,
               COALESCE(item_name, '') AS item_name,
               COALESCE(quantity, 0) AS quantity,
               COALESCE(unit_of_measurement, '') AS unit_of_measurement,
               COALESCE(delivery_address, '') AS delivery_address,
               COALESCE(delivery_driver, '') AS delivery_driver,
               COALESCE(helper, '') AS helper,
               COALESCE(delivery_fee, 0) AS delivery_fee
        FROM other_items_delivery
    """
    params = []
    if start and end:
        q += " WHERE DATE(COALESCE(NULLIF(delivery_date, ''), transaction_date, delivery_datetime, ts)) BETWEEN ? AND ?"
        params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
    q += """
        ORDER BY DATE(COALESCE(NULLIF(delivery_date, ''), transaction_date, delivery_datetime, ts)) DESC, item_name ASC
    """
    cursor.execute(q, params)
    return cursor.fetchall()


def fetch_latest_delivery_summary_date(cursor):
    cursor.execute("""
        SELECT COALESCE(NULLIF(delivery_date, ''), transaction_date, ts)
        FROM chb_delivery
        WHERE COALESCE(NULLIF(delivery_date, ''), transaction_date, ts) IS NOT NULL
        ORDER BY DATE(COALESCE(NULLIF(delivery_date, ''), transaction_date, ts)) DESC, ts DESC
        LIMIT 1
    """)
    row = cursor.fetchone()
    return row[0] if row else None
