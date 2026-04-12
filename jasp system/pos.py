from logging import root
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
from fpdf import FPDF
from datetime import datetime
import os

DB_NAME = os.path.join(os.path.dirname(__file__), "jasp.db")

# ==================== POS WINDOW ====================
def open_pos():
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
    conn.commit()

    cart = []
    inventory_names = []

    # ---------- Inventory ----------
    def refresh_inventory_names():
        nonlocal inventory_names
        cursor.execute("SELECT name FROM items")
        inventory_names = [row[0] for row in cursor.fetchall()]

    def load_inventory(search_query=""):
        for row in inv_tree.get_children():
            inv_tree.delete(row)
        if search_query:
            cursor.execute("SELECT * FROM items WHERE name LIKE ?", ('%' + search_query + '%',))
        else:
            cursor.execute("SELECT * FROM items")
        rows = cursor.fetchall()
        for row in rows:
            inv_tree.insert("", tk.END, values=row)
        refresh_inventory_names()

    # ---------- Cart Functions ----------
    def add_to_cart():
        nonlocal cart
        selected = inv_tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select a product from inventory", parent=root)
            return
        values = inv_tree.item(selected, "values")
        product_id = int(values[0])
        name = values[1]
        quantity = int(values[2])
        price = float(values[3])
        # capture raw price if available
        cursor.execute("SELECT raw_price FROM items WHERE id=?", (product_id,))
        rp = cursor.fetchone()
        raw_price = float(rp[0]) if rp and rp[0] is not None else price

        qty = qty_entry_cart.get()
        if not qty.isdigit() or int(qty) <= 0:
            messagebox.showerror("Error", "Enter valid quantity", parent=root)
            return
        qty = int(qty)
        if qty > quantity:
            messagebox.showerror("Error", "Not enough stock", parent=root)
            return

        # Add or update cart
        for item in cart:
            if item['id'] == product_id:
                item['qty'] += qty
                item['total'] = item['qty'] * item['price']
                break
        else:
            cart.append({'id': product_id, 'name': name, 'qty': qty, 'price': price,
                         'raw_price': raw_price, 'total': qty*price})

        update_cart()

    def update_cart():
        nonlocal cart
        cart_tree.delete(*cart_tree.get_children())
        total = 0
        for item in cart:
            cart_tree.insert("", tk.END, values=(item['id'], item['name'], item['qty'], f"{item['total']:.2f}"))
            total += item['total']
        total_label.config(text=f"Total: {total:.2f}")

    def generate_invoice_pdf(cart_items, total_amount, money_received, change, mode, platform, txn_id):
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
        conn.commit()

        pdf_path = generate_invoice_pdf(cart, total_amount, money_received, change, mode, platform, txn_id)
        cart.clear()
        update_cart()
        load_inventory()
        messagebox.showinfo("Success", f"Payment completed. Invoice saved to:\n{pdf_path}", parent=root)
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

        tk.Label(pay_modal, text=f"Total Amount: {total_amount:.2f}", font=("Arial", 14, "bold"), bg="white").pack(pady=(12, 6))

        pay_mode = tk.StringVar(value="Cash")
        mode_frame = tk.Frame(pay_modal, bg="white")
        mode_frame.pack(fill="x", padx=12, pady=6)
        tk.Radiobutton(mode_frame, text="Cash", variable=pay_mode, value="Cash", bg="white", command=on_mode_change).pack(side="left", padx=6)
        tk.Radiobutton(mode_frame, text="Online Payment", variable=pay_mode, value="Online", bg="white", command=on_mode_change).pack(side="left", padx=6)

        money_frame = tk.Frame(pay_modal, bg="white")
        money_frame.pack(fill="x", padx=12, pady=6)
        tk.Label(money_frame, text="Money Received:", bg="white", font=("Arial", 11)).pack(anchor="w")
        money_entry = tk.Entry(money_frame, font=("Arial", 12))
        money_entry.pack(fill="x", pady=4)
        money_entry.insert(0, f"{total_amount:.2f}")
        money_entry.bind("<KeyRelease>", update_change)

        change_var = tk.StringVar(value="Change: 0.00")
        tk.Label(pay_modal, textvariable=change_var, bg="white", font=("Arial", 11, "bold")).pack(anchor="w", padx=12)

        qr_frame = tk.Frame(pay_modal, bg="white", highlightthickness=1, highlightbackground="#d1d5db")
        tk.Label(qr_frame, text="QR / Online Payment Placeholder", bg="white", fg="#6b7280").pack(padx=20, pady=20)

        platform_frame = tk.Frame(pay_modal, bg="white")
        platform_frame.pack(fill="x", padx=12, pady=6)
        tk.Label(platform_frame, text="Platform (e.g., GCash/Bank):", bg="white").pack(anchor="w")
        platform_entry = tk.Entry(platform_frame, font=("Arial", 11))
        platform_entry.pack(fill="x", pady=4)

        btns = tk.Frame(pay_modal, bg="white")
        btns.pack(pady=12)
        tk.Button(btns, text="Pay & Print", bg="#16a34a", fg="white", font=("Arial", 11, "bold"),
                  command=on_pay).pack(side="left", padx=6)
        tk.Button(btns, text="Cancel", bg="#ef4444", fg="white", font=("Arial", 11, "bold"),
                  command=pay_modal.destroy).pack(side="left", padx=6)

        on_mode_change()

    # Called when an item in the cart is selected
    def on_cart_select(event):
        selected = cart_tree.focus()
        if not selected:
            return
        values = cart_tree.item(selected, "values")
        qty = values[2]  # Quantity in the cart
        qty_entry_cart.delete(0, tk.END)
        qty_entry_cart.insert(0, qty)

