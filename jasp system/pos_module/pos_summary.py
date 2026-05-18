import os
import sqlite3
import tkinter as tk
from datetime import datetime
from tkinter import messagebox
from tkinter import ttk
from tkinter import font as tkfont

from jasp_theme import DASHBOARD_CONTENT_BG
from main_dashboard.main_functions import (
    BG_CARD,
    PRIMARY,
    TEXT_MUTED,
    TEXT_PRIMARY,
    center_window,
    compact_items,
    compact_txn_id,
    compute_summary_range,
    format_dashboard_datetime,
    money,
    open_date_calendar,
)
from pos_module.pos_database import DB_NAME


SUMMARY_BG = DASHBOARD_CONTENT_BG


def ensure_receipt_columns(cursor):
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
    sales_cols = {col[1] for col in cursor.fetchall()}
    migrations = {
        "transaction_id": "ALTER TABLE sales ADD COLUMN transaction_id TEXT DEFAULT ''",
        "cashier": "ALTER TABLE sales ADD COLUMN cashier TEXT DEFAULT ''",
        "payment_status": "ALTER TABLE sales ADD COLUMN payment_status TEXT DEFAULT 'Paid'",
        "payment_method": "ALTER TABLE sales ADD COLUMN payment_method TEXT DEFAULT 'Cash'",
        "receipt_path": "ALTER TABLE sales ADD COLUMN receipt_path TEXT DEFAULT ''",
    }
    for column_name, sql in migrations.items():
        if column_name not in sales_cols:
            cursor.execute(sql)


