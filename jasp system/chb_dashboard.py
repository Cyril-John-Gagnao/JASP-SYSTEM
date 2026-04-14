import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import os

DB_NAME = os.path.join(os.path.dirname(__file__), "jasp.db")
CHB_ITEM_NAME = "CHB Blocks"

# 🎨 COLORS
BG_MAIN = "#eef6ff"
CARD_BG = "#ffffff"
PRIMARY = "#2563eb"
ACCENT = "#60a5fa"
TEXT = "#1e293b"
BORDER = "#dbeafe"


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
            ts TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            quantity INTEGER,
            price REAL,
            raw_price REAL
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

    conn.commit()
    conn.close()


def sync_chb_inventory(conn, cursor):
    """Mirror CHB stock in the inventory table (production minus sales)."""
    cursor.execute("SELECT COALESCE(SUM(total_blocks),0) FROM chb_production")
    produced = cursor.fetchone()[0] or 0

    cursor.execute("SELECT COALESCE(SUM(qty),0) FROM sales WHERE item_name=?", (CHB_ITEM_NAME,))
    sold = cursor.fetchone()[0] or 0

    stock = max(produced - sold, 0)

    cursor.execute("SELECT id FROM items WHERE name=?", (CHB_ITEM_NAME,))
    row = cursor.fetchone()
    if row:
        cursor.execute("UPDATE items SET quantity=? WHERE id=?", (stock, row[0]))
    else:
        cursor.execute(
            "INSERT INTO items (name, quantity, price, raw_price) VALUES (?, ?, ?, ?)",
            (CHB_ITEM_NAME, stock, 0, 0)
        )
    conn.commit()


