import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import os


DB_NAME = os.path.join(os.path.dirname(__file__), "jasp.db")
CHB_ITEM_NAME = "CHB Blocks"
CHB_STATE_ID = 1

# Predefined items with their measurement units
CHB_DEFAULT_UNIT = "pieces"
PREDEFINED_ITEMS = {
    "Nails": "kilograms",
    "CHB Blocks": CHB_DEFAULT_UNIT,
    "Cement": "bag/sack"
}

UNIT_OPTIONS = [
    CHB_DEFAULT_UNIT,
    "kilograms",
    "bag/sack",
    "pieces",
    "meters",
    "liters",
    "boxes",
    "sets",
    "rolls",]

# Prevent multiple inventory windows
inventory_window = None
inventory_refresh_callback = None
inventory_refresh_job = None

def open_inventory():
    global inventory_window, inventory_refresh_callback, inventory_refresh_job
    if inventory_window and inventory_window.winfo_exists():
        inventory_window.focus()
        return

    # ---------- DB Setup ----------
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Add raw_price and unit columns if not exists
    cursor.execute("PRAGMA table_info(items)")
    columns = [col[1] for col in cursor.fetchall()]
    if "raw_price" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN raw_price REAL DEFAULT 0")
        conn.commit()
    if "unit" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN unit TEXT DEFAULT ''")
        conn.commit()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        raw_price REAL DEFAULT 0,
        unit TEXT DEFAULT ''
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
    conn.commit()

    def ensure_chb_item():
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
                "INSERT INTO items (name, quantity, price, raw_price, unit) VALUES (?, ?, ?, ?, ?)",
                (CHB_ITEM_NAME, stock, 0, 0, CHB_DEFAULT_UNIT)
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

    ensure_chb_item()

    def normalize_predefined_units():
        for item_name, item_unit in PREDEFINED_ITEMS.items():
            cursor.execute(
                "UPDATE items SET unit=? WHERE name=? AND COALESCE(unit, '') = ''",
                (item_unit, item_name)
            )
        conn.commit()

    normalize_predefined_units()

    # ---------- GUI ----------
    inventory_window = tk.Toplevel()
    inventory_window.title("Inventory Management")
    inventory_window.state("zoomed")
    inventory_window.configure(bg="#f4f6f9")

    tk.Label(inventory_window, text="Inventory Management", font=("Arial", 20, "bold"), bg="#f4f6f9").pack(pady=15)

    main_frame = tk.Frame(inventory_window, bg="#f4f6f9")
    main_frame.pack(fill="both", expand=True, padx=20, pady=10)

    # -------- Left Frame: Actions ----------
    left_frame = tk.Frame(main_frame, bg="white", padx=20, pady=20, bd=2, relief="groove")
    left_frame.pack(side="left", fill="y", padx=(0,10), pady=5)

    # ---------- CRUD Functions ----------
    sort_state = {"column": None, "ascending": True}

    def view_items(filter_text=""):
        ensure_chb_item()
        for row in tree.get_children():
            tree.delete(row)
        if filter_text:
            cursor.execute(
                "SELECT id, name, unit, quantity, price, raw_price FROM items WHERE name LIKE ?",
                (f"%{filter_text}%",)
            )
        else:
            cursor.execute("SELECT id, name, unit, quantity, price, raw_price FROM items")
        rows = cursor.fetchall()
        for row in rows:
            tree.insert("", tk.END, values=row)

    def refresh_current_view():
        view_items(search_entry.get())

    def sort_tree(column, numeric=False):
        # Grab current rows
        data = [(tree.set(k, column), k) for k in tree.get_children("")]
        # Coerce numerics when needed
        if numeric:
            def to_num(val):
                try:
                    return float(val)
                except ValueError:
                    return 0
            data = [(to_num(val), k) for val, k in data]
        ascending = not (sort_state["column"] == column and sort_state["ascending"])
        data.sort(reverse=not ascending)
        for index, (_, k) in enumerate(data):
            tree.move(k, "", index)
        sort_state["column"] = column
        sort_state["ascending"] = ascending

    def log_restock(name, qty_added, price, raw_price):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        total_cost = raw_price * qty_added
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
        cursor.execute(
            "INSERT INTO restocks (item_name, qty, price, raw_price, total_cost, ts) VALUES (?, ?, ?, ?, ?, ?)",
            (name, qty_added, price, raw_price, total_cost, ts)
        )
        conn.commit()

    def open_item_form(mode, item_values=None):
        form = tk.Toplevel(inventory_window)
        form.title("Add Item" if mode == "add" else "Edit Item")
        form.transient(inventory_window)
        form.grab_set()
        form.configure(bg="white")

        tk.Label(form, text="Item Name", font=("Arial", 11, "bold"), bg="white").grid(row=0, column=0, padx=10, pady=5, sticky="w")
        name_var = tk.StringVar()
        name_entry = tk.Entry(form, textvariable=name_var, width=25, font=("Arial", 11))
        name_entry.grid(row=0, column=1, pady=5)

        tk.Label(form, text="Measurement Unit", font=("Arial", 11, "bold"), bg="white").grid(row=1, column=0, padx=10, pady=5, sticky="w")
        unit_var = tk.StringVar()
        unit_entry = ttk.Combobox(form, textvariable=unit_var, values=UNIT_OPTIONS, width=23, font=("Arial", 11), state="readonly")
        unit_entry.grid(row=1, column=1, pady=5)

        tk.Label(form, text="Quantity", font=("Arial", 11, "bold"), bg="white").grid(row=2, column=0, padx=10, pady=5, sticky="w")
        quantity_entry = tk.Entry(form, width=25, font=("Arial", 11))
        quantity_entry.grid(row=2, column=1, pady=5)

        tk.Label(form, text="Selling Price", font=("Arial", 11, "bold"), bg="white").grid(row=3, column=0, padx=10, pady=5, sticky="w")
        price_entry = tk.Entry(form, width=25, font=("Arial", 11))
        price_entry.grid(row=3, column=1, pady=5)

        tk.Label(form, text="Raw Price", font=("Arial", 11, "bold"), bg="white").grid(row=4, column=0, padx=10, pady=5, sticky="w")
        raw_price_entry = tk.Entry(form, width=25, font=("Arial", 11))
        raw_price_entry.grid(row=4, column=1, pady=5)

        def sync_unit_from_name(event=None):
            selected_item = name_var.get().strip()
            if selected_item in PREDEFINED_ITEMS:
                unit_var.set(PREDEFINED_ITEMS[selected_item])

        name_entry.bind("<KeyRelease>", sync_unit_from_name)
        name_entry.bind("<FocusOut>", sync_unit_from_name)

        if mode == "edit" and item_values:
            name_var.set(item_values[1])
            unit_var.set(item_values[2] if len(item_values) > 2 else "")
            quantity_entry.insert(0, item_values[3])
            price_entry.insert(0, item_values[4])
            raw_price_entry.insert(0, item_values[5])

            if not unit_var.get() and item_values[1] in PREDEFINED_ITEMS:
                unit_var.set(PREDEFINED_ITEMS[item_values[1]])

            if item_values[1] == CHB_ITEM_NAME:
                name_entry.config(state="disabled")
                quantity_entry.config(state="disabled")
                raw_price_entry.config(state="disabled")
                unit_entry.config(state="disabled")
                unit_var.set(CHB_DEFAULT_UNIT)
                tk.Label(form, text="Quantity is auto from CHB production. Only price can be updated.", fg="#dc2626", bg="white", font=("Arial", 9, "italic")).grid(row=6, column=0, columnspan=2, pady=(4, 0))

        def submit():
            name = name_var.get().strip()
            unit = unit_var.get().strip()
            quantity = quantity_entry.get().strip()
            price = price_entry.get().strip()
            raw = raw_price_entry.get().strip()

            if not name or not unit or not quantity or not price or not raw:
                messagebox.showerror("Error", "All fields are required!", parent=form)
                return

            if mode == "add" and name == CHB_ITEM_NAME:
                messagebox.showerror("Error", "CHB quantity is auto-generated. Edit price only via the existing CHB item.", parent=form)
                return

            try:
                quantity_val = int(quantity)
                price_val = float(price)
                raw_val = float(raw)
            except ValueError:
                messagebox.showerror("Error", "Quantity must be a whole number and prices must be numeric.", parent=form)
                return

            # Lock quantity/name for CHB on edit – only allow price change
            if mode == "edit" and item_values and item_values[1] == CHB_ITEM_NAME:
                name = CHB_ITEM_NAME
                quantity_val = int(item_values[3])
                raw_val = float(item_values[5])
                unit = CHB_DEFAULT_UNIT

            if name in PREDEFINED_ITEMS and not unit:
                unit = PREDEFINED_ITEMS[name]

            if mode == "add":
                # If an item with the same name and price exists, stack quantities instead of creating a duplicate
                cursor.execute("SELECT id, quantity FROM items WHERE name = ? AND price = ?", (name, price_val))
                existing = cursor.fetchone()

                if existing:
                    item_id, current_qty = existing
                    new_qty = int(current_qty) + quantity_val
                    cursor.execute("UPDATE items SET quantity = ?, raw_price = ?, unit = ? WHERE id = ?", (new_qty, raw_val, unit, item_id))
                    success_msg = "Item quantity updated successfully!"
                    log_restock(name, quantity_val, price_val, raw_val)
                else:
                    cursor.execute(
                        "INSERT INTO items (name, quantity, price, raw_price, unit) VALUES (?, ?, ?, ?, ?)",
                        (name, quantity_val, price_val, raw_val, unit),
                    )
                    success_msg = "Item added successfully!"
                    log_restock(name, quantity_val, price_val, raw_val)
            else:
                item_id = item_values[0]
                previous_qty = int(item_values[3])
                cursor.execute("UPDATE items SET name=?, quantity=?, price=?, raw_price=?, unit=? WHERE id=?",
                               (name, quantity_val, price_val, raw_val, unit, item_id))
                success_msg = "Item updated successfully!"
                if quantity_val > previous_qty:
                    log_restock(name, quantity_val - previous_qty, price_val, raw_val)

            conn.commit()
            messagebox.showinfo("Success", success_msg, parent=form)
            form.destroy()
            view_items()

        tk.Button(form, text="Save", width=15, bg="#28a745", fg="white", font=("Arial", 11, "bold"), command=submit).grid(row=5, column=0, pady=15)
        tk.Button(form, text="Cancel", width=15, bg="#6c757d", fg="white", font=("Arial", 11, "bold"), command=form.destroy).grid(row=5, column=1, pady=15)

    def add_item():
        open_item_form("add")

    def update_item():
        selected = tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select an item to update", parent=inventory_window)
            return
        values = tree.item(selected, "values")
        open_item_form("edit", values)

    def delete_item():
        selected = tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select an item to delete", parent=inventory_window)
            return
        values = tree.item(selected, "values")
        if values[1] == CHB_ITEM_NAME:
            messagebox.showerror("Error", "CHB item cannot be deleted. Its stock is managed separately.", parent=inventory_window)
            return
        item_id = values[0]
        cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
        conn.commit()
        messagebox.showinfo("Success", "Item Deleted Successfully!", parent=inventory_window)
        inventory_window.lift()
        inventory_window.focus_force()
        view_items()

    def search_items(event):
        # Live filter while typing (desktop equivalent of ajax search)
        view_items(search_entry.get())

    def back_to_main():
        global inventory_refresh_callback, inventory_refresh_job
        inventory_refresh_callback = None
        if inventory_refresh_job and inventory_window and inventory_window.winfo_exists():
            inventory_window.after_cancel(inventory_refresh_job)
        inventory_refresh_job = None
        inventory_window.destroy()

    def on_close():
        global inventory_refresh_callback, inventory_refresh_job
        inventory_refresh_callback = None
        if inventory_refresh_job and inventory_window and inventory_window.winfo_exists():
            inventory_window.after_cancel(inventory_refresh_job)
        inventory_refresh_job = None
        inventory_window.destroy()

    # ---------- Buttons ----------
    tk.Button(left_frame, text="Add Item", width=20, bg="#28a745", fg="white", font=("Arial", 11, "bold"), command=add_item).grid(row=0, column=0, pady=10, padx=5)
    tk.Button(left_frame, text="Edit Item", width=20, bg="#007bff", fg="white", font=("Arial", 11, "bold"), command=update_item).grid(row=1, column=0, pady=10, padx=5)
    tk.Button(left_frame, text="Delete Item", width=20, bg="#dc3545", fg="white", font=("Arial", 11, "bold"), command=delete_item).grid(row=2, column=0, pady=10, padx=5)
    tk.Button(left_frame, text="Back", width=20, bg="#ffc107", fg="black", font=("Arial", 11, "bold"), command=back_to_main).grid(row=3, column=0, pady=20, padx=5)

    # -------- Right Frame: Table + Search ----------
    right_frame = tk.Frame(main_frame, bg="#f4f6f9", padx=10, pady=10)
    right_frame.pack(side="right", fill="both", expand=True)

    tk.Label(right_frame, text="Search by Name:", font=("Arial", 11, "bold"), bg="#f4f6f9").pack(anchor="w")
    search_entry = tk.Entry(right_frame, font=("Arial", 11))
    search_entry.pack(fill="x", pady=5)
    search_entry.bind("<KeyRelease>", search_items)
    inventory_refresh_callback = refresh_current_view

    tree_frame = tk.Frame(right_frame)
    tree_frame.pack(fill="both", expand=True, pady=10)

    tree = ttk.Treeview(tree_frame, columns=("ID", "Name", "Unit", "Quantity", "Price", "Raw Price"), show="headings", selectmode="browse")
    v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    v_scroll.pack(side="right", fill="y")
    h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    h_scroll.pack(side="bottom", fill="x")
    tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
    tree.pack(fill="both", expand=True)

    tree.heading("ID", text="ID", command=lambda: sort_tree("ID", numeric=True))
    tree.column("ID", width=70, anchor="center")
    tree.heading("Name", text="Name", command=lambda: sort_tree("Name", numeric=False))
    tree.column("Name", width=200, anchor="w")
    tree.heading("Unit", text="Unit", command=lambda: sort_tree("Unit", numeric=False))
    tree.column("Unit", width=120, anchor="center")
    tree.heading("Quantity", text="Quantity", command=lambda: sort_tree("Quantity", numeric=True))
    tree.column("Quantity", width=100, anchor="center")
    tree.heading("Price", text="Selling Price", command=lambda: sort_tree("Price", numeric=True))
    tree.column("Price", width=100, anchor="center")
    tree.heading("Raw Price", text="Raw Price", command=lambda: sort_tree("Raw Price", numeric=True))
    tree.column("Raw Price", width=100, anchor="center")

    inventory_window.protocol("WM_DELETE_WINDOW", on_close)
    view_items()
