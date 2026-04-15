import tkinter as tk
from tkinter import ttk, messagebox
import sqlite3
from datetime import datetime
import os

DB_NAME = os.path.join(os.path.dirname(__file__), "jasp.db")

# 🎨 COLORS
BG_MAIN = "#eef6ff"
CARD_BG = "#ffffff"
PRIMARY = "#2563eb"
ACCENT = "#60a5fa"
TEXT = "#1e293b"
BORDER = "#dbeafe"


def init_delivery_db():
    """Initialize delivery table in database"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Check if table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='chb_delivery'")
    table_exists = cursor.fetchone()
    
    if not table_exists:
        # Create the table if it doesn't exist
        cursor.execute("""
            CREATE TABLE chb_delivery (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                delivery_date TEXT,
                worker_name TEXT,
                blocks_delivered INTEGER,
                payment_per_block REAL DEFAULT 2.0,
                total_payment REAL,
                ts TEXT
            )
        """)
        conn.commit()
    else:
        # Check if columns exist and add them if missing
        cursor.execute("PRAGMA table_info(chb_delivery)")
        columns = {row[1] for row in cursor.fetchall()}
        
        # Add missing columns
        if 'delivery_date' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN delivery_date TEXT")
        if 'payment_per_block' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN payment_per_block REAL DEFAULT 2.0")
        if 'total_payment' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN total_payment REAL")
        if 'ts' not in columns:
            cursor.execute("ALTER TABLE chb_delivery ADD COLUMN ts TEXT")
        
        conn.commit()
    
    conn.close()


def open_delivery_window(parent_win, bg_main, card_bg, primary):
    """Open delivery section window"""
    init_delivery_db()

    delivery_win = tk.Toplevel(parent_win)
    delivery_win.title("CHB Delivery Module")
    delivery_win.state("zoomed")
    delivery_win.configure(bg=bg_main)

    # Create a persistent connection that stays open for the window lifetime
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    selected_id = tk.StringVar()

    # ================= HEADER WITH CENTER TITLE =================
    header_frame = tk.Frame(delivery_win, bg=bg_main)
    header_frame.pack(fill="x", padx=20, pady=10)

    header_frame.columnconfigure(0, weight=1)
    header_frame.columnconfigure(1, weight=1)
    header_frame.columnconfigure(2, weight=1)

    tk.Label(
        header_frame,
        text="CHB Delivery Management",
        font=("Arial", 18, "bold"),
        bg=bg_main,
        fg=primary
    ).grid(row=0, column=1)

    def go_back():
        delivery_win.destroy()

    tk.Button(
        header_frame,
        text="← Back",
        command=go_back,
        bg=primary,
        fg="white",
        font=("Arial", 10, "bold"),
        padx=12,
        pady=5,
        relief="flat"
    ).grid(row=0, column=2, sticky="e")

    # ================= SEARCH & SORT =================
    search_frame = tk.Frame(delivery_win, bg=bg_main)
    search_frame.pack(fill="x", padx=20, pady=(0, 15))

    tk.Label(search_frame, text="🔍 Search:", bg=bg_main, fg=TEXT, font=("Arial", 12, "bold"))\
        .pack(side="left", padx=10, pady=10)

    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var, width=35, font=("Arial", 11), bd=2, relief="solid")
    search_entry.pack(side="left", padx=10, pady=10)

    tk.Label(search_frame, text="Sort By:", bg=bg_main, fg=TEXT, font=("Arial", 12, "bold"))\
        .pack(side="left", padx=(30, 10), pady=10)

    sort_var = tk.StringVar(value="Date (Latest)")

    sort_menu = ttk.Combobox(
        search_frame,
        textvariable=sort_var,
        values=["Date (Latest)", "Worker Name"],
        state="readonly",
        width=22,
        font=("Arial", 11)
    )
    sort_menu.pack(side="left", pady=10)

    # ================= MAIN CONTAINER (40-60 Split) =================
    main_container = tk.Frame(delivery_win, bg=card_bg, bd=1, relief="solid")
    main_container.pack(padx=20, pady=10, fill="both", expand=True)

    main_container.columnconfigure(0, weight=2)
    main_container.columnconfigure(1, weight=3)
    main_container.rowconfigure(0, weight=1)

    # ================= FORM (LEFT SIDE - 40%) =================
    form_card = tk.Frame(main_container, bg=card_bg)
    form_card.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
    form_card.columnconfigure(1, weight=1)

    tk.Label(form_card, text="Delivery Form", font=("Arial", 18, "bold"), bg=card_bg, fg=primary).pack(pady=(0, 20))

    form_bg = tk.Frame(form_card, bg="#fef3c7", bd=1, relief="flat")
    form_bg.pack(fill="x", padx=5, pady=10)

    form = tk.Frame(form_bg, bg="#fef3c7")
    form.pack(fill="x", padx=20, pady=20)

    # Delivery Date
    tk.Label(form, text="Delivery Date", bg="#fef3c7", font=("Arial", 11, "bold"), fg="#1e293b").grid(row=0, column=0, sticky="w", pady=10)
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    date_entry = tk.Entry(form, textvariable=date_var, width=20, font=("Arial", 11), bd=1, relief="solid", bg="white")
    date_entry.grid(row=0, column=1, sticky="ew", padx=15, pady=10)

    # Worker Name
    tk.Label(form, text="Worker Name", bg="#fef3c7", font=("Arial", 11, "bold"), fg="#1e293b").grid(row=1, column=0, sticky="w", pady=10)
    worker_entry = tk.Entry(form, width=20, font=("Arial", 11), bd=1, relief="solid", bg="white")
    worker_entry.grid(row=1, column=1, sticky="ew", padx=15, pady=10)

    # Blocks to be Delivered
    tk.Label(form, text="Blocks Delivered", bg="#fef3c7", font=("Arial", 11, "bold"), fg="#1e293b").grid(row=2, column=0, sticky="w", pady=10)
    blocks_entry = tk.Entry(form, width=20, font=("Arial", 11), bd=1, relief="solid", bg="white")
    blocks_entry.grid(row=2, column=1, sticky="ew", padx=15, pady=10)

    # Payment per Block
    tk.Label(form, text="Worker Salary / Block (₱)", bg="#fef3c7", font=("Arial", 11, "bold"), fg="#1e293b").grid(row=3, column=0, sticky="w", pady=10)
    payment_var = tk.DoubleVar(value=2.0)
    payment_entry = tk.Entry(form, textvariable=payment_var, width=20, font=("Arial", 11), bd=1, relief="solid", bg="white")
    payment_entry.grid(row=3, column=1, sticky="ew", padx=15, pady=10)

    form.columnconfigure(1, weight=1)

    # Result Display
    result_label = tk.Label(
        form_card,
        text="Total Salary of Worker: ₱0",
        font=("Arial", 14, "bold"),
        bg="#e0f2fe",
        fg="#0369a1",
        pady=12
    )
    result_label.pack(pady=15, fill="x", padx=5)

    # Buttons Frame
    btn_frame = tk.Frame(form_card, bg=card_bg)
    btn_frame.pack(pady=15, fill="x")

    # ================= AUTO CALC =================
    def auto_calc(event=None):
        try:
            blocks = int(blocks_entry.get() or 0)
            payment_per = float(payment_var.get() or 2.0)
            total = blocks * payment_per

            result_label.config(text=f"Total Payment: ₱{total:,.2f}")

        except:
            blocks_entry.delete(0, tk.END)
            result_label.config(text="Total Payment: ₱0")

    blocks_entry.bind("<KeyRelease>", auto_calc)
    payment_entry.bind("<KeyRelease>", auto_calc)

    # ================= FUNCTIONS =================
    def clear_form():
        worker_entry.delete(0, tk.END)
        blocks_entry.delete(0, tk.END)
        payment_var.set(2.0)
        result_label.config(text="Total Payment: ₱0")
        selected_id.set("")

    def save_delivery():
        try:
            blocks = int(blocks_entry.get())
            payment_per = float(payment_var.get())
            total = blocks * payment_per
        except:
            messagebox.showerror("Error", "Invalid input", parent=delivery_win)
            return

        worker = worker_entry.get()
        date = date_var.get()

        if not worker:
            messagebox.showerror("Error", "Fill all fields", parent=delivery_win)
            return

        if not messagebox.askyesno("Confirm Save", f"Save delivery record for {worker}?", parent=delivery_win):
            return

        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cursor.execute("""
            INSERT INTO chb_delivery
            (delivery_date, worker_name, blocks_delivered, payment_per_block, total_payment, ts)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (date, worker, blocks, payment_per, total, ts))

        conn.commit()
        load_data()
        clear_form()
        messagebox.showinfo("Success", "Delivery record saved successfully!", parent=delivery_win)

    def update_delivery():
        if not selected_id.get():
            messagebox.showerror("Error", "Select a record", parent=delivery_win)
            return

        try:
            blocks = int(blocks_entry.get())
            payment_per = float(payment_var.get())
            total = blocks * payment_per
        except:
            messagebox.showerror("Error", "Invalid input", parent=delivery_win)
            return

        if not messagebox.askyesno("Confirm Update", f"Update record for {worker_entry.get()}?", parent=delivery_win):
            return

        cursor.execute("""
            UPDATE chb_delivery
            SET delivery_date=?, worker_name=?, blocks_delivered=?, payment_per_block=?, total_payment=?
            WHERE id=?
        """, (
            date_var.get(),
            worker_entry.get(),
            blocks, payment_per, total,
            selected_id.get()
        ))

        conn.commit()
        load_data()
        clear_form()
        messagebox.showinfo("Success", "Record updated successfully!", parent=delivery_win)

    def delete_delivery():
        if not selected_id.get():
            return

        if not messagebox.askyesno("Confirm Delete", f"Delete record for {worker_entry.get()}?\n\nThis action cannot be undone.", parent=delivery_win):
            return

        cursor.execute("DELETE FROM chb_delivery WHERE id=?", (selected_id.get(),))
        conn.commit()
        load_data()
        clear_form()
        messagebox.showinfo("Success", "Record deleted successfully!", parent=delivery_win)

    # ================= BUTTONS =================
    tk.Button(btn_frame, text="✓ Save", command=save_delivery, bg="#15803d", fg="white", font=("Arial", 12, "bold"), width=12, padx=8, pady=10, relief="flat", cursor="hand2").pack(side="left", padx=6, pady=8)
    tk.Button(btn_frame, text="🔁 Update", command=update_delivery, bg="#1e40af", fg="white", font=("Arial", 12, "bold"), width=12, padx=8, pady=10, relief="flat", cursor="hand2").pack(side="left", padx=6, pady=8)
    tk.Button(btn_frame, text="🗑 Delete", command=delete_delivery, bg="#dc2626", fg="white", font=("Arial", 12, "bold"), width=12, padx=8, pady=10, relief="flat", cursor="hand2").pack(side="left", padx=6, pady=8)
    tk.Button(btn_frame, text="✋ Clear", command=clear_form, bg="#64748b", fg="white", font=("Arial", 12, "bold"), width=12, padx=8, pady=10, relief="flat", cursor="hand2").pack(side="left", padx=6, pady=8)

    # ================= TABLE (RIGHT SIDE - 60%) =================
    table_card = tk.Frame(main_container, bg=card_bg)
    table_card.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
    table_card.columnconfigure(0, weight=1)
    table_card.rowconfigure(0, weight=1)

    columns = ("id", "date", "worker", "blocks", "total Salary")

    # Configure Treeview with larger fonts and blue scrollbars
    style = ttk.Style()
    style.configure('Treeview', font=('Arial', 11), rowheight=28)
    style.configure('Treeview.Heading', font=('Arial', 12, 'bold'))

    # Create frame for tree and scrollbars
    tree_frame = tk.Frame(table_card, bg=card_bg)
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
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")

    # Configure scrollbars
    vsb.config(command=tree.yview)
    hsb.config(command=tree.xview)

    for col in columns:
        tree.heading(col, text=col.upper())
        tree.column(col, anchor="center", width=130)

    def on_select(event):
        selected = tree.focus()
        values = tree.item(selected, "values")

        if values:
            selected_id.set(values[0])
            date_var.set(values[1])
            worker_entry.delete(0, tk.END)
            worker_entry.insert(0, values[2])
            blocks_entry.delete(0, tk.END)
            blocks_entry.insert(0, values[3])
            auto_calc()

    tree.bind("<ButtonRelease-1>", on_select)

    # ================= LOAD DATA =================
    def load_data(event=None):
        try:
            for row in tree.get_children():
                tree.delete(row)

            keyword = search_var.get().lower()
            sort_option = sort_var.get()

            query = """
                SELECT id, delivery_date, worker_name, blocks_delivered, total_payment
                FROM chb_delivery
            """

            params = []

            if keyword:
                query += " WHERE LOWER(worker_name) LIKE ? OR delivery_date LIKE ?"
                params.extend([f"%{keyword}%", f"%{keyword}%"])

            if sort_option == "Worker Name":
                query += " ORDER BY worker_name ASC"
            else:
                query += " ORDER BY delivery_date DESC, ts DESC"

            cursor.execute(query, params)
            rows = cursor.fetchall()

            for row in rows:
                tree.insert("", "end", values=tuple(row))
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load data: {str(e)}", parent=delivery_win)

    # ✅ BINDINGS (LIVE SEARCH)
    search_entry.bind("<KeyRelease>", load_data)
    sort_menu.bind("<<ComboboxSelected>>", load_data)

    # ✅ WINDOW CLOSE HANDLER
    def on_closing():
        conn.close()
        delivery_win.destroy()

    delivery_win.protocol("WM_DELETE_WINDOW", on_closing)

    # ✅ INITIAL LOAD
    load_data()
