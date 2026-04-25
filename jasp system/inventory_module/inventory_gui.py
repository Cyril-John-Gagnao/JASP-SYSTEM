import tkinter as tk
from tkinter import ttk

from .inventory_database import open_inventory_connection, setup_inventory_database, ensure_chb_item, normalize_predefined_units
from . import inventory_functions
from .summary import open_inventory_summary

inventory_window = None
inventory_refresh_callback = None
inventory_refresh_job = None


def open_inventory():
    global inventory_window, inventory_refresh_callback, inventory_refresh_job
    if inventory_window and inventory_window.winfo_exists():
        inventory_window.focus()
        return

    conn, cursor = open_inventory_connection()
    setup_inventory_database(conn, cursor)
    ensure_chb_item(conn, cursor)
    normalize_predefined_units(conn, cursor)

    # ---------- GUI ----------
    inventory_window = tk.Toplevel()
    inventory_window.title("Inventory Management")
    inventory_window.state("zoomed")
    inventory_window.configure(bg="#f4f6f9")

    header_frame = tk.Frame(inventory_window, bg="#f4f6f9")
    header_frame.pack(fill="x", padx=30, pady=(15, 8))

    tk.Label(
        header_frame,
        text="Inventory Management",
        font=("Arial", 22, "bold"),
        bg="#f4f6f9",
        fg="#2563eb"
    ).pack(side="left")

    header_button_options = {
        "width": 10,
        "font": ("Arial", 10, "bold"),
        "bd": 2,
        "relief": "solid",
        "padx": 6,
        "pady": 5,
    }

    tk.Button(
        header_frame,
        text="Back",
        bg="#ffeb3b",
        fg="black",
        command=lambda: inventory_functions.back_to_main(__import__(__name__, fromlist=[''])),
        **header_button_options
    ).pack(side="right", padx=(6, 0))
    tk.Button(
        header_frame,
        text="Refresh",
        bg="#f59e0b",
        fg="white",
        command=lambda: refresh_view(),
        **header_button_options
    ).pack(side="right", padx=(6, 0))

    main_frame = tk.Frame(inventory_window, bg="#f4f6f9")
    main_frame.pack(fill="both", expand=True, padx=20, pady=10)

    # -------- Left Frame: Table + Search ----------
    left_frame = tk.Frame(main_frame, bg="#f4f6f9", padx=10, pady=10)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=5)

    controls_frame = tk.Frame(left_frame, bg="#f4f6f9")
    controls_frame.pack(fill="x", pady=(0, 4), anchor="n")

    tk.Label(controls_frame, text="Search by Name:", font=("Arial", 13, "bold"), bg="#f4f6f9").pack(side="left", padx=(0, 8))
    search_entry = tk.Entry(controls_frame, font=("Arial", 13), width=24)
    search_entry.pack(side="left", padx=(0, 14))

    tk.Label(controls_frame, text="Sort By:", font=("Arial", 13, "bold"), bg="#f4f6f9").pack(side="left", padx=(0, 8))
    sort_filter_var = tk.StringVar(value="Latest Date")
    sort_filter = ttk.Combobox(
        controls_frame,
        textvariable=sort_filter_var,
        values=["Name", "Latest Date"],
        state="readonly",
        width=14,
        font=("Arial", 12)
    )
    sort_filter.pack(side="left", padx=(0, 10))

    tk.Button(
        controls_frame,
        text="Summary",
        bg="#8b5cf6",
        fg="white",
        font=("Arial", 12, "bold"),
        bd=2,
        relief="solid",
        padx=14,
        pady=5,
        command=lambda: open_inventory_summary(inventory_window)
    ).pack(side="left")

    total_items_var = tk.StringVar(value="Total Items in Inventory: 0")
    tk.Label(left_frame, textvariable=total_items_var, font=("Arial", 14, "bold"), bg="#f4f6f9", fg="#1e40af").pack(anchor="w", pady=(4, 6))

    # ---------- CRUD Functions ----------
    sort_state = {"column": None, "ascending": True}

    tree_frame = tk.Frame(left_frame)
    tree_frame.pack(fill="both", expand=True, pady=10)

    columns = ("ID", "Name", "Unit", "Quantity", "Price", "Raw Price", "Status")
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
    v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    v_scroll.pack(side="right", fill="y")
    h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    h_scroll.pack(side="bottom", fill="x")
    tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
    tree.pack(fill="both", expand=True)

    style = ttk.Style()
    style.configure("Inventory.Treeview", font=("Arial", 12), rowheight=34)
    style.configure("Inventory.Treeview.Heading", font=("Arial", 13, "bold"))
    tree.configure(style="Inventory.Treeview")
    tree.tag_configure("blue_row", background="#93c5fd", foreground="#000000")
    tree.tag_configure("white_row", background="#ffffff", foreground="#000000")

    tree.heading("ID", text="ID", command=lambda: inventory_functions.sort_tree(tree, sort_state, "ID", numeric=True))
    tree.column("ID", width=70, anchor="center")
    tree.heading("Name", text="Name", command=lambda: inventory_functions.sort_tree(tree, sort_state, "Name", numeric=False))
    tree.column("Name", width=200, anchor="w")
    tree.heading("Unit", text="Unit of Measurement", command=lambda: inventory_functions.sort_tree(tree, sort_state, "Unit", numeric=False))
    tree.column("Unit", width=170, anchor="center")
    tree.heading("Quantity", text="Quantity", command=lambda: inventory_functions.sort_tree(tree, sort_state, "Quantity", numeric=True))
    tree.column("Quantity", width=100, anchor="center")
    tree.heading("Price", text="Unit Price", command=lambda: inventory_functions.sort_tree(tree, sort_state, "Price", numeric=True))
    tree.column("Price", width=120, anchor="e")
    tree.heading("Raw Price", text="Raw Price", command=lambda: inventory_functions.sort_tree(tree, sort_state, "Raw Price", numeric=True))
    tree.column("Raw Price", width=120, anchor="e")
    tree.heading("Status", text="Status", command=lambda: inventory_functions.sort_tree(tree, sort_state, "Status", numeric=False))
    tree.column("Status", width=100, anchor="center")

    status_labels = []

    def render_status_labels():
        for label in status_labels:
            label.destroy()
        status_labels.clear()

        tree.update_idletasks()
        for item in tree.get_children():
            bbox = tree.bbox(item, "Status")
            if not bbox:
                continue

            x, y, width, height = bbox
            status = tree.set(item, "Status") or "Active"
            is_active = status.lower() == "active"
            row_tags = tree.item(item, "tags")
            bg = "#93c5fd" if row_tags and row_tags[0] == "blue_row" else "#ffffff"
            fg = "#15803d" if is_active else "#dc2626"
            label = tk.Label(
                tree,
                text=status,
                bg=bg,
                fg=fg,
                font=("Arial", 12, "bold"),
                anchor="center"
            )
            label.place(x=x + 1, y=y + 1, width=width - 2, height=height - 2)

            def select_row(event, row_id=item):
                tree.selection_set(row_id)
                tree.focus(row_id)

            label.bind("<Button-1>", select_row)
            status_labels.append(label)

    def refresh_view():
        inventory_functions.refresh_current_view(conn, cursor, tree, search_entry, sort_filter_var, total_items_var)
        render_status_labels()

    def sort_and_render(column, numeric=False):
        inventory_functions.sort_tree(tree, sort_state, column, numeric=numeric)
        render_status_labels()

    tree.heading("ID", text="ID", command=lambda: sort_and_render("ID", numeric=True))
    tree.heading("Name", text="Name", command=lambda: sort_and_render("Name", numeric=False))
    tree.heading("Unit", text="Unit of Measurement", command=lambda: sort_and_render("Unit", numeric=False))
    tree.heading("Quantity", text="Quantity", command=lambda: sort_and_render("Quantity", numeric=True))
    tree.heading("Price", text="Unit Price", command=lambda: sort_and_render("Price", numeric=True))
    tree.heading("Raw Price", text="Raw Price", command=lambda: sort_and_render("Raw Price", numeric=True))
    tree.heading("Status", text="Status", command=lambda: sort_and_render("Status", numeric=False))

    v_scroll.config(command=lambda *args: (tree.yview(*args), render_status_labels()))
    h_scroll.config(command=lambda *args: (tree.xview(*args), render_status_labels()))
    tree.bind("<Configure>", lambda event: render_status_labels())
    tree.bind("<MouseWheel>", lambda event: tree.after_idle(render_status_labels))
    tree.bind("<ButtonRelease-1>", lambda event: tree.after_idle(render_status_labels))

    search_entry.bind("<KeyRelease>", lambda event: refresh_view())
    sort_filter.bind("<<ComboboxSelected>>", lambda event: refresh_view())
    inventory_refresh_callback = refresh_view

    # -------- Right Frame: Actions ----------
    right_frame = tk.Frame(main_frame, bg="white", padx=24, pady=24, bd=2, relief="groove")
    right_frame.pack(side="right", fill="both", padx=(10, 0), pady=5)

    # ---------- Buttons ----------
    button_options = {
        "width": 26,
        "font": ("Arial", 14, "bold"),
        "bd": 2,
        "relief": "solid",
        "highlightbackground": "black",
        "highlightcolor": "black",
        "highlightthickness": 1,
        "padx": 10,
        "pady": 14,
    }
    tk.Button(right_frame, text="Add Item", bg="#00c853", fg="white", command=lambda: inventory_functions.add_item(conn, cursor, inventory_window, tree, refresh_view), **button_options).grid(row=0, column=0, pady=14, padx=5)
    tk.Button(right_frame, text="Edit Item", bg="#2196f3", fg="white", command=lambda: inventory_functions.update_item(conn, cursor, inventory_window, tree, refresh_view), **button_options).grid(row=1, column=0, pady=14, padx=5)
    tk.Button(right_frame, text="Delete Item", bg="#ff1744", fg="white", command=lambda: inventory_functions.delete_item(conn, cursor, inventory_window, tree, refresh_view), **button_options).grid(row=2, column=0, pady=14, padx=5)

    inventory_window.protocol("WM_DELETE_WINDOW", lambda: inventory_functions.on_close(__import__(__name__, fromlist=[''])))
    refresh_view()
