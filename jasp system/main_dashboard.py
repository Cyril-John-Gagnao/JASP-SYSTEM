import tkinter as tk
from tkinter import ttk
import sqlite3
import os
from datetime import datetime
from inventory_module import open_inventory
from pos_module import open_pos
from chb_module import open_chb_dashboard
from reports_module import open_reports
from User_management.user_gui import open_user_management
from window_utils import enable_centered_toplevels

enable_centered_toplevels()

DB_NAME = os.path.join(os.path.dirname(__file__), "data", "jasp.db")
BG_PAGE = "#edeff3"
BG_SIDEBAR = "#273142"
BG_CARD = "#ffffff"
TEXT_PRIMARY = "#1f2933"
TEXT_MUTED = "#6b7280"
ACCENT = "#8d93aa"
LINE = "#e5e7eb"


def spacer(parent, h=12):
    tk.Frame(parent, height=h, bg=parent["bg"]).pack(fill="x")


def stat_card(parent, title, value, subtitle=""):
    card = tk.Frame(parent, bg=BG_CARD, bd=0, relief="flat",
                    highlightthickness=1, highlightbackground=LINE)
    card.pack(side="left", expand=True, fill="both", padx=8)

    tk.Label(card, text=title.upper(), bg=BG_CARD, fg=TEXT_MUTED,
             font=("Arial", 10, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
    tk.Label(card, text=value, bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 22, "bold")).pack(anchor="w", padx=16)
    if subtitle:
        tk.Label(card, text=subtitle, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Arial", 9)).pack(anchor="w", padx=16, pady=(0, 14))
    return card


def build_table(parent, columns, rows):
    style = ttk.Style()
    style.configure("Dash.Treeview", font=("Arial", 10), rowheight=26,
                    background=BG_CARD, fieldbackground=BG_CARD)
    style.configure("Dash.Treeview.Heading", font=("Arial", 10, "bold"), foreground=TEXT_PRIMARY)
    style.map("Dash.Treeview", background=[("selected", ACCENT)])

    # Extract column IDs from columns tuples
    col_ids = [col for col, _, _ in columns]
    tree = ttk.Treeview(parent, columns=col_ids, show="headings", style="Dash.Treeview", height=6)
    for col, heading, width in columns:
        tree.heading(col, text=heading)
        tree.column(col, anchor="w", width=width, stretch=True)
    for row in rows:
        tree.insert("", "end", values=row)

    vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(0, weight=1)
    return tree


def render_table_or_empty(container, columns, rows, empty_text):
    """
    Render a table when rows exist; otherwise show a muted empty-state message.
    """
    if rows:
        build_table(container, columns, rows)
    else:
        tk.Label(container, text=empty_text, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Arial", 11, "italic")).pack(expand=True, fill="both", pady=12)


def fetch_dashboard_data():
    """Gather dynamic metrics from the database."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Ensure tables exist so queries do not fail
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            raw_price REAL DEFAULT 0
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

    today = datetime.now().strftime("%Y-%m-%d")

    # KPIs
    cursor.execute("SELECT COALESCE(SUM(total),0) FROM sales WHERE DATE(ts)=?", (today,))
    revenue = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM((price - raw_price) * qty),0) FROM sales WHERE DATE(ts)=?", (today,))
    profit = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(quantity,0) FROM items WHERE name=? ORDER BY id ASC LIMIT 1", ("CHB Blocks",))
    chb_stock = cursor.fetchone()
    chb_stock = chb_stock[0] if chb_stock else 0

    # Recent transactions (latest 5, sales + restocks)
    cursor.execute("""
        SELECT 'Sale' as kind, id, ts, item_name, qty, total
        FROM sales
        UNION ALL
        SELECT 'Restock' as kind, id, ts, item_name, qty, total_cost
        FROM restocks
        ORDER BY ts DESC
        LIMIT 5
    """)
    recent = cursor.fetchall()

    # Low stock (<10)
    cursor.execute("""
        SELECT name, quantity
        FROM items
        WHERE quantity < 10
        ORDER BY quantity ASC
    """)
    low_stock = cursor.fetchall()

    # Top selling today
    cursor.execute("""
        SELECT item_name, SUM(qty) as total_qty
        FROM sales
        WHERE DATE(ts)=?
        GROUP BY item_name
        ORDER BY total_qty DESC
        LIMIT 3
    """, (today,))
    top_selling = cursor.fetchall()

    conn.close()

    return {
        "revenue": revenue,
        "profit": profit,
        "chb_stock": chb_stock,
        "recent": recent,
        "low_stock": low_stock,
        "top_selling": top_selling,
    }


def open_main(root, logout_callback=None):
    """Render dashboard inside existing root window (no new window)."""
    data = fetch_dashboard_data()

    root.title("JASP Dashboard")
    try:
        root.state("zoomed")
    except Exception:
        pass
    root.configure(bg=BG_PAGE)

    for child in root.winfo_children():
        child.destroy()

    # ================= SIDEBAR =================
    sidebar = tk.Frame(root, bg=BG_SIDEBAR, width=230)
    sidebar.pack(side="left", fill="y")

    tk.Label(sidebar, text="JASP Hardware", bg=BG_SIDEBAR, fg="white",
             font=("Arial", 18, "bold")).pack(anchor="w", padx=18, pady=(20, 0))
    tk.Label(sidebar, text="Management System", bg=BG_SIDEBAR, fg="#cbd5e1",
             font=("Arial", 10)).pack(anchor="w", padx=18, pady=(2, 18))

    def sidebar_btn(text, command=None):
        return tk.Button(
            sidebar,
            text=text,
            command=command,
            font=("Arial", 11),
            bg=BG_SIDEBAR,
            fg="#e2e8f0",
            activebackground="#36455b",
            activeforeground="white",
            bd=0,
            relief="flat",
            anchor="w",
            padx=20,
            pady=10
        )

    sidebar_btn("Dashboard Overview", lambda: None).pack(fill="x")
    sidebar_btn("Point of Sale (POS)", open_pos).pack(fill="x")
    sidebar_btn("Inventory Management", lambda: open_inventory(root)).pack(fill="x")
    sidebar_btn("CHB and Delivery Production", open_chb_dashboard).pack(fill="x")
    sidebar_btn("User Management", lambda: open_user_management(root)).pack(fill="x")
    sidebar_btn("Reports & Analytics", open_reports).pack(fill="x")
    sidebar_btn("Settings & Users", lambda: print("Settings clicked")).pack(fill="x")

    tk.Label(sidebar, bg=BG_SIDEBAR).pack(expand=True, fill="both")

    tk.Button(sidebar, text="Logout", bg="#dc2626", fg="white",
              font=("Arial", 11, "bold"), relief="flat", bd=0,
              command=(logout_callback if logout_callback else root.destroy), padx=16, pady=10,
              activebackground="#b91c1c").pack(fill="x", padx=18, pady=16)

    # ================= MAIN CONTENT =================
    main_area = tk.Frame(root, bg=BG_PAGE)
    main_area.pack(side="right", fill="both", expand=True)

    header = tk.Frame(main_area, bg=BG_CARD, height=64, highlightthickness=1,
                      highlightbackground=LINE)
    header.pack(fill="x")
    tk.Label(header, text="Dashboard Overview", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 18, "bold")).pack(side="left", padx=20, pady=14)
    tk.Button(header, text="Refresh Data", bg=ACCENT, fg=TEXT_PRIMARY,
              font=("Arial", 10, "bold"), relief="flat", bd=0,
              padx=12, pady=8,
              command=lambda: open_main(root, logout_callback)).pack(side="right", padx=14, pady=10)
    tk.Button(header, text="Open Inventory", bg="#2563eb", fg="white",
              font=("Arial", 10, "bold"), relief="flat", bd=0,
              padx=12, pady=8,
              command=lambda: open_inventory(root)).pack(side="right", padx=6, pady=10)

    content = tk.Frame(main_area, bg=BG_PAGE)
    content.pack(fill="both", expand=True, padx=18, pady=18)

    # Top stats row
    stats_row = tk.Frame(content, bg=BG_PAGE)
    stats_row.pack(fill="x")
    def money(val):
        return f"₱ {val:,.2f}"

    stat_card(stats_row, "Today's Revenue", money(data["revenue"]), "")
    stat_card(stats_row, "Est. Profit (Today)", money(data["profit"]), "")
    stat_card(stats_row, "CHB Stock Available", f"{data['chb_stock']:,}", "pcs")

    spacer(content, 14)

    # Middle row (Recent transactions + Low stock)
    mid_row = tk.Frame(content, bg=BG_PAGE)
    mid_row.pack(fill="both", expand=True)

    recent_card = tk.Frame(mid_row, bg=BG_CARD, highlightthickness=1,
                           highlightbackground=LINE, height=260)
    recent_card.pack(side="left", fill="both", expand=True, padx=(0, 12))
    recent_card.pack_propagate(False)
    tk.Label(recent_card, text="Recent Transactions (Preview)", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=(12, 4))
    tk.Button(recent_card, text="View All", relief="flat", bd=0, bg=BG_CARD,
              fg="#2563eb", font=("Arial", 10, "bold"),
              activebackground=ACCENT, activeforeground="#1d4ed8").pack(
        anchor="e", padx=16, pady=(0, 6))

    table_container = tk.Frame(recent_card, bg=BG_CARD, padx=12, pady=6)
    table_container.pack(fill="both", expand=True)
    recent_cols = [
        ("receipt", "Type/Ref", 120),
        ("time", "Time", 90),
        ("items", "Items", 260),
        ("amount", "Amount", 110),
    ]
    recent_rows = []
    for kind, rid, ts, item_name, qty, total in data["recent"]:
        tstr = datetime.strptime(ts, "%Y-%m-%d %H:%M:%S").strftime("%I:%M %p")
        ref = f"{'SL' if kind=='Sale' else 'RS'}-{rid:04d}"
        label = f"{kind}: {item_name} ({qty})"
        recent_rows.append((ref, tstr, label, money(total)))
    render_table_or_empty(table_container, recent_cols, recent_rows, "No transactions today.")

    low_card = tk.Frame(mid_row, bg=BG_CARD, width=260, highlightthickness=1,
                        highlightbackground=LINE, height=260)
    low_card.pack(side="left", fill="y", padx=(12, 0))
    low_card.pack_propagate(False)
    tk.Label(low_card, text="Low Stock Alerts (Preview)", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=12)

    alert_container = tk.Frame(low_card, bg=BG_CARD)
    alert_container.pack(fill="both", expand=True, padx=10, pady=(0, 12))
    if data["low_stock"]:
        for item, qty in data["low_stock"]:
            row = tk.Frame(alert_container, bg=BG_CARD)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=item, bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 10)).pack(
                side="left", padx=6, pady=4)
            tk.Label(row, text=f"{qty} pcs", bg="#336bdb", fg=TEXT_PRIMARY, font=("Arial", 10, "bold"),
                     padx=10, pady=4).pack(side="right", padx=6)
    else:
        tk.Label(alert_container, text="No items below threshold.", bg=BG_CARD,
                 fg=TEXT_MUTED, font=("Arial", 10, "italic")).pack(anchor="w", padx=6, pady=12)

    spacer(content, 14)

    # Bottom row (Top selling + Generate reports)
    bottom_row = tk.Frame(content, bg=BG_PAGE)
    bottom_row.pack(fill="both", expand=True)

    top_sell_card = tk.Frame(bottom_row, bg=BG_CARD, highlightthickness=1,
                             highlightbackground=LINE, height=220)
    top_sell_card.pack(side="left", fill="both", expand=True, padx=(0, 12))
    top_sell_card.pack_propagate(False)
    tk.Label(top_sell_card, text="Most Items Sold Today (Preview)", bg=BG_CARD,
             fg=TEXT_PRIMARY, font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=12)

    sell_container = tk.Frame(top_sell_card, bg=BG_CARD, padx=12, pady=6)
    sell_container.pack(fill="both", expand=True)
    sell_cols = [
        ("item", "Item Description", 250),
        ("qty", "Qty Sold", 120),
    ]
    sell_rows = [(name, f"{qty} pcs") for name, qty in data["top_selling"]]
    render_table_or_empty(sell_container, sell_cols, sell_rows, "No sales yet today.")

    reports_card = tk.Frame(bottom_row, bg=BG_CARD, width=260, highlightthickness=1,
                            highlightbackground=LINE, height=220)
    reports_card.pack(side="left", fill="y", padx=(12, 0))
    reports_card.pack_propagate(False)
    tk.Label(reports_card, text="Generate Reports", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=12)

    for label in ["Today", "This Week", "This Month"]:
        tk.Button(reports_card, text=label, font=("Arial", 11, "bold"),
                  bg=ACCENT, fg=TEXT_PRIMARY, relief="flat", bd=0,
                  activebackground="#dfe3ea", padx=10, pady=10,
                  command=lambda l=label: print(f"Generate {l} report")).pack(
            fill="x", padx=16, pady=6)


if __name__ == "__main__":
    root = tk.Tk()
    open_main(root)
    root.mainloop()
