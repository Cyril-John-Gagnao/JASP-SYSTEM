import os
import sqlite3
from datetime import datetime


DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")


def ensure_sales_metadata(cursor):
    cursor.execute("PRAGMA table_info(sales)")
    sales_cols = [col[1] for col in cursor.fetchall()]
    if "transaction_id" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN transaction_id TEXT DEFAULT ''")
    if "cashier" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN cashier TEXT DEFAULT ''")
    if "payment_status" not in sales_cols:
        cursor.execute("ALTER TABLE sales ADD COLUMN payment_status TEXT DEFAULT 'Paid'")


def ensure_sales_table(cursor):
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
    ensure_sales_metadata(cursor)


def fetch_recent_transaction_summary(start, end):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    ensure_sales_table(cursor)

    cursor.execute("""
        SELECT
            CASE
                WHEN COALESCE(transaction_id, '') != '' THEN transaction_id
                ELSE 'TXN-' || printf('%05d', MIN(id))
            END AS txn_ref,
            MAX(ts) AS latest_ts,
            GROUP_CONCAT(item_name, ', ') AS items,
            COUNT(*) AS item_count,
            COALESCE(SUM(qty), 0) AS total_qty,
            COALESCE(SUM(total), 0) AS total_amount,
            COALESCE(NULLIF(MAX(cashier), ''), 'Admin') AS cashier_name,
            COALESCE(NULLIF(MAX(payment_status), ''), 'Paid') AS status
        FROM sales
        WHERE DATE(ts) BETWEEN ? AND ?
          AND COALESCE(payment_status, 'Paid') <> 'Void'
        GROUP BY CASE
            WHEN COALESCE(transaction_id, '') != '' THEN transaction_id
            ELSE ts
        END
        ORDER BY latest_ts DESC
    """, (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
    transactions = cursor.fetchall()

    cursor.execute("""
        SELECT item_name, COALESCE(SUM(qty), 0), COALESCE(SUM(total), 0)
        FROM sales
        WHERE DATE(ts) BETWEEN ? AND ?
          AND COALESCE(payment_status, 'Paid') <> 'Void'
        GROUP BY item_name
        ORDER BY SUM(qty) DESC, SUM(total) DESC
        LIMIT 5
    """, (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
    top_items = cursor.fetchall()
    conn.commit()
    conn.close()

    return {
        "transactions": transactions,
        "top_items": top_items,
        "total_sales": sum(row[5] for row in transactions),
        "total_qty": sum(row[4] for row in transactions),
        "transaction_count": len(transactions),
    }


def fetch_most_items_summary(start, end):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    ensure_sales_table(cursor)

    cursor.execute("""
        SELECT
            item_name,
            COALESCE(SUM(qty), 0) AS total_qty,
            COUNT(*) AS sales_count,
            COALESCE(SUM(total), 0) AS total_sales,
            MAX(ts) AS latest_ts
        FROM sales
        WHERE DATE(ts) BETWEEN ? AND ?
          AND COALESCE(payment_status, 'Paid') <> 'Void'
        GROUP BY item_name
        ORDER BY total_qty DESC, total_sales DESC, item_name ASC
    """, (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
    items = cursor.fetchall()
    conn.close()

    return {
        "items": items,
        "item_count": len(items),
        "total_qty": sum(row[1] for row in items),
        "total_sales": sum(row[3] for row in items),
    }


def fetch_dashboard_data():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            raw_price REAL DEFAULT 0
        )
    """)
    ensure_sales_table(cursor)
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chb_inventory_state (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            total_produced INTEGER NOT NULL DEFAULT 0,
            total_sold INTEGER NOT NULL DEFAULT 0,
            available INTEGER NOT NULL DEFAULT 0,
            updated_ts TEXT
        )
    """)

    today = datetime.now().strftime("%Y-%m-%d")

    cursor.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE DATE(ts)=? AND COALESCE(payment_status, 'Paid') <> 'Void'", (today,))
    revenue = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM((price - raw_price) * qty),0) FROM sales WHERE DATE(ts)=? AND COALESCE(payment_status, 'Paid') <> 'Void'", (today,))
    profit = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(quantity,0) FROM items WHERE name=? ORDER BY id ASC LIMIT 1", ("CHB Blocks",))
    chb_stock = cursor.fetchone()
    chb_stock = chb_stock[0] if chb_stock else 0

    cursor.execute("""
        SELECT
            CASE
                WHEN COALESCE(transaction_id, '') != '' THEN transaction_id
                ELSE 'TXN-' || printf('%05d', MIN(id))
            END AS txn_ref,
            MAX(ts) AS latest_ts,
            GROUP_CONCAT(item_name, ', ') AS items,
            COUNT(*) AS item_count,
            COALESCE(SUM(qty), 0) AS total_qty,
            COALESCE(SUM(total), 0) AS total_amount,
            COALESCE(NULLIF(MAX(cashier), ''), 'Admin') AS cashier_name,
            COALESCE(NULLIF(MAX(payment_status), ''), 'Paid') AS status
        FROM sales
        WHERE DATE(ts) = ?
          AND COALESCE(payment_status, 'Paid') <> 'Void'
        GROUP BY CASE
            WHEN COALESCE(transaction_id, '') != '' THEN transaction_id
            ELSE ts
        END
        ORDER BY latest_ts DESC
    """, (today,))
    recent = cursor.fetchall()
    recent_day_count = len(recent)
    recent_day_label = datetime.strptime(today, "%Y-%m-%d").strftime("%B %d, %Y")

    cursor.execute("""
        SELECT name, quantity
        FROM items
        WHERE quantity < 10
        ORDER BY quantity ASC
    """)
    low_stock = cursor.fetchall()

    cursor.execute("""
        SELECT item_name, SUM(qty) as total_qty
        FROM sales
        WHERE DATE(ts)=?
          AND COALESCE(payment_status, 'Paid') <> 'Void'
        GROUP BY item_name
        ORDER BY total_qty DESC
        LIMIT 3
    """, (today,))
    top_selling = cursor.fetchall()

    cursor.execute("""
        SELECT STRFTIME('%H', ts) AS sale_hour, COALESCE(SUM(total), 0)
        FROM sales
        WHERE DATE(ts)=?
          AND COALESCE(payment_status, 'Paid') <> 'Void'
        GROUP BY sale_hour
        ORDER BY sale_hour ASC
    """, (today,))
    revenue_by_hour = [(f"{int(hour):02d}:00", total or 0) for hour, total in cursor.fetchall() if hour is not None]

    cursor.execute("""
        SELECT
            COALESCE(SUM(total), 0),
            COALESCE(SUM(raw_price * qty), 0)
        FROM sales
        WHERE DATE(ts)=?
          AND COALESCE(payment_status, 'Paid') <> 'Void'
    """, (today,))
    revenue_total, cost_total = cursor.fetchone()
    revenue_total = revenue_total or 0
    cost_total = cost_total or 0
    estimated_profit = revenue_total - cost_total

    cursor.execute("""
        SELECT
            COALESCE(total_produced, 0),
            COALESCE(total_sold, 0),
            COALESCE(available, 0)
        FROM chb_inventory_state
        WHERE id = 1
    """)
    chb_state_row = cursor.fetchone()
    chb_state = chb_state_row if chb_state_row else (0, 0, chb_stock or 0)

    cursor.execute("""
        SELECT item_name, COALESCE(SUM(qty), 0)
        FROM sales
        WHERE DATE(ts)=?
          AND COALESCE(payment_status, 'Paid') <> 'Void'
        GROUP BY item_name
        ORDER BY SUM(qty) DESC
        LIMIT 5
    """, (today,))
    top_items_chart = cursor.fetchall()

    conn.commit()
    conn.close()

    return {
        "revenue": revenue,
        "profit": profit,
        "chb_stock": chb_stock,
        "recent": recent,
        "recent_day_count": recent_day_count,
        "recent_day_label": recent_day_label,
        "low_stock": low_stock,
        "top_selling": top_selling,
        "analytics": {
            "revenue_by_hour": revenue_by_hour,
            "profit_breakdown": {
                "revenue": revenue_total,
                "cost": cost_total,
                "profit": estimated_profit,
            },
            "chb_state": {
                "total_produced": chb_state[0],
                "total_sold": chb_state[1],
                "available": chb_state[2],
            },
            "top_items": top_items_chart,
        },
    }
