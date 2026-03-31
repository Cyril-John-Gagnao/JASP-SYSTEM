import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
import os

DB_NAME = os.path.join(os.path.dirname(__file__), "jasp.db")
# Prevent multiple inventory windows
inventory_window = None

def open_inventory():
    global inventory_window
    if inventory_window and inventory_window.winfo_exists():
        inventory_window.focus()
        return

    # ---------- DB Setup ----------
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Add raw_price column if not exists
    cursor.execute("PRAGMA table_info(items)")
    columns = [col[1] for col in cursor.fetchall()]
    if "raw_price" not in columns:
        cursor.execute("ALTER TABLE items ADD COLUMN raw_price REAL DEFAULT 0")
        conn.commit()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        quantity INTEGER NOT NULL,
        price REAL NOT NULL,
        raw_price REAL DEFAULT 0
    )
    """)
    conn.commit()

    # ---------- GUI ----------
    inventory_window = tk.Toplevel()
    inventory_window.title("Inventory Management")
    inventory_window.state("zoomed")
    inventory_window.configure(bg="#f4f6f9")

    tk.Label(inventory_window, text="Inventory Management", font=("Arial", 20, "bold"), bg="#f4f6f9").pack(pady=15)

    main_frame = tk.Frame(inventory_window, bg="#f4f6f9")
    main_frame.pack(fill="both", expand=True, padx=20, pady=10)

    # -------- Left Frame: CRUD Form ----------
    left_frame = tk.Frame(main_frame, bg="white", padx=20, pady=20, bd=2, relief="groove")
    left_frame.pack(side="left", fill="y", padx=(0,10), pady=5)

    tk.Label(left_frame, text="Item Name", font=("Arial", 11, "bold"), bg="white").grid(row=0, column=0, padx=10, pady=5, sticky="w")
    name_entry = tk.Entry(left_frame, width=25, font=("Arial", 11))
    name_entry.grid(row=0, column=1, pady=5)

    tk.Label(left_frame, text="Quantity", font=("Arial", 11, "bold"), bg="white").grid(row=1, column=0, padx=10, pady=5, sticky="w")
    quantity_entry = tk.Entry(left_frame, width=25, font=("Arial", 11))
    quantity_entry.grid(row=1, column=1, pady=5)

    tk.Label(left_frame, text="Selling Price", font=("Arial", 11, "bold"), bg="white").grid(row=2, column=0, padx=10, pady=5, sticky="w")
    price_entry = tk.Entry(left_frame, width=25, font=("Arial", 11))
    price_entry.grid(row=2, column=1, pady=5)

    tk.Label(left_frame, text="Raw Price", font=("Arial", 11, "bold"), bg="white").grid(row=3, column=0, padx=10, pady=5, sticky="w")
    raw_price_entry = tk.Entry(left_frame, width=25, font=("Arial", 11))
    raw_price_entry.grid(row=3, column=1, pady=5)

    # ---------- CRUD Functions ----------
    def view_items(filter_text=""):
        for row in tree.get_children():
            tree.delete(row)
        if filter_text:
            cursor.execute("SELECT * FROM items WHERE name LIKE ?", (f"%{filter_text}%",))
        else:
            cursor.execute("SELECT * FROM items")
        rows = cursor.fetchall()
        for row in rows:
            tree.insert("", tk.END, values=row)

    def clear_fields():
        name_entry.delete(0, tk.END)
        quantity_entry.delete(0, tk.END)
        price_entry.delete(0, tk.END)
        raw_price_entry.delete(0, tk.END)

    def add_item():
        name = name_entry.get()
        quantity = quantity_entry.get()
        price = price_entry.get()
        raw = raw_price_entry.get()
        if not name or not quantity or not price or not raw:
            messagebox.showerror("Error", "All fields are required!", parent=inventory_window)
            return
        cursor.execute("INSERT INTO items (name, quantity, price, raw_price) VALUES (?, ?, ?, ?)",
                       (name, quantity, price, raw))
        conn.commit()
        messagebox.showinfo("Success", "Item Added Successfully!", parent=inventory_window)
        inventory_window.lift()
        inventory_window.focus_force()
        clear_fields()
        view_items()

    def update_item():
        selected = tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select an item to update", parent=inventory_window)
            return
        values = tree.item(selected, "values")
        item_id = values[0]
        cursor.execute("UPDATE items SET name=?, quantity=?, price=?, raw_price=? WHERE id=?",
                       (name_entry.get(), quantity_entry.get(), price_entry.get(), raw_price_entry.get(), item_id))
        conn.commit()
        messagebox.showinfo("Success", "Item Updated Successfully!", parent=inventory_window)
        inventory_window.lift()
        inventory_window.focus_force()
        clear_fields()
        view_items()

    def delete_item():
        selected = tree.focus()
        if not selected:
            messagebox.showerror("Error", "Select an item to delete", parent=inventory_window)
            return
        values = tree.item(selected, "values")
        item_id = values[0]
        cursor.execute("DELETE FROM items WHERE id=?", (item_id,))
        conn.commit()
        messagebox.showinfo("Success", "Item Deleted Successfully!", parent=inventory_window)
        inventory_window.lift()
        inventory_window.focus_force()
        view_items()

    def select_item(event):
        selected = tree.focus()
        if selected:
            values = tree.item(selected, "values")
            name_entry.delete(0, tk.END)
            quantity_entry.delete(0, tk.END)
            price_entry.delete(0, tk.END)
            raw_price_entry.delete(0, tk.END)
            name_entry.insert(0, values[1])
            quantity_entry.insert(0, values[2])
            price_entry.insert(0, values[3])
            raw_price_entry.insert(0, values[4])

    def search_items(event):
        view_items(search_entry.get())

    def back_to_main():
        inventory_window.destroy()

    # ---------- Buttons ----------
    tk.Button(left_frame, text="Add Item", width=15, bg="#28a745", fg="white", font=("Arial", 11, "bold"), command=add_item).grid(row=4, column=0, pady=10)
    tk.Button(left_frame, text="Update Item", width=15, bg="#007bff", fg="white", font=("Arial", 11, "bold"), command=update_item).grid(row=4, column=1, pady=10)
    tk.Button(left_frame, text="Delete Item", width=15, bg="#dc3545", fg="white", font=("Arial", 11, "bold"), command=delete_item).grid(row=5, column=0, pady=10)
    tk.Button(left_frame, text="Clear", width=15, bg="#6c757d", fg="white", font=("Arial", 11, "bold"), command=clear_fields).grid(row=5, column=1, pady=10)
    tk.Button(left_frame, text="Back", width=32, bg="#ffc107", fg="black", font=("Arial", 11, "bold"), command=back_to_main).grid(row=6, column=0, columnspan=2, pady=20)

    # -------- Right Frame: Table + Search ----------
    right_frame = tk.Frame(main_frame, bg="#f4f6f9", padx=10, pady=10)
    right_frame.pack(side="right", fill="both", expand=True)

    tk.Label(right_frame, text="Search by Name:", font=("Arial", 11, "bold"), bg="#f4f6f9").pack(anchor="w")
    search_entry = tk.Entry(right_frame, font=("Arial", 11))
    search_entry.pack(fill="x", pady=5)
    search_entry.bind("<KeyRelease>", search_items)

    tree_frame = tk.Frame(right_frame)
    tree_frame.pack(fill="both", expand=True, pady=10)

    tree = ttk.Treeview(tree_frame, columns=("ID", "Name", "Quantity", "Price", "Raw Price"), show="headings", selectmode="browse")
    v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    v_scroll.pack(side="right", fill="y")
    h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    h_scroll.pack(side="bottom", fill="x")
    tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
    tree.pack(fill="both", expand=True)

    tree.heading("ID", text="ID")
    tree.column("ID", width=70, anchor="center")
    tree.heading("Name", text="Name")
    tree.column("Name", width=250, anchor="w")
    tree.heading("Quantity", text="Quantity")
    tree.column("Quantity", width=120, anchor="center")
    tree.heading("Price", text="Selling Price")
    tree.column("Price", width=120, anchor="center")
    tree.heading("Raw Price", text="Raw Price")
    tree.column("Raw Price", width=120, anchor="center")

    tree.bind("<ButtonRelease-1>", select_item)

    view_items()