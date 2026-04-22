import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime, timedelta
import os
from delivery_section import open_delivery_window

DB_NAME = os.path.join(os.path.dirname(__file__), "jasp.db")
CHB_ITEM_NAME = "CHB Blocks"
CHB_DEFAULT_UNIT = "pieces"

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
            raw_price REAL,
            unit TEXT DEFAULT ''
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
    cursor.execute("PRAGMA table_info(items)")
    item_cols = [col[1] for col in cursor.fetchall()]
    if "unit" not in item_cols:
        cursor.execute("ALTER TABLE items ADD COLUMN unit TEXT DEFAULT ''")

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
        cursor.execute(
            "UPDATE items SET quantity=?, unit=? WHERE id=?",
            (stock, CHB_DEFAULT_UNIT, row[0])
        )
    else:
        cursor.execute(
            "INSERT INTO items (name, quantity, price, raw_price, unit) VALUES (?, ?, ?, ?, ?)",
            (CHB_ITEM_NAME, stock, 0, 0, CHB_DEFAULT_UNIT)
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

    # RIGHT: Refresh and Back Buttons
    def go_back():
        win.destroy()
        import main_dashboard
        main_dashboard.open_main()

    def refresh_data():
        load_data()
        update_total_blocks()

    # Button container for Refresh and Back
    btn_container = tk.Frame(header_frame, bg=BG_MAIN)
    btn_container.grid(row=0, column=2, sticky="e")

    tk.Button(
        btn_container,
        text="🔄 Refresh",
        command=refresh_data,
        bg="#f59e0b",
        fg="white",
        font=("Arial", 10, "bold"),
        padx=12,
        pady=5,
        relief="flat"
    ).pack(side="left", padx=3)

    tk.Button(
        btn_container,
        text="← Back",
        command=go_back,
        bg="#2563eb",
        fg="white",
        font=("Arial", 10, "bold"),
        padx=12,
        pady=5,
        relief="flat"
    ).pack(side="left", padx=3)

    # ================= SEARCH =================
    search_frame = tk.Frame(win, bg=BG_MAIN)
    search_frame.pack(fill="x", padx=20, pady=(0, 15))

    tk.Label(search_frame, text="🔍 Search:", bg=BG_MAIN, fg=TEXT, font=("Arial", 12, "bold"))\
        .pack(side="left", padx=10, pady=10)

    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var, width=35, font=("Arial", 11), bd=2, relief="solid")
    search_entry.pack(side="left", padx=10, pady=10)

    tk.Label(search_frame, text="Sort By:", bg=BG_MAIN, fg=TEXT, font=("Arial", 12, "bold"))\
        .pack(side="left", padx=(30, 10), pady=10)

    sort_var = tk.StringVar(value="Date (Newest)")

    sort_menu = ttk.Combobox(
        search_frame,
        textvariable=sort_var,
        values=["Date (Newest)", "Worker Name"],
        state="readonly",
        width=22,
        font=("Arial", 11)
    )
    sort_menu.pack(side="left", pady=10)
    # Summary button (opens period summary dialog)
    def open_period_summary():
        def compute_range():
            p = period_var.get()
            if p == 'day':
                d = datetime.strptime(date_sel.get(), "%Y-%m-%d")
                start = d
                end = d
            elif p == 'week':
                d = datetime.strptime(date_sel.get(), "%Y-%m-%d")
                start = d - timedelta(days=d.weekday())
                end = start + timedelta(days=6)
            elif p == 'month':
                try:
                    m = months.index(month_var.get()) + 1
                    y = int(year_var.get())
                except Exception:
                    m = datetime.now().month
                    y = datetime.now().year
                start = datetime(y, m, 1)
                if m == 12:
                    end = datetime(y, 12, 31)
                else:
                    end = datetime(y, m + 1, 1) - timedelta(days=1)
            else:
                start = None
                end = None
            return start, end

        def load_summary():
            for r in summary_tree.get_children():
                summary_tree.delete(r)

            start, end = compute_range()
            params = []
            q = "SELECT worker_name, COALESCE(SUM(total_blocks),0) AS blocks, COALESCE(SUM(pay),0) AS pay FROM chb_production"
            if start and end:
                q += " WHERE production_date BETWEEN ? AND ?"
                params = [start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d")]
            q += " GROUP BY worker_name ORDER BY worker_name ASC"
            cursor.execute(q, params)
            rows = cursor.fetchall()
            total_blocks = 0
            total_pay = 0
            for i, row in enumerate(rows):
                worker, blocks, pay = row
                total_blocks += blocks
                total_pay += pay
                tag = 'evenrow' if i % 2 == 0 else 'oddrow'
                summary_tree.insert('', 'end', values=(worker, f"{blocks:,}", f"₱{pay:,.2f}"), tags=(tag,))
            totals_var.set(f"TOTAL: {len(rows)} workers | {total_blocks:,} blocks | ₱{total_pay:,.2f}")

        summary_win = tk.Toplevel(win)
        summary_win.title('Production Summary')
        summary_win.geometry('700x450')
        summary_win.configure(bg=BG_MAIN)

        top_frame = tk.Frame(summary_win, bg=BG_MAIN)
        top_frame.pack(fill='x', pady=8)

        period_var = tk.StringVar(value='day')
        tk.Radiobutton(top_frame, text='Day', variable=period_var, value='day', bg=BG_MAIN, command=load_summary).pack(side='left', padx=6)
        tk.Radiobutton(top_frame, text='Week', variable=period_var, value='week', bg=BG_MAIN, command=load_summary).pack(side='left', padx=6)
        tk.Radiobutton(top_frame, text='Month', variable=period_var, value='month', bg=BG_MAIN, command=load_summary).pack(side='left', padx=6)

        tk.Label(top_frame, text=' Date (YYYY-MM-DD):', bg=BG_MAIN).pack(side='left', padx=(20,4))
        date_sel = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))
        date_entry2 = tk.Entry(top_frame, textvariable=date_sel, width=12)
        date_entry2.pack(side='left', padx=4)

        months = ["January", "February", "March", "April", "May", "June",
                  "July", "August", "September", "October", "November", "December"]
        month_var = tk.StringVar(value=datetime.now().strftime('%B'))
        month_cb = ttk.Combobox(top_frame, values=months, textvariable=month_var, width=10, state='readonly')
        month_cb.pack(side='left', padx=6)

        year_var = tk.StringVar(value=str(datetime.now().year))
        years = [str(y) for y in range(datetime.now().year - 5, datetime.now().year + 1)]
        year_cb = ttk.Combobox(top_frame, values=years, textvariable=year_var, width=6, state='readonly')
        year_cb.pack(side='left', padx=6)

        tk.Button(top_frame, text='Apply', command=load_summary, bg='#3b82f6', fg='white').pack(side='left', padx=8)

        # Summary tree
        cols = ('worker', 'blocks', 'pay')
        summary_tree = ttk.Treeview(summary_win, columns=cols, show='headings')
        summary_tree.heading('worker', text='Worker')
        summary_tree.heading('blocks', text='Total Blocks')
        summary_tree.heading('pay', text='Total Pay')
        summary_tree.column('worker', width=250)
        summary_tree.column('blocks', width=120, anchor='center')
        summary_tree.column('pay', width=140, anchor='center')
        summary_tree.pack(fill='both', expand=True, padx=12, pady=8)
        summary_tree.tag_configure('oddrow', background='#ffffff')
        summary_tree.tag_configure('evenrow', background='#93c5fd')

        totals_var = tk.StringVar(value='')
        totals_lbl = tk.Label(summary_win, textvariable=totals_var, bg=BG_MAIN, font=('Arial', 11, 'bold'))
        totals_lbl.pack(fill='x', padx=12, pady=(0,10))

        load_summary()

    tk.Button(search_frame, text='Summary', command=open_period_summary, bg='#8b5cf6', fg='white', font=('Arial', 10, 'bold')).pack(side='left', padx=10)

    # ================= TOTAL HOLLOW BLOCKS DISPLAY =================
    total_frame = tk.Frame(win, bg=BG_MAIN)
    total_frame.pack(fill="x", padx=20, pady=(5, 10))

    total_blocks_var = tk.StringVar(value="Total Hollow Blocks Available: 0")

    total_label = tk.Label(
        total_frame,
        textvariable=total_blocks_var,
        font=("Arial", 14, "bold"),
        bg=BG_MAIN,
        fg="#1e40af"
    )
    total_label.pack(side="left")

    # ================= MAIN CONTAINER (60-40 Split) =================
    main_container = tk.Frame(win, bg=CARD_BG, bd=1, relief="solid")
    main_container.pack(padx=20, pady=10, fill="both", expand=True)

    # Configure columns: table (60%) and form (40%)
    main_container.columnconfigure(0, weight=3)  # table - 60%
    main_container.columnconfigure(1, weight=2)  # form - 40%
    main_container.rowconfigure(0, weight=1)

    # ================= FORM (RIGHT SIDE - 40%) =================
    form_card = tk.Frame(main_container, bg=CARD_BG)
    form_card.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
    form_card.columnconfigure(1, weight=1)

    # Form Title
    tk.Label(form_card, text="CHB Production", font=("Arial", 18, "bold"), bg=CARD_BG, fg=PRIMARY).pack(pady=(0, 20))

    # Form Background Frame
    form_bg = tk.Frame(form_card, bg="#fef3c7", bd=1, relief="flat")
    form_bg.pack(fill="x", padx=5, pady=10)

    form = tk.Frame(form_bg, bg="#fef3c7")
    form.pack(fill="x", padx=20, pady=20)

    # Production Date
    tk.Label(form, text="Production Date", bg="#fef3c7", font=("Arial", 11, "bold"), fg="#1e293b").grid(row=0, column=0, sticky="w", pady=10)
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    date_entry = tk.Entry(form, textvariable=date_var, width=20, font=("Arial", 11), bd=1, relief="solid", bg="white")
    date_entry.grid(row=0, column=1, sticky="ew", padx=15, pady=10)

    # Worker Name
    tk.Label(form, text="Worker Name", bg="#fef3c7", font=("Arial", 11, "bold"), fg="#1e293b").grid(row=1, column=0, sticky="w", pady=10)
    worker_entry = tk.Entry(form, width=20, font=("Arial", 11), bd=1, relief="solid", bg="white")
    worker_entry.grid(row=1, column=1, sticky="ew", padx=15, pady=10)

    # Cement Bags
    tk.Label(form, text="Bag/s of Cement", bg="#fef3c7", font=("Arial", 11, "bold"), fg="#1e293b").grid(row=2, column=0, sticky="w", pady=10)
    cement_entry = tk.Entry(form, width=20, font=("Arial", 11), bd=1, relief="solid", bg="white")
    cement_entry.grid(row=2, column=1, sticky="ew", padx=15, pady=10)

    # Bag of Fine Sand
    tk.Label(form, text="Bag/s of Fine Sand", bg="#fef3c7", font=("Arial", 11, "bold"), fg="#1e293b").grid(row=3, column=0, sticky="w", pady=10)
    sand_entry = tk.Entry(form, width=20, font=("Arial", 11), bd=1, relief="solid", bg="white")
    sand_entry.grid(row=3, column=1, sticky="ew", padx=15, pady=10)

    # Pay Rate
    tk.Label(form, text="Worker Salary / 75 Blocks  (₱)", bg="#fef3c7", font=("Arial", 11, "bold"), fg="#1e293b").grid(row=4, column=0, sticky="w", pady=10)
    pay_rate_var = tk.DoubleVar(value=pay_rate_default)
    pay_rate_entry = tk.Entry(form, textvariable=pay_rate_var, width=20, font=("Arial", 11), bd=1, relief="solid", bg="white")
    pay_rate_entry.grid(row=4, column=1, sticky="ew", padx=15, pady=10)

    # Configure column weight for better alignment
    form.columnconfigure(1, weight=1)

    # Result Display
    result_label = tk.Label(
        form_card,
        text="Blocks: 0 | Pay: ₱0",
        font=("Arial", 14, "bold"),
        bg="#e0f2fe",
        fg="#0369a1",
        pady=12
    )
    result_label.pack(pady=15, fill="x", padx=5)

    # Buttons Frame
    btn_frame = tk.Frame(form_card, bg=CARD_BG)
    btn_frame.pack(pady=15, fill="x")

    # ================= AUTO CALC =================
    def auto_sand(event=None):
        try:
            cement = int(cement_entry.get() or 0)
            sand = cement * 15
            sand_entry.delete(0, tk.END)
            sand_entry.insert(0, str(sand))

            blocks = cement * 75
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
            blocks = cement * 75
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

        # Confirmation dialog
        if not messagebox.askyesno("Confirm Save", f"Save production record for {worker}?", parent=win):
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
        messagebox.showinfo("Success", "Record saved successfully!", parent=win)

    def update():
        if not selected_id.get():
            messagebox.showerror("Error", "Select a record", parent=win)
            return

        try:
            cement = int(cement_entry.get())
            sand = cement * 15
            blocks = cement * 75
            pay_rate = float(pay_rate_var.get())
            pay = cement * pay_rate
        except:
            messagebox.showerror("Error", "Invalid input", parent=win)
            return

        # Confirmation dialog
        if not messagebox.askyesno("Confirm Update", f"Update record for {worker_entry.get()}?", parent=win):
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
        messagebox.showinfo("Success", "Record updated successfully!", parent=win)

    def delete():
        if not selected_id.get():
            return

        # Confirmation dialog
        if not messagebox.askyesno("Confirm Delete", f"Delete record for {worker_entry.get()}?\n\nThis action cannot be undone.", parent=win):
            return

        cursor.execute("DELETE FROM chb_production WHERE id=?", (selected_id.get(),))
        conn.commit()
        sync_chb_inventory(conn, cursor)
        load_data()
        clear_form()
        messagebox.showinfo("Success", "Record deleted successfully!", parent=win)

    def update_total_blocks():
        cursor.execute("SELECT COALESCE(SUM(total_blocks),0) FROM chb_production")
        produced = cursor.fetchone()[0] or 0

        cursor.execute("SELECT COALESCE(SUM(qty),0) FROM sales WHERE item_name=?", (CHB_ITEM_NAME,))
        sold = cursor.fetchone()[0] or 0

        stock = max(produced - sold, 0)

        total_blocks_var.set(f"Total Hollow Blocks Available: {stock:,}")

    # ================= BUTTONS =================
    tk.Button(btn_frame, text="✓ Save", command=save, bg="#15803d", fg="white", font=("Arial", 12, "bold"), width=12, padx=8, pady=10, relief="flat", cursor="hand2").pack(side="left", padx=6, pady=8)
    tk.Button(btn_frame, text="🔁 Update", command=update, bg="#1e40af", fg="white", font=("Arial", 12, "bold"), width=12, padx=8, pady=10, relief="flat", cursor="hand2").pack(side="left", padx=6, pady=8)
    tk.Button(btn_frame, text="🗑 Delete", command=delete, bg="#dc2626", fg="white", font=("Arial", 12, "bold"), width=12, padx=8, pady=10, relief="flat", cursor="hand2").pack(side="left", padx=6, pady=8)
    tk.Button(btn_frame, text="✋ Clear", command=clear_form, bg="#64748b", fg="white", font=("Arial", 12, "bold"), width=12, padx=8, pady=10, relief="flat", cursor="hand2").pack(side="left", padx=6, pady=8)

    # ================= TABLE (LEFT SIDE - 60%) =================
    table_card = tk.Frame(main_container, bg=CARD_BG)
    table_card.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
    table_card.columnconfigure(0, weight=1)
    table_card.rowconfigure(0, weight=1)

    columns = ("id", "date", "worker", "cement", "Fine Sand", "blocks", "pay")
    
    # Configure Treeview with larger fonts
    style = ttk.Style()
    style.configure('Treeview', font=('Arial', 11), rowheight=28)
    style.configure('Treeview.Heading', font=('Arial', 12, 'bold'))
    
    # Configure alternating row colors
    style.configure('Treeview', background="white", fieldbackground="white")
    style.map('Treeview', background=[('selected', '#2563eb')])
    style.configure('oddrow.Treeview', background='#ffffff')
    style.configure('evenrow.Treeview', background='#e0f2fe')
    
    # Create frame for tree and scrollbars
    tree_frame = tk.Frame(table_card, bg=CARD_BG)
    tree_frame.grid(row=0, column=0, sticky="nsew")
    tree_frame.columnconfigure(0, weight=1)
    tree_frame.rowconfigure(0, weight=1)
    
    # Create vertical scrollbar
    vsb = ttk.Scrollbar(tree_frame, orient="vertical")
    vsb.grid(row=0, column=1, sticky="ns")
    
    # Create horizontal scrollbar
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
    hsb.grid(row=1, column=0, sticky="ew")
    
    # Create treeview with scrollbar commands
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style='Treeview', yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    
    # Configure scrollbars
    vsb.config(command=tree.yview)
    hsb.config(command=tree.xview)

    for col in columns:
        tree.heading(col, text=col.upper())
        tree.column(col, anchor="center", width=130, stretch=False)

    # Bind to configure event to update scrollbar after column resize
    def on_tree_configure(event=None):
        tree.update_idletasks()
    
    tree.bind('<Configure>', on_tree_configure)
    
    # Configure tags for alternating row colors
    tree.tag_configure('oddrow', background='#ffffff', foreground='#000000')
    tree.tag_configure('evenrow', background='#93c5fd', foreground='#000000')

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

    # ================= DELIVERY BUTTON =================
    delivery_btn = tk.Button(
        win,
        text="🚚 Open Delivery Form",
        command=lambda: open_delivery_window(win, BG_MAIN, CARD_BG, PRIMARY),
        bg="#f59e0b",
        fg="white",
        font=("Arial", 12, "bold"),
        padx=15,
        pady=8,
        relief="flat",
        cursor="hand2"
    )
    delivery_btn.pack(pady=10)

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

        row_index = 0
        for row in cursor.fetchall():
            tag = 'evenrow' if row_index % 2 == 0 else 'oddrow'
            tree.insert("", "end", values=row, tags=(tag,))
            row_index += 1

    # ✅ BINDINGS (LIVE SEARCH)
    search_entry.bind("<KeyRelease>", load_data)
    sort_menu.bind("<<ComboboxSelected>>", load_data)

    # ✅ INITIAL LOAD
    load_data()
    update_total_blocks()
