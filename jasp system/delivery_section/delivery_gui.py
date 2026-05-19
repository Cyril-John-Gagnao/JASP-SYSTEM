import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
from datetime import datetime

from .delivery_database import init_delivery_db, open_delivery_connection
from . import delivery_functions
from jasp_theme import (
    DASHBOARD_CONTENT_BG,
    DASHBOARD_HEADER_BG,
    DASHBOARD_HEADER_BORDER,
    DASHBOARD_HEADER_FG,
    add_header_logo,
)

# COLORS
BG_MAIN = DASHBOARD_CONTENT_BG
CARD_BG = "#ffffff"
PRIMARY = "#2563eb"
ACCENT = "#60a5fa"
TEXT = "#1e293b"
BORDER = "#dbeafe"

BUTTON_BORDER = {
    "bd": 2,
    "relief": "solid",
    "highlightthickness": 1,
    "highlightbackground": "black",
    "highlightcolor": "black",
}


def open_delivery_window(parent_win, bg_main, card_bg, primary):
    """Open delivery section window"""
    init_delivery_db()

    delivery_win = tk.Toplevel(parent_win)
    delivery_win.title("CHB Delivery Module")
    delivery_win.state("zoomed")
    delivery_win.configure(bg=bg_main)

    # Create a persistent connection that stays open for the window lifetime
    conn, cursor = open_delivery_connection()

    selected_id = tk.StringVar()

    # ================= HEADER =================
    header_frame = tk.Frame(delivery_win, bg=DASHBOARD_HEADER_BG, padx=14, pady=10, highlightthickness=1, highlightbackground=DASHBOARD_HEADER_BORDER)
    header_frame.pack(fill="x", padx=20, pady=10)

    header_frame.columnconfigure(0, weight=1)
    header_frame.columnconfigure(1, weight=0)

    title_frame = tk.Frame(header_frame, bg=DASHBOARD_HEADER_BG)
    title_frame.grid(row=0, column=0, sticky="w")
    add_header_logo(title_frame, DASHBOARD_HEADER_BG, size=52)

    tk.Label(
        title_frame,
        text="CHB Delivery Management",
        font=("Arial", 26, "bold"),
        bg=DASHBOARD_HEADER_BG,
        fg=DASHBOARD_HEADER_FG
    ).pack(side="left")

    # RIGHT: Button container for Refresh and Back
    btn_container = tk.Frame(header_frame, bg=DASHBOARD_HEADER_BG)
    btn_container.grid(row=0, column=1, sticky="e")

    tk.Button(
        btn_container,
        text="🔄 Refresh",
        command=lambda: delivery_functions.refresh_data(load_data),
        bg="#16a34a",
        fg="white",
        font=("Arial", 13, "bold"),
        padx=12,
        pady=5,
        **BUTTON_BORDER
    ).pack(side="left", padx=3)

    tk.Button(
        btn_container,
        text="← Back",
        command=lambda: delivery_functions.go_back(delivery_win),
        bg=primary,
        fg="white",
        font=("Arial", 13, "bold"),
        padx=12,
        pady=5,
        **BUTTON_BORDER
    ).pack(side="left", padx=3)

    # ================= SEARCH & SORT =================
    search_frame = tk.Frame(delivery_win, bg=bg_main)
    search_frame.pack(fill="x", padx=20, pady=(0, 15))

    tk.Label(search_frame, text="Search:", bg=bg_main, fg=TEXT, font=("Arial", 15, "bold"))\
        .pack(side="left", padx=10, pady=10)

    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var, width=35, font=("Arial", 14), bd=2, relief="solid")
    search_entry.pack(side="left", padx=10, pady=10)

    tk.Label(search_frame, text="Sort By:", bg=bg_main, fg=TEXT, font=("Arial", 15, "bold"))\
        .pack(side="left", padx=(30, 10), pady=10)

    sort_var = tk.StringVar(value="Date (Latest)")

    sort_menu = ttk.Combobox(
        search_frame,
        textvariable=sort_var,
        values=["Date (Latest)", "Worker Name"],
        state="readonly",
        width=22,
        font=("Arial", 14)
    )
    sort_menu.pack(side="left", pady=10)

    tk.Button(search_frame, text="Summary", command=lambda: delivery_functions.open_delivery_summary(delivery_win, cursor, bg_main, TEXT), bg="#8b5cf6", fg="white", font=("Arial", 13, "bold"), padx=12, pady=6, **BUTTON_BORDER).pack(side="left", padx=10)

    display_option_var = tk.StringVar(value="Option 1")

    tk.Button(
        search_frame,
        text="Other Items to Deliver",
        command=lambda: delivery_functions.open_other_items_form(delivery_win, conn, cursor, load_data, display_option_var),
        bg="#f59e0b",
        fg="white",
        font=("Arial", 13, "bold"),
        padx=12,
        pady=6,
        cursor="hand2",
        **BUTTON_BORDER
    ).pack(side="left", padx=(0, 10))

    fullscreen_btn = tk.Button(
        search_frame,
        text="Full Screen Display",
        command=lambda: toggle_display_fullscreen(),
        bg="#0f766e",
        fg="white",
        font=("Arial", 13, "bold"),
        padx=12,
        pady=6,
        cursor="hand2",
        **BUTTON_BORDER
    )
    fullscreen_btn.pack(side="left", padx=(0, 10))

    total_frame = tk.Frame(delivery_win, bg=bg_main)
    total_frame.pack(fill="x", padx=20, pady=(0, 8))

    total_delivered_var = tk.StringVar(value="Total CHB Blocks Delivered Today: 0")
    tk.Label(
        total_frame,
        textvariable=total_delivered_var,
        bg=bg_main,
        fg="#1e40af",
        font=("Arial", 18, "bold")
    ).pack(side="left", padx=10)

    # ================= MAIN CONTAINER (60-40 Split) =================
    main_container = tk.Frame(delivery_win, bg=card_bg, bd=1, relief="solid")
    main_container.pack(padx=20, pady=(5, 10), fill="both", expand=True)

    main_container.columnconfigure(0, weight=3, uniform="delivery")
    main_container.columnconfigure(1, weight=2, uniform="delivery")
    main_container.rowconfigure(0, weight=1)

    # ================= FORM (RIGHT SIDE - 40%) =================
    form_card = tk.Frame(main_container, bg=card_bg)
    form_card.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
    form_card.columnconfigure(1, weight=1)

    tk.Label(form_card, text="Delivery Form", font=("Arial", 16, "bold"), bg=card_bg, fg=primary).pack(pady=(0, 8))

    form_bg = tk.Frame(form_card, bg="#fef3c7", bd=1, relief="flat")
    form_bg.pack(fill="x", padx=5, pady=4)

    form = tk.Frame(form_bg, bg="#fef3c7")
    form.pack(fill="x", padx=16, pady=10)
    form.columnconfigure(0, weight=0)
    form.columnconfigure(1, weight=1)

    # Transaction Date
    tk.Label(form, text="Transaction Date", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=0, column=0, sticky="w", pady=5)
    transaction_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    transaction_date_frame = tk.Frame(form, bg="#fef3c7")
    transaction_date_frame.grid(row=0, column=1, sticky="ew", padx=12, pady=5)
    transaction_date_entry = tk.Entry(transaction_date_frame, textvariable=transaction_date_var, width=17, font=("Arial", 13), bd=1, relief="solid", bg="white")
    transaction_date_entry.pack(side="left", fill="x", expand=True)
    tk.Button(transaction_date_frame, text="📅", command=lambda: delivery_functions.open_date_calendar(delivery_win, transaction_date_var), bg="#3b82f6", fg="white", font=("Arial", 11, "bold"), width=3, padx=4, pady=2, **BUTTON_BORDER).pack(side="left", padx=(5, 0))

    # Delivery Date
    tk.Label(form, text="Delivery Date", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=1, column=0, sticky="w", pady=5)
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    date_frame = tk.Frame(form, bg="#fef3c7")
    date_frame.grid(row=1, column=1, sticky="ew", padx=12, pady=5)
    date_entry = tk.Entry(date_frame, textvariable=date_var, width=17, font=("Arial", 13), bd=1, relief="solid", bg="white")
    date_entry.pack(side="left", fill="x", expand=True)
    tk.Button(date_frame, text="📅", command=lambda: delivery_functions.open_date_calendar(delivery_win, date_var), bg="#3b82f6", fg="white", font=("Arial", 11, "bold"), width=3, padx=4, pady=2, **BUTTON_BORDER).pack(side="left", padx=(5, 0))

    # Worker Name
    tk.Label(form, text="Worker Name", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=2, column=0, sticky="w", pady=5)
    worker_entry = tk.Entry(form, width=20, font=("Arial", 13), bd=1, relief="solid", bg="white")
    worker_entry.grid(row=2, column=1, sticky="ew", padx=12, pady=5)

    # Driver Name
    tk.Label(form, text="Driver Name", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=3, column=0, sticky="w", pady=5)
    driver_entry = tk.Entry(form, width=20, font=("Arial", 13), bd=1, relief="solid", bg="white")
    driver_entry.grid(row=3, column=1, sticky="ew", padx=12, pady=5)

    # Delivery Address
    tk.Label(form, text="Delivery Address", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=4, column=0, sticky="w", pady=5)
    address_entry = tk.Entry(form, width=20, font=("Arial", 13), bd=1, relief="solid", bg="white")
    address_entry.grid(row=4, column=1, sticky="ew", padx=12, pady=5)

    # Blocks to be Delivered
    tk.Label(form, text="Blocks to be Delivered", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=5, column=0, sticky="w", pady=5)
    blocks_entry = tk.Entry(form, width=20, font=("Arial", 13), bd=1, relief="solid", bg="white")
    blocks_entry.grid(row=5, column=1, sticky="ew", padx=12, pady=5)

    # Delivery Fee
    tk.Label(form, text="Delivery Fee (₱)", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=6, column=0, sticky="w", pady=5)
    delivery_fee_entry = tk.Entry(form, width=20, font=("Arial", 13), bd=1, relief="solid", bg="white")
    delivery_fee_entry.grid(row=6, column=1, sticky="ew", padx=12, pady=5)

    # Payment per Block
    tk.Label(form, text="Worker Salary / Block (₱)", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=7, column=0, sticky="w", pady=5)
    payment_var = tk.DoubleVar(value=2.0)
    payment_entry = tk.Entry(form, textvariable=payment_var, width=20, font=("Arial", 13), bd=1, relief="solid", bg="white")
    payment_entry.grid(row=7, column=1, sticky="ew", padx=12, pady=5)

    # Result Display
    result_label = tk.Label(
        form_card,
        text="Total Salary of Worker: ₱0",
        font=("Arial", 14, "bold"),
        bg="#e0f2fe",
        fg="#0369a1",
        pady=8
    )
    result_label.pack(pady=8, fill="x", padx=5)

    # Buttons Frame
    btn_frame = tk.Frame(form_card, bg=card_bg)
    btn_frame.pack(pady=6, fill="x")
    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)

    # ================= AUTO CALC =================
    auto_calc = lambda event=None: delivery_functions.auto_calc(event, blocks_entry, payment_var, result_label)

    blocks_entry.bind("<KeyRelease>", auto_calc)
    payment_entry.bind("<KeyRelease>", auto_calc)

    # ================= FUNCTIONS =================
    clear_form = lambda: delivery_functions.clear_form(transaction_date_var, date_var, worker_entry, driver_entry, address_entry, blocks_entry, delivery_fee_entry, payment_var, result_label, selected_id)
    save_delivery = lambda: delivery_functions.save_delivery(conn, cursor, delivery_win, transaction_date_var, worker_entry, date_var, driver_entry, address_entry, blocks_entry, delivery_fee_entry, payment_var, load_data, clear_form)
    update_delivery = lambda: delivery_functions.update_delivery(conn, cursor, delivery_win, selected_id, transaction_date_var, worker_entry, date_var, driver_entry, address_entry, blocks_entry, delivery_fee_entry, payment_var, load_data, clear_form)
    delete_delivery = lambda: delivery_functions.delete_delivery(conn, cursor, delivery_win, selected_id, worker_entry, load_data, clear_form)

    # ================= BUTTONS =================
    tk.Button(btn_frame, text="Save", command=save_delivery, bg="#15803d", fg="white", font=("Arial", 12, "bold"), padx=8, pady=7, cursor="hand2", **BUTTON_BORDER).grid(row=0, column=0, sticky="ew", padx=6, pady=4)
    tk.Button(btn_frame, text="Update", command=update_delivery, bg="#1e40af", fg="white", font=("Arial", 12, "bold"), padx=8, pady=7, cursor="hand2", **BUTTON_BORDER).grid(row=0, column=1, sticky="ew", padx=6, pady=4)
    tk.Button(btn_frame, text="Delete", command=delete_delivery, bg="#dc2626", fg="white", font=("Arial", 12, "bold"), padx=8, pady=7, cursor="hand2", **BUTTON_BORDER).grid(row=1, column=0, sticky="ew", padx=6, pady=4)
    tk.Button(btn_frame, text="Clear", command=clear_form, bg="#64748b", fg="white", font=("Arial", 12, "bold"), padx=8, pady=7, cursor="hand2", **BUTTON_BORDER).grid(row=1, column=1, sticky="ew", padx=6, pady=4)

    # ================= TABLE (LEFT SIDE - 60%) =================
    table_card = tk.Frame(main_container, bg=card_bg)
    table_card.grid(row=0, column=0, sticky="nsew", padx=15, pady=15)
    table_card.columnconfigure(0, weight=1)
    table_card.rowconfigure(1, weight=1)

    display_fullscreen = tk.BooleanVar(value=False)

    def toggle_display_fullscreen():
        if display_fullscreen.get():
            form_card.grid(row=0, column=1, sticky="nsew", padx=15, pady=15)
            table_card.grid_configure(row=0, column=0, columnspan=1, sticky="nsew", padx=15, pady=15)
            main_container.columnconfigure(0, weight=3, uniform="delivery")
            main_container.columnconfigure(1, weight=2, minsize=0, uniform="delivery")
            fullscreen_btn.config(text="Full Screen Display", bg="#0f766e")
            display_fullscreen.set(False)
        else:
            form_card.grid_remove()
            table_card.grid_configure(row=0, column=0, columnspan=2, sticky="nsew", padx=15, pady=15)
            main_container.columnconfigure(0, weight=1, uniform="")
            main_container.columnconfigure(1, weight=0, minsize=0, uniform="")
            fullscreen_btn.config(text="Exit Full Screen", bg="#334155")
            display_fullscreen.set(True)
        delivery_win.after(50, auto_adjust_columns)

    columns = ("id", "transaction date", "delivery date", "worker", "driver", "address", "blocks", "delivery fee", "total Salary", "user")
    other_columns = ("id", "transaction date", "delivery date", "item name", "quantity", "unit of measurement", "delivery address", "delivery driver", "helper", "delivery fee", "user")
    active_columns = {"columns": columns}

    option_frame = tk.Frame(table_card, bg=card_bg)
    option_frame.grid(row=0, column=0, sticky="w", pady=(0, 10))
    tk.Label(option_frame, text="Display:", bg=card_bg, fg=TEXT, font=("Arial", 16, "bold")).pack(side="left", padx=(0, 10))
    tk.Radiobutton(
        option_frame,
        text="CHB Blocks",
        variable=display_option_var,
        value="Option 1",
        bg=card_bg,
        fg=TEXT,
        font=("Arial", 15, "bold"),
        command=lambda: load_data()
    ).pack(side="left", padx=10)
    tk.Radiobutton(
        option_frame,
        text="Other Items",
        variable=display_option_var,
        value="Option 2",
        bg=card_bg,
        fg=TEXT,
        font=("Arial", 15, "bold"),
        command=lambda: load_data()
    ).pack(side="left", padx=10)

    # Configure Treeview with larger fonts and blue scrollbars
    style = ttk.Style()
    style.configure('Treeview', font=('Arial', 14), rowheight=36)
    style.configure('Treeview.Heading', font=('Arial', 15, 'bold'))

    # Configure alternating row colors
    style.map('Treeview', background=[('selected', '#2563eb')])
    style.configure('oddrow.Treeview', background='#ffffff')
    style.configure('evenrow.Treeview', background='#e0f2fe')

    # Create frame for tree and scrollbars
    tree_frame = tk.Frame(table_card, bg=card_bg)
    tree_frame.grid(row=1, column=0, sticky="nsew")
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

    column_headings = {col: col.title() for col in columns}
    other_column_headings = {col: col.title() for col in other_columns}

    def configure_table_columns():
        selected_columns = other_columns if display_option_var.get() == "Option 2" else columns
        active_columns["columns"] = selected_columns
        tree.configure(columns=selected_columns)
        headings = other_column_headings if display_option_var.get() == "Option 2" else column_headings
        for col in selected_columns:
            tree.heading(col, text=headings[col])
            anchor = "w" if col in ("worker", "driver", "address", "item name", "delivery address", "delivery driver", "helper", "user") else "center"
            tree.column(col, anchor=anchor, width=130, minwidth=80, stretch=False)

    configure_table_columns()

    def auto_adjust_columns():
        tree.update_idletasks()
        heading_font = tkfont.Font(font=style.lookup("Treeview.Heading", "font"))
        row_font = tkfont.Font(font=style.lookup("Treeview", "font"))
        padding = {
            "id": 45,
            "transaction date": 55,
            "delivery date": 55,
            "worker": 65,
            "driver": 65,
            "address": 80,
            "blocks": 55,
            "delivery fee": 65,
            "total Salary": 70,
            "user": 65,
            "item name": 70,
            "quantity": 55,
            "unit of measurement": 75,
            "delivery address": 90,
            "delivery driver": 80,
            "helper": 65,
            "date": 55,
        }
        min_widths = {
            "id": 65,
            "transaction date": 150,
            "delivery date": 135,
            "worker": 120,
            "driver": 120,
            "address": 180,
            "blocks": 100,
            "delivery fee": 130,
            "total Salary": 140,
            "user": 120,
            "item name": 150,
            "quantity": 100,
            "unit of measurement": 155,
            "delivery address": 220,
            "delivery driver": 150,
            "helper": 130,
            "date": 175,
        }
        max_widths = {
            "id": 90,
            "transaction date": 190,
            "delivery date": 180,
            "worker": 220,
            "driver": 220,
            "address": 360,
            "blocks": 150,
            "delivery fee": 180,
            "total Salary": 190,
            "user": 240,
            "item name": 280,
            "quantity": 140,
            "unit of measurement": 220,
            "delivery address": 420,
            "delivery driver": 260,
            "helper": 240,
            "date": 220,
        }

        headings = other_column_headings if display_option_var.get() == "Option 2" else column_headings
        measured_widths = {}
        min_column_widths = {}
        for col in active_columns["columns"]:
            width = heading_font.measure(headings[col]) + padding[col]
            for item in tree.get_children():
                width = max(width, row_font.measure(str(tree.set(item, col))) + padding[col])
            width = max(min_widths[col], min(width, max_widths[col]))
            measured_widths[col] = width
            min_column_widths[col] = min_widths[col]

        if display_fullscreen.get():
            total_width = sum(measured_widths.values())
            available_width = max(tree.winfo_width() - 24, total_width)
            if available_width > total_width:
                selected_columns = list(active_columns["columns"])
                flexible_columns = [col for col in selected_columns if col != "id"]
                extra_width = available_width - total_width
                per_column = extra_width // len(flexible_columns)
                remainder = extra_width % len(flexible_columns)
                for index, col in enumerate(flexible_columns):
                    measured_widths[col] += per_column + (1 if index < remainder else 0)

        for col in active_columns["columns"]:
            tree.column(col, width=measured_widths[col], minwidth=min_column_widths[col], stretch=False)

    def update_total_delivered_today():
        total_delivered = 0
        if display_option_var.get() == "Option 2":
            value_index = 4
            label = "Total Other Items Delivered Today"
        else:
            value_index = 6
            label = "Total CHB Blocks Delivered Today"

        for item in tree.get_children():
            values = tree.item(item, "values")
            if len(values) <= value_index:
                continue
            try:
                total_delivered += int(str(values[value_index]).replace(",", "") or 0)
            except ValueError:
                continue

        total_delivered_var.set(f"{label}: {total_delivered:,}")

    # Bind to configure event to update scrollbar after column resize
    on_tree_configure = lambda event=None: delivery_functions.on_tree_configure(event, tree)

    tree.bind('<Configure>', on_tree_configure)

    # Configure tags for alternating row colors
    tree.tag_configure('oddrow', background='#ffffff', foreground='#000000')
    tree.tag_configure('evenrow', background='#93c5fd', foreground='#000000')

    def on_select(event):
        if display_option_var.get() == "Option 1":
            delivery_functions.on_select(event, tree, selected_id, transaction_date_var, date_var, worker_entry, driver_entry, address_entry, blocks_entry, delivery_fee_entry, auto_calc)
            return

        selected = tree.focus()
        values = tree.item(selected, "values")
        if values and values[0]:
            delivery_functions.open_other_items_form(delivery_win, conn, cursor, load_data, display_option_var, values)

    tree.bind("<ButtonRelease-1>", on_select)

    # ================= LOAD DATA =================
    def load_data(event=None):
        configure_table_columns()
        selected_id.set("")
        if display_option_var.get() == "Option 2":
            delivery_functions.load_other_items_data(event, cursor, tree, search_var, sort_var, delivery_win)
        else:
            delivery_functions.load_data(event, cursor, tree, search_var, sort_var, delivery_win)
        auto_adjust_columns()
        update_total_delivered_today()

    # BINDINGS (LIVE SEARCH)
    search_entry.bind("<KeyRelease>", load_data)
    sort_menu.bind("<<ComboboxSelected>>", load_data)

    # WINDOW CLOSE HANDLER
    delivery_win.protocol("WM_DELETE_WINDOW", lambda: delivery_functions.on_closing(conn, delivery_win))

    # INITIAL LOAD
    load_data()