# ================= MAIN =================
def open_chb_dashboard():
    init_db()

    win = tk.Toplevel()
    win.title("CHB Production Module")
    win.state("zoomed")
    win.configure(bg=BG_MAIN)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    sync_chb_inventory(conn, cursor)

    cursor.execute("SELECT pay_rate FROM chb_production ORDER BY ts DESC LIMIT 1")
    last_rate = cursor.fetchone()
    if last_rate and last_rate[0] is not None:
        try:
            pay_rate_default = float(last_rate[0])
        except Exception:
            pay_rate_default = 200
    else:
        pay_rate_default = 200

    selected_id = tk.StringVar()

    # ================= HEADER WITH CENTER TITLE =================
    header_frame = tk.Frame(win, bg=BG_MAIN)
    header_frame.pack(fill="x", padx=20, pady=10)

    # Configure grid (3 columns)
    header_frame.columnconfigure(0, weight=1)  # left space
    header_frame.columnconfigure(1, weight=1)  # center
    header_frame.columnconfigure(2, weight=1)  # right space

    # CENTER: Title
    tk.Label(
        header_frame,
        text="CHB Production Management",
        font=("Arial", 18, "bold"),
        bg=BG_MAIN,
        fg=PRIMARY
    ).grid(row=0, column=1)

    # RIGHT: Back Button
    def go_back():
        win.destroy()
        import main_dashboard
        main_dashboard.open_main()

    tk.Button(
        header_frame,
        text="← Back",
        command=go_back,
        bg="#2563eb",
        fg="white",
        font=("Arial", 10, "bold"),
        padx=12,
        pady=5,
        relief="flat"
    ).grid(row=0, column=2, sticky="e")

    # ================= SEARCH =================
    search_frame = tk.Frame(win, bg=BG_MAIN)
    search_frame.pack(fill="x", padx=20, pady=(0, 10))

    tk.Label(search_frame, text="🔍 Search:", bg=BG_MAIN, fg=TEXT)\
        .pack(side="left", padx=5)

    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var, width=30)
    search_entry.pack(side="left", padx=5)

    tk.Label(search_frame, text="Sort By:", bg=BG_MAIN, fg=TEXT)\
        .pack(side="left", padx=(20, 5))

    sort_var = tk.StringVar(value="Date (Newest)")

    sort_menu = ttk.Combobox(
        search_frame,
        textvariable=sort_var,
        values=["Date (Newest)", "Worker Name"],
        state="readonly",
        width=18
    )
    sort_menu.pack(side="left")

    # ================= FORM =================
    card = tk.Frame(win, bg=CARD_BG, bd=1, relief="solid")
    card.pack(padx=20, pady=10, fill="x")

    form = tk.Frame(card, bg=CARD_BG)
    form.pack(pady=15, padx=20)

    tk.Label(form, text="Production Date", bg=CARD_BG).grid(row=0, column=0)
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    tk.Entry(form, textvariable=date_var).grid(row=0, column=1)

    tk.Label(form, text="Worker Name", bg=CARD_BG).grid(row=1, column=0)
    worker_entry = tk.Entry(form)
    worker_entry.grid(row=1, column=1)

    tk.Label(form, text="Cement Bags", bg=CARD_BG).grid(row=2, column=0)
    cement_entry = tk.Entry(form)
    cement_entry.grid(row=2, column=1)

    tk.Label(form, text="Fine Sand (Auto)", bg=CARD_BG).grid(row=3, column=0)
    sand_entry = tk.Entry(form)
    sand_entry.grid(row=3, column=1)

    tk.Label(form, text="Pay / 150 Blocks", bg=CARD_BG).grid(row=4, column=0)
    pay_rate_var = tk.DoubleVar(value=pay_rate_default)
    pay_rate_entry = tk.Entry(form, textvariable=pay_rate_var)
    pay_rate_entry.grid(row=4, column=1)

    result_label = tk.Label(
        card,
        text="Blocks: 0 | Pay: ₱0",
        font=("Arial", 12, "bold"),
        bg=CARD_BG,
        fg=PRIMARY
    )
    result_label.pack(pady=10)

    # ================= AUTO CALC =================
    def auto_sand(event=None):
        try:
            cement = int(cement_entry.get() or 0)

            sand = cement * 15
            sand_entry.delete(0, tk.END)
            sand_entry.insert(0, str(sand))

            blocks = cement * 150
            pay = cement * float(pay_rate_var.get() or 0)

            result_label.config(text=f"Blocks: {blocks:,} | Pay: ₱{pay:,}")

        except:
            sand_entry.delete(0, tk.END)
            result_label.config(text="Blocks: 0 | Pay: ₱0")

    cement_entry.bind("<KeyRelease>", auto_sand)
    pay_rate_entry.bind("<KeyRelease>", auto_sand)

    # ================= FUNCTIONS =================
    def clear_form():
        worker_entry.delete(0, tk.END)
        cement_entry.delete(0, tk.END)
        sand_entry.delete(0, tk.END)
        result_label.config(text="Blocks: 0 | Pay: ₱0")
        selected_id.set("")

    def save():
        try:
            cement = int(cement_entry.get())
            sand = cement * 15
            blocks = cement * 150
            pay_rate = float(pay_rate_var.get())
            pay = cement * pay_rate
        except:
            messagebox.showerror("Error", "Invalid input", parent=win)
            return

        worker = worker_entry.get()
        date = date_var.get()

        if not worker:
            messagebox.showerror("Error", "Fill all fields", parent=win)
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO chb_production
            (production_date, worker_name, cement_bags, fine_sand, total_blocks, pay, pay_rate, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (date, worker, cement, sand, blocks, pay, pay_rate, ts))

        conn.commit()
        sync_chb_inventory(conn, cursor)
        load_data()
        clear_form()

    def update():
        if not selected_id.get():
            messagebox.showerror("Error", "Select a record", parent=win)
            return

        try:
            cement = int(cement_entry.get())
            sand = cement * 15
            blocks = cement * 150
            pay_rate = float(pay_rate_var.get())
            pay = cement * pay_rate
        except:
            messagebox.showerror("Error", "Invalid input", parent=win)
            return

        cursor.execute("""
            UPDATE chb_production
            SET production_date=?, worker_name=?, cement_bags=?, fine_sand=?, total_blocks=?, pay=?, pay_rate=?
            WHERE id=?
        """, (
            date_var.get(),
            worker_entry.get(),
            cement, sand, blocks, pay, pay_rate,
            selected_id.get()
        ))

        conn.commit()
        sync_chb_inventory(conn, cursor)
        load_data()
        clear_form()

    def delete():
        if not selected_id.get():
            return

        cursor.execute("DELETE FROM chb_production WHERE id=?", (selected_id.get(),))
        conn.commit()
        sync_chb_inventory(conn, cursor)
        load_data()
        clear_form()

    # ================= TABLE =================
    table_card = tk.Frame(win, bg=CARD_BG)
    table_card.pack(fill="both", expand=True, padx=20, pady=10)

    columns = ("id", "date", "worker", "cement", "sand", "blocks", "pay")
    tree = ttk.Treeview(table_card, columns=columns, show="headings")

    for col in columns:
        tree.heading(col, text=col.upper())
        tree.column(col, anchor="center", width=120)

    tree.pack(fill="both", expand=True)

    def on_select(event):
        selected = tree.focus()
        values = tree.item(selected, "values")

        if values:
            selected_id.set(values[0])
            date_var.set(values[1])

            worker_entry.delete(0, tk.END)
            worker_entry.insert(0, values[2])

            cement_entry.delete(0, tk.END)
            cement_entry.insert(0, values[3])

            sand_entry.delete(0, tk.END)
            sand_entry.insert(0, values[4])

            cursor.execute("SELECT pay_rate FROM chb_production WHERE id=?", (values[0],))
            pr = cursor.fetchone()
            pay_rate_var.set(pr[0] if pr and pr[0] is not None else 200)
            auto_sand()

    tree.bind("<ButtonRelease-1>", on_select)

    # ================= LOAD DATA =================
    def load_data(event=None):
        for row in tree.get_children():
            tree.delete(row)

        keyword = search_var.get().lower()
        sort_option = sort_var.get()

        query = """
            SELECT id, production_date, worker_name, cement_bags, fine_sand, total_blocks, pay
            FROM chb_production
        """

        params = []

        if keyword:
            query += " WHERE LOWER(worker_name) LIKE ? OR production_date LIKE ?"
            params.extend([f"%{keyword}%", f"%{keyword}%"])

        if sort_option == "Worker Name":
            query += " ORDER BY worker_name ASC"
        else:
            query += " ORDER BY ts DESC"

        cursor.execute(query, params)

        for row in cursor.fetchall():
            tree.insert("", "end", values=row)

    # ✅ BINDINGS (LIVE SEARCH)
    search_entry.bind("<KeyRelease>", load_data)
    sort_menu.bind("<<ComboboxSelected>>", load_data)

    # ================= BUTTONS =================
    btn_frame = tk.Frame(win, bg=BG_MAIN)
    btn_frame.pack(pady=10)

    tk.Button(btn_frame, text="Save", command=save, bg="#16a34a", fg="white").grid(row=0, column=0, padx=5)
    tk.Button(btn_frame, text="Update", command=update, bg="#2563eb", fg="white").grid(row=0, column=1, padx=5)
    tk.Button(btn_frame, text="Delete", command=delete, bg="#dc2626", fg="white").grid(row=0, column=2, padx=5)
    tk.Button(btn_frame, text="Clear", command=clear_form, bg="#64748b", fg="white").grid(row=0, column=3, padx=5)

    # ✅ INITIAL LOAD
    load_data()
