import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime
import os
import sys

from pos_module.database import DB_NAME
from window_utils import enable_centered_toplevels

enable_centered_toplevels()

pos_refresh_callback = None
CHB_ITEM_NAME = "CHB Blocks"
CHB_STATE_ID = 1

# ==================== HELPER FUNCTIONS ====================
def center_window(window):
    """Center a window on the screen"""
    window.update_idletasks()
    width = window.winfo_width()
    height = window.winfo_height()
    x = (window.winfo_screenwidth() // 2) - (width // 2)
    y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"+{x}+{y}")


def notify_inventory_views():
    """Refresh open inventory windows when stock changes."""
    module = sys.modules.get("inventory_module") or sys.modules.get("inventory")
    callback = getattr(module, "inventory_refresh_callback", None) if module else None
    if callable(callback):
        try:
            callback()
        except Exception:
            pass

# ==================== POS WINDOW ====================
def open_pos():
    global pos_refresh_callback
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        raw_price REAL DEFAULT 0,
        unit TEXT DEFAULT '',
        status TEXT DEFAULT 'Active'
    )
    """)
    # Sales ledger for dashboard stats
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
    cursor.execute("PRAGMA table_info(items)")
    item_cols = [col[1] for col in cursor.fetchall()]
    if "unit" not in item_cols:
        cursor.execute("ALTER TABLE items ADD COLUMN unit TEXT DEFAULT ''")
    if "status" not in item_cols:
        cursor.execute("ALTER TABLE items ADD COLUMN status TEXT DEFAULT 'Active'")
        cursor.execute("UPDATE items SET status='Active' WHERE status IS NULL OR status=''")

    cursor.execute("SELECT id FROM chb_inventory_state WHERE id=?", (CHB_STATE_ID,))
    if not cursor.fetchone():
        cursor.execute("SELECT COALESCE(SUM(total_blocks),0) FROM chb_production")
        produced = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(SUM(qty),0) FROM sales WHERE item_name=?", (CHB_ITEM_NAME,))
        sold = cursor.fetchone()[0] or 0
        cursor.execute("SELECT COALESCE(quantity,0) FROM items WHERE name=? ORDER BY id ASC LIMIT 1", (CHB_ITEM_NAME,))
        row = cursor.fetchone()
        available = row[0] if row else max(produced - sold, 0)
        cursor.execute(
            "INSERT INTO chb_inventory_state (id, total_produced, total_sold, available, updated_ts) VALUES (?, ?, ?, ?, ?)",
            (CHB_STATE_ID, produced, sold, available, datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
        )
    conn.commit()

    cart = []
    inventory_names = []
    pos_style = ttk.Style()
    pos_style.configure(
        "Pos.Treeview",
        font=("Arial", 12),
        rowheight=28,
        background="white",
        fieldbackground="white",
    )
    pos_style.configure(
        "Pos.Treeview.Heading",
        font=("Arial", 12, "bold"),
    )

    # ---------- Inventory ----------
    def refresh_inventory_names():
        nonlocal inventory_names
        cursor.execute("SELECT name FROM items WHERE COALESCE(status, 'Active') = 'Active'")
        inventory_names = [row[0] for row in cursor.fetchall()]

    def load_inventory(search_query=""):
        for row in inv_tree.get_children():
            inv_tree.delete(row)

        query = "SELECT id, name, unit, quantity, price FROM items WHERE COALESCE(status, 'Active') = 'Active'"
        params = []

        # 🔍 KEEP YOUR SEARCH (unchanged logic)
        if search_query:
            query += " AND name LIKE ?"
            params.append('%' + search_query + '%')

        # 🔽 ADD SORTING (NEW PART)
        if sort_var.get() == "Name":
            query += " ORDER BY LOWER(name) ASC"
        else:
            query += " ORDER BY id DESC"

        cursor.execute(query, params)

        rows = cursor.fetchall()
        for row in rows:
            inv_tree.insert("", tk.END, values=row)

        refresh_inventory_names()

    # ---------- Cart Functions ----------
    def add_item_to_cart(product_id, name, quantity, price, qty):
        nonlocal cart
        cursor.execute("SELECT raw_price, COALESCE(status, 'Active') FROM items WHERE id=?", (product_id,))
        rp = cursor.fetchone()
        if not rp or rp[1] != "Active":
            messagebox.showerror("Error", "This item is inactive and cannot be sold.", parent=root)
            load_inventory(search_entry.get())
            return False
        raw_price = float(rp[0]) if rp[0] is not None else price

        existing_qty = 0
        existing_item = None
        for item in cart:
            if item['id'] == product_id:
                existing_qty = item['qty']
                existing_item = item
                break

        if qty <= 0:
            messagebox.showerror("Error", "Enter a valid quantity", parent=root)
            return False
        if existing_qty + qty > quantity:
            messagebox.showerror("Error", "Stocks aren't enough", parent=root)
            return False

        if existing_item:
            existing_item['qty'] += qty
            existing_item['total'] = existing_item['qty'] * existing_item['price']
        else:
            cart.append({
                'id': product_id,
                'name': name,
                'qty': qty,
                'price': price,
                'raw_price': raw_price,
                'total': qty * price
            })

        update_cart()
        return True

    def update_cart():
        nonlocal cart
        cart_tree.delete(*cart_tree.get_children())
        total = 0
        for item in cart:
            cart_tree.insert("", tk.END, values=(item['id'], item['name'], item['qty'], f"{item['total']:.2f}"))
            total += item['total']
        total_label.config(text=f"Total: {total:.2f}")

    def clear_cart():
        nonlocal cart
        if not cart:
            messagebox.showinfo("Cart", "Cart is already empty", parent=root)
            return
        if not messagebox.askyesno("Clear Cart", "Clear all items from the cart?", parent=root):
            return
        cart.clear()
        update_cart()

    def open_add_to_cart_modal(_event=None):
        selected = inv_tree.focus()
        if not selected:
            return

        values = inv_tree.item(selected, "values")
        product_id = int(values[0])
        name = values[1]
        unit = values[2] or "pcs"
        quantity = int(values[3])
        price = float(values[4])

        modal = tk.Toplevel(root)
        modal.title("Add to Cart")
        modal.configure(bg="white")
        modal.resizable(False, False)
        modal.transient(root)
        modal.grab_set()

        tk.Label(modal, text=name, font=("Arial", 16, "bold"), bg="white").pack(padx=16, pady=(14, 6))
        tk.Label(modal, text=f"Available stock: {quantity} {unit}", font=("Arial", 13), bg="white").pack(padx=16, pady=(0, 10))

        form = tk.Frame(modal, bg="white")
        form.pack(padx=16, pady=4, fill="x")
        tk.Label(form, text="Quantity", bg="white", font=("Arial", 14)).grid(row=0, column=0, padx=(0, 8), pady=4)
        qty_entry = tk.Entry(form, width=12, font=("Arial", 14))
        qty_entry.grid(row=0, column=1, pady=4)
        qty_entry.focus_set()

        def submit():
            qty_text = qty_entry.get().strip()
            if not qty_text.isdigit():
                messagebox.showerror("Error", "Enter a valid quantity", parent=modal)
                return
            if add_item_to_cart(product_id, name, quantity, price, int(qty_text)):
                modal.destroy()

        btns = tk.Frame(modal, bg="white")
        btns.pack(pady=(10, 14))
        tk.Button(btns, text="Add to Cart", bg="#16a34a", fg="white", font=("Arial", 14, "bold"),
                  command=submit, padx=10, pady=8).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", bg="#6b7280", fg="white", font=("Arial", 14, "bold"),
                  command=modal.destroy, padx=10, pady=8).pack(side="left", padx=6)

        qty_entry.bind("<Return>", lambda _e: submit())
        center_window(modal)

    def open_cart_item_modal(_event=None):
        nonlocal cart
        selected = cart_tree.focus()
        if not selected:
            return

        values = cart_tree.item(selected, "values")
        item_id = int(values[0])
        cart_item = next((item for item in cart if item['id'] == item_id), None)
        if not cart_item:
            return

        cursor.execute("SELECT quantity FROM items WHERE id=?", (item_id,))
        row = cursor.fetchone()
        available_stock = int(row[0]) if row else 0
        cursor.execute("SELECT unit FROM items WHERE id=?", (item_id,))
        unit_row = cursor.fetchone()
        unit = unit_row[0] if unit_row and unit_row[0] else "pcs"

        modal = tk.Toplevel(root)
        modal.title("Edit Cart Item")
        modal.configure(bg="white")
        modal.resizable(False, False)
        modal.transient(root)
        modal.grab_set()

        tk.Label(modal, text=cart_item['name'], font=("Arial", 16, "bold"), bg="white").pack(padx=16, pady=(14, 6))
        tk.Label(modal, text=f"Available stock: {available_stock} {unit}", font=("Arial", 13), bg="white").pack(padx=16, pady=(0, 10))

        form = tk.Frame(modal, bg="white")
        form.pack(padx=16, pady=4, fill="x")
        tk.Label(form, text="Quantity", bg="white", font=("Arial", 14)).grid(row=0, column=0, padx=(0, 8), pady=4)
        qty_entry = tk.Entry(form, width=12, font=("Arial", 14))
        qty_entry.grid(row=0, column=1, pady=4)
        qty_entry.insert(0, str(cart_item['qty']))
        qty_entry.focus_set()
        qty_entry.select_range(0, tk.END)

        def save_changes():
            qty_text = qty_entry.get().strip()
            if not qty_text.isdigit():
                messagebox.showerror("Error", "Enter a valid quantity", parent=modal)
                return
            new_qty = int(qty_text)
            if new_qty <= 0:
                messagebox.showerror("Error", "Enter a valid quantity", parent=modal)
                return
            if new_qty > available_stock:
                messagebox.showerror("Error", "Stocks aren't enough", parent=modal)
                return
            cart_item['qty'] = new_qty
            cart_item['total'] = new_qty * cart_item['price']
            update_cart()
            modal.destroy()

        def remove_item():
            if not messagebox.askyesno("Remove Item", f"Remove {cart_item['name']} from the cart?", parent=modal):
                return
            cart.remove(cart_item)
            update_cart()
            modal.destroy()

        btns = tk.Frame(modal, bg="white")
        btns.pack(pady=(10, 14))
        tk.Button(btns, text="Save", bg="#16a34a", fg="white", font=("Arial", 14, "bold"),
                  command=save_changes, padx=10, pady=8).pack(side="left", padx=6)
        tk.Button(btns, text="Remove", bg="#dc3545", fg="white", font=("Arial", 14, "bold"),
                  command=remove_item, padx=10, pady=8).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", bg="#6b7280", fg="white", font=("Arial", 14, "bold"),
                  command=modal.destroy, padx=10, pady=8).pack(side="left", padx=6)

        qty_entry.bind("<Return>", lambda _e: save_changes())
        center_window(modal)

    def generate_invoice_pdf(cart_items, total_amount, money_received, change, mode, platform, txn_id):
        try:
            from fpdf import FPDF
        except ImportError:
            messagebox.showwarning(
                "PDF Library Missing",
                "Receipt PDF was skipped because 'fpdf' is not installed.\n"
                "Install it with: pip install fpdf"
            )
            return None

        documents_path = os.path.expanduser("~/Documents")
        pdf_path = os.path.join(documents_path, f"receipt_{txn_id}.pdf")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", "B", 14)
        pdf.cell(0, 8, "JASP Hardware", ln=True)
        pdf.set_font("Arial", "", 11)
        pdf.cell(0, 6, "123 Business St, City", ln=True)
        pdf.cell(0, 6, "email@example.com | +63-900-000-0000", ln=True)
        pdf.ln(4)
        pdf.cell(0, 6, f"Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
        pdf.cell(0, 6, f"Transaction ID: {txn_id}", ln=True)
        pdf.ln(6)
        pdf.set_font("Arial", "B", 11)
        pdf.cell(60, 8, "Item", 1)
        pdf.cell(30, 8, "Qty", 1, align="C")
        pdf.cell(40, 8, "Price", 1, align="R")
        pdf.cell(40, 8, "Total", 1, ln=True, align="R")
        pdf.set_font("Arial", "", 11)
        for item in cart_items:
            pdf.cell(60, 8, item['name'], 1)
            pdf.cell(30, 8, f"x{item['qty']}", 1, align="C")
            pdf.cell(40, 8, f"{item['price']:.2f}", 1, align="R")
            pdf.cell(40, 8, f"{item['total']:.2f}", 1, ln=True, align="R")
        pdf.ln(4)
        pdf.cell(0, 8, f"Total Amount: {total_amount:.2f}", ln=True)
        pdf.cell(0, 8, f"Money Received: {money_received:.2f}", ln=True)
        pdf.cell(0, 8, f"Mode of Payment: {mode}" + (f" ({platform})" if platform else ""), ln=True)
        if mode == "Cash":
            pdf.cell(0, 8, f"Change: {change:.2f}", ln=True)
        pdf.output(pdf_path)
        return pdf_path

    def open_invoice_window(cart_items, total_amount, money_received, change, mode, platform, txn_id):
        """Display invoice in a new floating window"""
        inv_window = tk.Toplevel(root)
        inv_window.title("Invoice")
        inv_window.configure(bg="white")
        inv_window.resizable(True, True)
        inv_window.minsize(500, 600)
        inv_window.transient(root)

        # Header
        header_frame = tk.Frame(inv_window, bg="#2c3e50")
        header_frame.pack(fill="x")
        tk.Label(header_frame, text="JASP Hardware", font=("Arial", 19, "bold"), bg="#2c3e50", fg="white").pack(pady=(10, 4))
        tk.Label(header_frame, text="123 Business St, City", font=("Arial", 13), bg="#2c3e50", fg="white").pack()
        tk.Label(header_frame, text="email@example.com | +63-900-000-0000", font=("Arial", 12), bg="#2c3e50", fg="white").pack(pady=(0, 10))

        # Content
        content_frame = tk.Frame(inv_window, bg="white")
        content_frame.pack(fill="both", expand=True, padx=15, pady=15)

        tk.Label(content_frame, text=f"Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", font=("Arial", 13), bg="white").pack(anchor="w", pady=(0, 4))
        tk.Label(content_frame, text=f"Transaction ID: {txn_id}", font=("Arial", 13), bg="white").pack(anchor="w", pady=(0, 10))

        # Items table
        tk.Label(content_frame, text="Items", font=("Arial", 14, "bold"), bg="white").pack(anchor="w", pady=(10, 5))
        
        table_frame = tk.Frame(content_frame, bg="white")
        table_frame.pack(fill="x", pady=(0, 10))
        
        # Headers
        header_subframe = tk.Frame(table_frame, bg="#ecf0f1")
        header_subframe.pack(fill="x")
        tk.Label(header_subframe, text="Item", font=("Arial", 13, "bold"), bg="#ecf0f1", width=30, anchor="w").pack(side="left", padx=5, pady=4)
        tk.Label(header_subframe, text="Qty", font=("Arial", 13, "bold"), bg="#ecf0f1", width=8, anchor="center").pack(side="left", padx=5, pady=4)
        tk.Label(header_subframe, text="Price", font=("Arial", 13, "bold"), bg="#ecf0f1", width=12, anchor="e").pack(side="left", padx=5, pady=4)
        tk.Label(header_subframe, text="Total", font=("Arial", 13, "bold"), bg="#ecf0f1", width=12, anchor="e").pack(side="left", padx=5, pady=4)

        # Items
        for item in cart_items:
            item_subframe = tk.Frame(table_frame, bg="white")
            item_subframe.pack(fill="x")
            tk.Label(item_subframe, text=item['name'], font=("Arial", 13), bg="white", width=30, anchor="w").pack(side="left", padx=5, pady=3)
            tk.Label(item_subframe, text=f"x{item['qty']}", font=("Arial", 13), bg="white", width=8, anchor="center").pack(side="left", padx=5, pady=3)
            tk.Label(item_subframe, text=f"{item['price']:.2f}", font=("Arial", 13), bg="white", width=12, anchor="e").pack(side="left", padx=5, pady=3)
            tk.Label(item_subframe, text=f"{item['total']:.2f}", font=("Arial", 13), bg="white", width=12, anchor="e").pack(side="left", padx=5, pady=3)

        # Totals
        sep_frame = tk.Frame(content_frame, bg="#d1d5db", height=1)
        sep_frame.pack(fill="x", pady=10)

        tk.Label(content_frame, text=f"Total Amount: {total_amount:.2f}", font=("Arial", 14, "bold"), bg="white").pack(anchor="w", pady=2)
        tk.Label(content_frame, text=f"Money Received: {money_received:.2f}", font=("Arial", 14), bg="white").pack(anchor="w", pady=2)
        tk.Label(content_frame, text=f"Mode of Payment: {mode}" + (f" ({platform})" if platform else ""), font=("Arial", 14), bg="white").pack(anchor="w", pady=2)
        if mode == "Cash":
            tk.Label(content_frame, text=f"Change: {change:.2f}", font=("Arial", 14), bg="white").pack(anchor="w", pady=2)

        # Buttons
        btn_frame = tk.Frame(inv_window, bg="white")
        btn_frame.pack(pady=15)
        tk.Button(btn_frame, text="Printing...", bg="#6b7280", fg="white", font=("Arial", 14, "bold"), width=18, padx=12, pady=10).pack(side="left", padx=6)
        tk.Button(btn_frame, text="Close", bg="#ef4444", fg="white", font=("Arial", 14, "bold"), width=18, padx=12, pady=10, command=inv_window.destroy).pack(side="left", padx=6)

        center_window(inv_window)

    def finalize_transaction(mode, money_received, platform):
        nonlocal cart
        if not cart:
            messagebox.showerror("Error", "Cart is empty", parent=root)
            return False
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        txn_id = datetime.now().strftime("%Y%m%d%H%M%S")
        total_amount = sum(item['total'] for item in cart)
        change = money_received - total_amount if mode == "Cash" else 0

        for item in cart:
            cursor.execute("UPDATE items SET quantity = quantity - ? WHERE id=?", (item['qty'], item['id']))
            cursor.execute(
                "INSERT INTO sales (item_name, qty, price, raw_price, total, ts) VALUES (?, ?, ?, ?, ?, ?)",
                (item['name'], item['qty'], item['price'], item.get('raw_price', 0), item['total'], now)
            )
            if item['name'] == CHB_ITEM_NAME:
                cursor.execute(
                    """
                    UPDATE chb_inventory_state
                    SET total_sold = total_sold + ?,
                        available = MAX(available - ?, 0),
                        updated_ts = ?
                    WHERE id = ?
                    """,
                    (item['qty'], item['qty'], now, CHB_STATE_ID)
                )
        conn.commit()
        notify_inventory_views()

        pdf_path = generate_invoice_pdf(cart, total_amount, money_received, change, mode, platform, txn_id)
        cart_items_copy = [item.copy() for item in cart]
        cart.clear()
        update_cart()
        load_inventory()
        open_invoice_window(cart_items_copy, total_amount, money_received, change, mode, platform, txn_id)
        return True

    def open_payment_modal():
        nonlocal cart
        if not cart:
            messagebox.showerror("Error", "Cart is empty", parent=root)
            return
        total_amount = sum(item['total'] for item in cart)

        def on_mode_change(*_):
            if pay_mode.get() == "Cash":
                qr_frame.pack_forget()
                money_entry.config(state="normal")
                update_change()
            else:
                qr_frame.pack(fill="x", pady=6)
                money_entry.delete(0, tk.END)
                money_entry.insert(0, "0")
                money_entry.config(state="disabled")
                change_var.set("Change: N/A (online)")

        def update_change(*_):
            if pay_mode.get() != "Cash":
                return
            val = money_entry.get().strip()
            try:
                received = float(val)
            except ValueError:
                change_var.set("Change: —")
                return
            change = received - total_amount
            change_var.set(f"Change: {change:.2f}")

        def on_pay():
            mode = pay_mode.get()
            platform = platform_entry.get().strip() if mode == "Online" else ""
            if mode == "Cash":
                try:
                    received = float(money_entry.get())
                except ValueError:
                    messagebox.showerror("Error", "Enter a valid amount for money received.", parent=pay_modal)
                    return
                if received < total_amount:
                    messagebox.showerror("Error", "Money received is less than total.", parent=pay_modal)
                    return
            else:
                received = total_amount
            success = finalize_transaction(mode, received, platform)
            if success:
                pay_modal.destroy()

        pay_modal = tk.Toplevel(root)
        pay_modal.title("Complete Payment")
        pay_modal.grab_set()
        pay_modal.configure(bg="white")
        pay_modal.resizable(False, False)

        tk.Label(pay_modal, text=f"Total Amount: {total_amount:.2f}", font=("Arial", 17, "bold"), bg="white").pack(pady=(12, 6))

        pay_mode = tk.StringVar(value="Cash")
        mode_frame = tk.Frame(pay_modal, bg="white")
        mode_frame.pack(fill="x", padx=12, pady=6)
        tk.Radiobutton(mode_frame, text="Cash", variable=pay_mode, value="Cash", bg="white", command=on_mode_change, font=("Arial", 13)).pack(side="left", padx=6)
        tk.Radiobutton(mode_frame, text="Online Payment", variable=pay_mode, value="Online", bg="white", command=on_mode_change, font=("Arial", 13)).pack(side="left", padx=6)

        money_frame = tk.Frame(pay_modal, bg="white")
        money_frame.pack(fill="x", padx=12, pady=6)
        tk.Label(money_frame, text="Money Received:", bg="white", font=("Arial", 14)).pack(anchor="w")
        money_entry = tk.Entry(money_frame, font=("Arial", 15))
        money_entry.pack(fill="x", pady=4)
        money_entry.insert(0, f"{total_amount:.2f}")
        money_entry.bind("<KeyRelease>", update_change)

        change_var = tk.StringVar(value="Change: 0.00")
        tk.Label(pay_modal, textvariable=change_var, bg="white", font=("Arial", 14, "bold")).pack(anchor="w", padx=12)

        qr_frame = tk.Frame(pay_modal, bg="white", highlightthickness=1, highlightbackground="#d1d5db")
        tk.Label(qr_frame, text="QR / Online Payment Placeholder", bg="white", fg="#6b7280").pack(padx=20, pady=20)

        platform_frame = tk.Frame(pay_modal, bg="white")
        platform_frame.pack(fill="x", padx=12, pady=6)
        tk.Label(platform_frame, text="Platform (e.g., GCash/Bank):", bg="white", font=("Arial", 13)).pack(anchor="w")
        platform_entry = tk.Entry(platform_frame, font=("Arial", 14))
        platform_entry.pack(fill="x", pady=4)

        btns = tk.Frame(pay_modal, bg="white")
        btns.pack(pady=12)
        tk.Button(btns, text="Checkout", bg="#16a34a", fg="white", font=("Arial", 14, "bold"),
                  command=on_pay, padx=15, pady=10).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", bg="#ef4444", fg="white", font=("Arial", 14, "bold"),
                  command=pay_modal.destroy, padx=15, pady=10).pack(side="left", padx=6)

        on_mode_change()
        center_window(pay_modal)

    def back_to_main():
        global pos_refresh_callback
        pos_refresh_callback = None
        root.destroy()

    def on_close():
        global pos_refresh_callback
        pos_refresh_callback = None
        root.destroy()

    # ---------- GUI ----------
    root = tk.Toplevel()
    root.title("POS System")
    root.state("zoomed")  # Fullscreen
    root.configure(bg="#f4f6f9")

    root.transient()        # link to main window
    root.grab_set()         # lock focus to POS
    root.protocol("WM_DELETE_WINDOW", on_close)

    # ====== Top Frame (Search + Back) ======
    top_frame = tk.Frame(root, bg="#f4f6f9", pady=10)
    top_frame.pack(fill="x")

    tk.Label(top_frame, text="Search Inventory:", bg="#f4f6f9", font=("Arial", 13)).pack(side=tk.LEFT, padx=10)
    search_entry = ttk.Combobox(top_frame, width=30, font=("Arial", 14))
    search_entry.pack(side=tk.LEFT, padx=10)
    def update_suggestions(event=None):
        text = search_entry.get()
        filtered = [n for n in inventory_names if text.lower() in n.lower()]
        search_entry["values"] = filtered
    search_entry.bind("<KeyRelease>", lambda e: (update_suggestions(), load_inventory(search_entry.get())))
    tk.Button(top_frame, text="Search", bg="#17a2b8", fg="white", font=("Arial", 13, "bold"),
              command=lambda: load_inventory(search_entry.get()), padx=12, pady=8).pack(side=tk.LEFT, padx=10)
    tk.Button(top_frame, text="Back", bg="#dc3545", fg="white", font=("Arial", 13, "bold"),
              command=back_to_main, padx=12, pady=8).pack(side=tk.RIGHT, padx=20)
    
    tk.Label(top_frame, text="Sort By:", bg="#f4f6f9", font=("Arial", 13)).pack(side=tk.LEFT, padx=5)

    sort_var = tk.StringVar(value="Name")

    sort_menu = ttk.Combobox(
        top_frame,
        textvariable=sort_var,
        values=["Name", "Newest"],
        state="readonly",
        width=12
    )
    sort_menu.pack(side=tk.LEFT, padx=5)

    # reload when changed
    sort_menu.bind("<<ComboboxSelected>>", lambda e: load_inventory(search_entry.get()))
    pos_refresh_callback = lambda: load_inventory(search_entry.get())

    # ====== Main Frame ======
    main_frame = tk.Frame(root, bg="#f4f6f9")
    main_frame.pack(fill="both", expand=True, padx=10, pady=5)

    # Left Frame - Inventory
    left_frame = tk.Frame(main_frame, bg="white", padx=10, pady=10)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0,5))
    tk.Label(left_frame, text="Inventory", font=("Arial", 17, "bold"), bg="white").pack(pady=5)

    global inv_tree
    inv_tree = ttk.Treeview(left_frame, columns=("ID","Name","Unit","Quantity","Price"), show="headings", style="Pos.Treeview")
    inv_tree.pack(fill=tk.BOTH, expand=True)
    for col in ("ID","Name","Unit","Quantity","Price"):
        inv_tree.heading(col, text=col)
        inv_tree.column(col, width=120, anchor="center")

    # Add to Cart button for inventory
    btn_frame_left = tk.Frame(left_frame, bg="white")
    btn_frame_left.pack(pady=10)
    tk.Button(btn_frame_left, text="Add to Cart", bg="#16a34a", fg="white", font=("Arial", 14, "bold"),
              command=open_add_to_cart_modal, padx=15, pady=10).pack()

    # Right Frame - Cart / POS
    right_frame = tk.Frame(main_frame, bg="#f4f6f9", padx=10, pady=10)
    right_frame.pack(side="right", fill="both", expand=True, padx=(5,0))

    tk.Label(right_frame, text="Cart / POS", font=("Arial", 17, "bold"), bg="#f4f6f9").pack(pady=5)

    cart_frame = tk.Frame(right_frame, bg="#f4f6f9")
    cart_frame.pack(pady=5)
    tk.Label(cart_frame, text="Double-click an inventory item to add it to cart.", font=("Arial", 13),
             bg="#f4f6f9").pack()
        # Cart Treeview
    global cart_tree
    cart_tree = ttk.Treeview(right_frame, columns=("ID","Name","Qty","Total"), show="headings", style="Pos.Treeview")
    cart_tree.pack(fill="both", expand=True, pady=5)
    for col, w in (("ID",80), ("Name",180), ("Qty",80), ("Total",120)):
            cart_tree.heading(col, text=col)
            cart_tree.column(col, width=w, anchor="center")

    global total_label
    total_label = tk.Label(right_frame, text="Total: 0.00", font=("Arial", 17, "bold"), bg="#f4f6f9")
    total_label.pack(pady=5)

    # Checkout buttons
    btn_frame_right = tk.Frame(right_frame, bg="#f4f6f9")
    btn_frame_right.pack(pady=10)
    tk.Button(btn_frame_right, text="Pay / Checkout", bg="#ffc107", fg="black", width=25, font=("Arial", 14, "bold"),
              command=open_payment_modal, padx=15, pady=10).grid(row=0,column=0,padx=5)
    tk.Button(btn_frame_right, text="Clear Cart", bg="#dc3545", fg="white", width=25, font=("Arial", 14, "bold"),
              command=clear_cart, padx=15, pady=10).grid(row=0,column=1,padx=5)

    inv_tree.bind("<Double-1>", open_add_to_cart_modal)
    cart_tree.bind("<Double-1>", open_cart_item_modal)

    load_inventory()
    root.mainloop()
