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
        price REAL NOT NULL
    )
    """)
    conn.commit()

    cart = []

    # ---------- Inventory ----------
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
            cart.append({'id': product_id, 'name': name, 'qty': qty, 'price': price, 'total': qty*price})

        update_cart()

    def update_cart():
        nonlocal cart
        cart_tree.delete(*cart_tree.get_children())
        total = 0
        for item in cart:
            cart_tree.insert("", tk.END, values=(item['name'], f"{item['price']:.2f}", item['qty'], f"{item['total']:.2f}"))
            total += item['total']
        total_label.config(text=f"Total: {total:.2f}")

    def checkout():
        nonlocal cart
        if not cart:
            messagebox.showerror("Error", "Cart is empty", parent=root)
            return

        for item in cart:
            cursor.execute("UPDATE items SET quantity = quantity - ? WHERE id=?", (item['qty'], item['id']))
        conn.commit()

        display_invoice()
        cart.clear()
        update_cart()
        load_inventory()

    def display_invoice():
        invoice_text.delete("1.0", tk.END)
        if not cart:
            messagebox.showinfo("POS Invoice", "Cart is empty.", parent=root)
            return
        invoice_text.insert(tk.END, "===== POS Invoice =====\n")
        invoice_text.insert(tk.END, f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
        invoice_text.insert(tk.END, f"{'Product':20} {'Price':10} {'Qty':5} {'Total':10}\n")
        total_amount = 0
        for item in cart:
            invoice_text.insert(tk.END, f"{item['name']:20} {item['price']:10.2f} {item['qty']:5} {item['total']:10.2f}\n")
            total_amount += item['total']
        invoice_text.insert(tk.END, f"\nTotal Amount: {total_amount:.2f}\n")
        invoice_text.insert(tk.END, "======================\n")

    def print_receipt():
        if not cart:  # Check if cart is empty
            messagebox.showerror("Error", "Cart is empty. Cannot print receipt.", parent=root)
            return

        documents_path = os.path.expanduser("~/Documents")
        pdf_path = os.path.join(documents_path, "receipt.pdf")
        pdf = FPDF()
        pdf.add_page()
        pdf.set_font("Arial", 'B', 16)
        pdf.cell(0, 10, "POS Receipt", ln=True, align="C")
        pdf.set_font("Arial", '', 12)
        pdf.multi_cell(0, 8, invoice_text.get("1.0", tk.END))
        pdf.output(pdf_path)
        messagebox.showinfo("Success", f"Receipt saved to {pdf_path}", parent=root)

    # Called when an item in the cart is selected
    def on_cart_select(event):
        selected = cart_tree.focus()
        if not selected:
            return
        values = cart_tree.item(selected, "values")
        name = values[0]
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
        name = values[0]

        # Get the quantity to remove from entry box
        qty_to_remove = qty_entry_cart.get()
        if not qty_to_remove.isdigit() or int(qty_to_remove) <= 0:
            messagebox.showerror("Error", "Enter a valid quantity to remove", parent=root)
            return
        qty_to_remove = int(qty_to_remove)

        # Find the item in the cart
        for item in cart:
            if item['name'] == name:
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
    search_entry = tk.Entry(top_frame, width=30, font=("Arial", 11))
    search_entry.pack(side=tk.LEFT, padx=10)
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
    cart_tree = ttk.Treeview(right_frame, columns=("Name","Price","Qty","Total"), show="headings")
    cart_tree.pack(fill="both", expand=True, pady=5)
    for col in ("Name","Price","Qty","Total"):
            cart_tree.heading(col, text=col)
            cart_tree.column(col, width=100, anchor="center")

    global total_label
    total_label = tk.Label(right_frame, text="Total: 0.00", font=("Arial", 14, "bold"), bg="#f4f6f9")
    total_label.pack(pady=5)

    # Invoice Preview
    tk.Label(right_frame, text="Invoice Preview:", font=("Arial", 12, "bold"), bg="#f4f6f9").pack()
    global invoice_text
    invoice_text = tk.Text(right_frame, height=12, width=60, font=("Arial", 10))
    invoice_text.pack(pady=5)

    # Checkout / Print buttons
    btn_frame_right = tk.Frame(right_frame, bg="#f4f6f9")
    btn_frame_right.pack(pady=5)
    tk.Button(btn_frame_right, text="Pay / Checkout", bg="#ffc107", fg="black", width=20, font=("Arial", 10, "bold"),
              command=checkout).grid(row=0,column=0,padx=5)
    tk.Button(btn_frame_right, text="Print Receipt", bg="#17a2b8", fg="white", width=20, font=("Arial", 10, "bold"),
              command=print_receipt).grid(row=0,column=1,padx=5)

    load_inventory()
    root.mainloop()