def fetch_receipt_rows(cursor, start, end):
    ensure_receipt_columns(cursor)
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
            COALESCE(NULLIF(MAX(payment_status), ''), 'Paid') AS status,
            COALESCE(NULLIF(MAX(receipt_path), ''), '') AS receipt_path
        FROM sales
        WHERE DATE(ts) BETWEEN ? AND ?
        GROUP BY CASE
            WHEN COALESCE(transaction_id, '') != '' THEN transaction_id
            ELSE ts
        END
        ORDER BY latest_ts DESC
    """, (start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")))
    return cursor.fetchall()


def open_pos_summary(parent):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    ensure_receipt_columns(cursor)
    conn.commit()

    summary_win = tk.Toplevel(parent)
    summary_win.title("POS Receipt Summary")
    summary_win.configure(bg=SUMMARY_BG)
    summary_win.transient(parent)
    summary_win._large_calendar = True

    period_var = tk.StringVar(value="Day")
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    title_var = tk.StringVar()
    totals_var = tk.StringVar()

    headings = [
        ("txn", "Receipt ID", 95, 150, "w"),
        ("date", "Date & Time", 170, 240, "w"),
        ("items", "Item(s)", 230, 380, "w"),
        ("qty", "Qty", 75, 120, "e"),
        ("total", "Total", 110, 160, "e"),
        ("cashier", "Cashier", 110, 180, "w"),
        ("status", "Status", 90, 130, "center"),
        ("location", "Receipt Location", 320, 520, "w"),
    ]

    def title_text():
        start, end = compute_summary_range(period_var.get(), date_var.get())
        if period_var.get() == "Day":
            return f"POS Receipts - {start.strftime('%B %d, %Y')}"
        if period_var.get() == "Week":
            return f"POS Receipts - {start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
        return f"POS Receipts - {start.strftime('%B %Y')}"

    def clear_tree():
        for item in summary_tree.get_children():
            summary_tree.delete(item)

    def auto_adjust_columns():
        body_font = tkfont.Font(font=("Arial", 15))
        heading_font = tkfont.Font(font=("Arial", 14, "bold"))
        tree_columns = list(summary_tree["columns"])
        for col, heading, min_width, max_width, anchor in headings:
            col_index = tree_columns.index(col)
            width = max(min_width, heading_font.measure(heading) + 28)
            for item in summary_tree.get_children():
                values = summary_tree.item(item, "values")
                if col_index < len(values):
                    width = max(width, body_font.measure(str(values[col_index])) + 34)
            width = min(width, max_width)
            summary_tree.column(col, width=width, minwidth=min_width, anchor=anchor, stretch=False)

    def open_receipt_location(path):
        if not path or path == "Not downloaded":
            messagebox.showinfo("Receipt Location", "This receipt has not been downloaded yet.", parent=summary_win)
            return
        if not os.path.exists(path):
            messagebox.showwarning("Receipt Missing", f"The receipt file was not found:\n{path}", parent=summary_win)
            return
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("Open Failed", f"Unable to open receipt:\n{exc}", parent=summary_win)

    def on_tree_click(event):
        if summary_tree.identify_column(event.x) != f"#{len(headings)}":
            return
        row_id = summary_tree.identify_row(event.y)
        if not row_id:
            return
        values = summary_tree.item(row_id, "values")
        if values:
            open_receipt_location(values[-1])

    def load_summary():
        start, end = compute_summary_range(period_var.get(), date_var.get())
        rows = fetch_receipt_rows(cursor, start, end)
        clear_tree()

        paid_total = 0
        paid_count = 0
        void_count = 0
        if not rows:
            summary_tree.insert(
                "",
                "end",
                values=("", "", "No POS transactions for the selected period.", "", "", "", "", ""),
                tags=("even",),
            )
        for index, row in enumerate(rows):
            txn_ref, ts, items, item_count, qty, total, cashier, status, receipt_path = row
            status = status or "Paid"
            if status == "Void":
                void_count += 1
            else:
                paid_count += 1
                paid_total += total or 0
            summary_tree.insert(
                "",
                "end",
                values=(
                    compact_txn_id(txn_ref),
                    format_dashboard_datetime(ts),
                    compact_items(items, item_count),
                    f"{int(qty or 0):,}",
                    money(total or 0),
                    cashier or "Admin",
                    status,
                    receipt_path or "Not downloaded",
                ),
                tags=("even" if index % 2 == 0 else "odd",),
            )

        title_var.set(title_text())
        totals_var.set(
            f"Receipts: {len(rows):,}   |   Paid: {paid_count:,}   |   Void: {void_count:,}   |   Paid Sales: {money(paid_total)}"
        )
        auto_adjust_columns()

    controls = tk.Frame(summary_win, bg=SUMMARY_BG)
    controls.pack(fill="x", padx=16, pady=(14, 8))
    button_options = {
        "fg": "white",
        "font": ("Arial", 13, "bold"),
        "relief": "solid",
        "bd": 2,
        "highlightbackground": "black",
        "highlightcolor": "black",
        "highlightthickness": 1,
        "padx": 12,
        "pady": 7,
    }
    tk.Label(controls, text="Period:", bg=SUMMARY_BG, fg=TEXT_PRIMARY, font=("Arial", 18, "bold")).pack(side="left", padx=(0, 8))
    for period in ("Day", "Week", "Month"):
        tk.Radiobutton(
            controls,
            text=period,
            variable=period_var,
            value=period,
            bg=SUMMARY_BG,
            fg=TEXT_PRIMARY,
            font=("Arial", 17),
            command=load_summary,
        ).pack(side="left", padx=5)
    tk.Label(controls, text="Date:", bg=SUMMARY_BG, fg=TEXT_PRIMARY, font=("Arial", 18, "bold")).pack(side="left", padx=(24, 8))
    tk.Entry(controls, textvariable=date_var, width=13, font=("Arial", 17), relief="solid", bd=2).pack(side="left", padx=4)
    tk.Button(controls, text="Calendar", command=lambda: open_date_calendar(summary_win, date_var, load_summary), bg=PRIMARY, **button_options).pack(side="left", padx=4)
    tk.Button(controls, text="Apply", command=load_summary, bg=PRIMARY, **button_options).pack(side="left", padx=4)
    tk.Button(controls, text="Close", command=summary_win.destroy, bg="#dc2626", **button_options).pack(side="right")

    tk.Label(summary_win, textvariable=title_var, bg=SUMMARY_BG, fg=PRIMARY, font=("Arial", 22, "bold")).pack(anchor="w", padx=16)
    tk.Label(summary_win, textvariable=totals_var, bg=SUMMARY_BG, fg=TEXT_PRIMARY, font=("Arial", 16, "bold")).pack(anchor="w", padx=16, pady=(2, 8))
    hint_label = tk.Label(
        summary_win,
        text="Click a receipt location to open the downloaded PDF.",
        bg="#fef3c7",
        fg="#92400e",
        font=("Arial", 15, "bold"),
        relief="solid",
        bd=1,
        padx=12,
        pady=6,
    )
    hint_label.pack(anchor="w", padx=16, pady=(0, 8))

    table_frame = tk.Frame(summary_win, bg=BG_CARD)
    table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
    columns = tuple(col for col, _heading, _width, _anchor in headings)
    style = ttk.Style()
    style.configure("PosSummary.Treeview", font=("Arial", 15), rowheight=42, background=BG_CARD, fieldbackground=BG_CARD)
    style.configure("PosSummary.Treeview.Heading", font=("Arial", 14, "bold"), foreground=TEXT_PRIMARY)
    summary_tree = ttk.Treeview(table_frame, columns=columns, show="headings", style="PosSummary.Treeview")
    vsb = ttk.Scrollbar(table_frame, orient="vertical", command=summary_tree.yview)
    hsb = ttk.Scrollbar(table_frame, orient="horizontal", command=summary_tree.xview)
    summary_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    summary_tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    table_frame.grid_rowconfigure(0, weight=1)
    table_frame.grid_columnconfigure(0, weight=1)
    for col, heading, width, _max_width, anchor in headings:
        summary_tree.heading(col, text=heading)
        summary_tree.column(col, width=width, minwidth=width, anchor=anchor, stretch=False)
    summary_tree.tag_configure("even", background="#e0f2fe", foreground=TEXT_PRIMARY)
    summary_tree.tag_configure("odd", background="#ffffff", foreground=TEXT_PRIMARY)
    summary_tree.bind("<ButtonRelease-1>", on_tree_click)

    def on_close():
        conn.close()
        summary_win.destroy()

    summary_win.protocol("WM_DELETE_WINDOW", on_close)
    load_summary()
    center_window(summary_win, 1180, 640, parent)