# Remove or update the selected item in the cart
    def remove_from_cart():
        nonlocal cart
        selected = cart_tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select an item from cart to remove", parent=root)
            return
        values = cart_tree.item(selected, "values")
        item_id = int(values[0])

        # Get the quantity to remove from entry box
        qty_to_remove = qty_entry_cart.get()
        if not qty_to_remove.isdigit() or int(qty_to_remove) <= 0:
            messagebox.showerror("Error", "Enter a valid quantity to remove", parent=root)
            return
        qty_to_remove = int(qty_to_remove)

        # Find the item in the cart
        for item in cart:
            if item['id'] == item_id:
                name = item['name']
                if qty_to_remove >= item['qty']:
                    cart.remove(item)  # Remove completely if quantity >= in cart
                    messagebox.showinfo("Removed", f"{name} removed from cart", parent=root)
                else:
                    item['qty'] -= qty_to_remove  # Reduce quantity
                    item['total'] = item['qty'] * item['price']
                    messagebox.showinfo("Removed", f"{qty_to_remove} of {name} removed from cart", parent=root)
                break

        update_cart()
        qty_entry_cart.delete(0, tk.END)

    def back_to_main():
        root.destroy()

    # ---------- GUI ----------
    root = tk.Toplevel()
    root.title("POS System")
    root.state("zoomed")  # Fullscreen
    root.configure(bg="#f4f6f9")

    root.transient()        # link to main window
    root.grab_set()         # lock focus to POS

    # ====== Top Frame (Search + Back) ======
    top_frame = tk.Frame(root, bg="#f4f6f9", pady=10)
    top_frame.pack(fill="x")

    tk.Label(top_frame, text="Search Inventory:", bg="#f4f6f9").pack(side=tk.LEFT, padx=10)
    search_entry = ttk.Combobox(top_frame, width=30, font=("Arial", 11))
    search_entry.pack(side=tk.LEFT, padx=10)
    def update_suggestions(event=None):
        text = search_entry.get()
        filtered = [n for n in inventory_names if text.lower() in n.lower()]
        search_entry["values"] = filtered
    search_entry.bind("<KeyRelease>", lambda e: (update_suggestions(), load_inventory(search_entry.get())))
    tk.Button(top_frame, text="Search", bg="#17a2b8", fg="white", font=("Arial", 10, "bold"),
              command=lambda: load_inventory(search_entry.get())).pack(side=tk.LEFT, padx=10)
    tk.Button(top_frame, text="Back", bg="#dc3545", fg="white", font=("Arial", 10, "bold"),
              command=back_to_main).pack(side=tk.RIGHT, padx=20)

    # ====== Main Frame ======
    main_frame = tk.Frame(root, bg="#f4f6f9")
    main_frame.pack(fill="both", expand=True, padx=10, pady=5)

    # Left Frame - Inventory
    left_frame = tk.Frame(main_frame, bg="white", padx=10, pady=10)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0,5))
    tk.Label(left_frame, text="Inventory", font=("Arial", 14, "bold"), bg="white").pack(pady=5)

    global inv_tree
    inv_tree = ttk.Treeview(left_frame, columns=("ID","Name","Quantity","Price"), show="headings")
    inv_tree.pack(fill=tk.BOTH, expand=True)
    for col in ("ID","Name","Quantity","Price"):
        inv_tree.heading(col, text=col)
        inv_tree.column(col, width=120, anchor="center")

    # Right Frame - Cart / POS
    right_frame = tk.Frame(main_frame, bg="#f4f6f9", padx=10, pady=10)
    right_frame.pack(side="right", fill="both", expand=True, padx=(5,0))

    tk.Label(right_frame, text="Cart / POS", font=("Arial", 14, "bold"), bg="#f4f6f9").pack(pady=5)

    # Qty + Add + Remove button
    cart_frame = tk.Frame(right_frame, bg="#f4f6f9")
    cart_frame.pack(pady=5)

    tk.Label(cart_frame, text="Qty:", font=("Arial", 10), bg="#f4f6f9").grid(row=0, column=0, padx=5)
    global qty_entry_cart
    qty_entry_cart = tk.Entry(cart_frame, width=5, font=("Arial", 11))
    qty_entry_cart.grid(row=0, column=1, padx=5)

    tk.Button(cart_frame, text="Add to Cart", bg="#28a745", fg="white", font=("Arial", 10, "bold"),
            command=add_to_cart).grid(row=0, column=2, padx=5)

    tk.Button(cart_frame, text="Remove Selected Item", bg="#dc3545", fg="white", font=("Arial", 10, "bold"),
            command=remove_from_cart).grid(row=0, column=3, padx=5)
        # Cart Treeview
    global cart_tree
    cart_tree = ttk.Treeview(right_frame, columns=("ID","Name","Qty","Total"), show="headings")
    cart_tree.pack(fill="both", expand=True, pady=5)
    for col, w in (("ID",80), ("Name",180), ("Qty",80), ("Total",120)):
            cart_tree.heading(col, text=col)
            cart_tree.column(col, width=w, anchor="center")

    global total_label
    total_label = tk.Label(right_frame, text="Total: 0.00", font=("Arial", 14, "bold"), bg="#f4f6f9")
    total_label.pack(pady=5)

    # Checkout buttons
    btn_frame_right = tk.Frame(right_frame, bg="#f4f6f9")
    btn_frame_right.pack(pady=10)
    tk.Button(btn_frame_right, text="Pay / Checkout", bg="#ffc107", fg="black", width=22, font=("Arial", 11, "bold"),
              command=open_payment_modal).grid(row=0,column=0,padx=5)
    tk.Button(btn_frame_right, text="Remove Selected Item", bg="#dc3545", fg="white", width=22, font=("Arial", 11, "bold"),
              command=remove_from_cart).grid(row=0,column=1,padx=5)

    load_inventory()
    root.mainloop()
