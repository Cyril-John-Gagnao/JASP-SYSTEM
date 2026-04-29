import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .inventory_database import open_inventory_connection, setup_inventory_database, ensure_chb_item, ensure_chb_material_items, normalize_predefined_units
from . import inventory_functions
from .summary import open_inventory_summary

inventory_window = None
inventory_refresh_callback = None
inventory_refresh_job = None

CHB_SECTION_ITEMS = ("Cement", "Fine Sand", "CHB Blocks")


def open_inventory():
    global inventory_window, inventory_refresh_callback, inventory_refresh_job
    if inventory_window and inventory_window.winfo_exists():
        inventory_window.focus()
        return

    conn, cursor = open_inventory_connection()
    setup_inventory_database(conn, cursor)
    ensure_chb_item(conn, cursor)
    ensure_chb_material_items(conn, cursor)
    normalize_predefined_units(conn, cursor)

    # ---------- GUI ----------
    inventory_window = tk.Toplevel()
    inventory_window.title("Inventory Management")
    inventory_window.state("zoomed")
    inventory_window.configure(bg="#f4f6f9")
    inventory_window.option_add("*TCombobox*Listbox.font", ("Arial", 18))

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
        bg="#2563eb",
        fg="white",
        command=lambda: inventory_functions.back_to_main(__import__(__name__, fromlist=[''])),
        **header_button_options
    ).pack(side="right", padx=(6, 0))
    tk.Button(
        header_frame,
        text="Refresh",
        bg="#16a34a",
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

    tk.Label(controls_frame, text="Search by Item Name:", font=("Arial", 16, "bold"), bg="#f4f6f9").pack(side="left", padx=(0, 10))
    search_entry = tk.Entry(
        controls_frame,
        font=("Arial", 16),
        width=26,
        bd=2,
        relief="solid",
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black"
    )
    search_entry.pack(side="left", padx=(0, 14))

    tk.Label(controls_frame, text="Sort By:", font=("Arial", 16, "bold"), bg="#f4f6f9").pack(side="left", padx=(0, 10))
    sort_filter_var = tk.StringVar(value="Latest Date")
    sort_filter = ttk.Combobox(
        controls_frame,
        textvariable=sort_filter_var,
        values=["Item Name", "Latest Date"],
        state="readonly",
        width=15,
        font=("Arial", 18)
    )
    sort_filter.pack(side="left", padx=(0, 10))

    tk.Button(
        controls_frame,
        text="Summary",
        bg="#8b5cf6",
        fg="white",
        font=("Arial", 14, "bold"),
        bd=2,
        relief="solid",
        padx=16,
        pady=7,
        command=lambda: open_inventory_summary(inventory_window)
    ).pack(side="left")

    total_items_var = tk.StringVar(value="Total Items in Inventory: 0")
    tk.Label(left_frame, textvariable=total_items_var, font=("Arial", 14, "bold"), bg="#f4f6f9", fg="#1e40af").pack(anchor="w", pady=(4, 6))

    # ---------- CRUD Functions ----------
    sort_state = {"column": None, "ascending": True}

    content_frame = tk.Frame(left_frame, bg="#f4f6f9")
    content_frame.pack(fill="both", expand=True, pady=10)

    table_area = tk.Frame(content_frame, bg="#f4f6f9")
    table_area.pack(side="left", fill="both", expand=True, padx=(0, 10))

    chb_section = tk.Frame(
        table_area,
        bg="white",
        padx=8,
        pady=8,
        highlightthickness=2,
        highlightbackground="#1e3a8a",
        highlightcolor="#1e3a8a"
    )
    chb_section.pack(fill="x", pady=(0, 10))

    tk.Label(
        chb_section,
        text="CHB Items",
        font=("Arial", 18, "bold"),
        bg="white",
        fg="#1e40af"
    ).pack(anchor="w", pady=(0, 8))

    chb_tree_frame = tk.Frame(chb_section, bg="white")
    chb_tree_frame.pack(fill="x")

    lower_section = tk.Frame(
        table_area,
        bg="white",
        padx=8,
        pady=8,
        highlightthickness=2,
        highlightbackground="#111827",
        highlightcolor="#111827"
    )
    lower_section.pack(fill="both", expand=True)

    tk.Label(
        lower_section,
        text="Other Inventory Items",
        font=("Arial", 18, "bold"),
        bg="white",
        fg="#1e40af"
    ).pack(anchor="w", pady=(0, 8))

    tree_frame = tk.Frame(lower_section, bg="white")
    tree_frame.pack(fill="both", expand=True)

    # -------- Right Frame: Actions ----------
    right_frame = tk.Frame(content_frame, bg="white", padx=24, pady=24, bd=2, relief="groove")
    right_frame.pack(side="right", fill="y", padx=(10, 0))

    columns = ("ID", "Name", "Unit", "Quantity", "Price", "Raw Price", "Status")
    column_headings = {
        "ID": "ID",
        "Name": "Name",
        "Unit": "Unit of Measurement",
        "Quantity": "Quantity",
        "Price": "Selling Price",
        "Raw Price": "Raw Price",
        "Status": "Status",
    }
    chb_tree = ttk.Treeview(chb_tree_frame, columns=columns, show="headings", selectmode="browse", height=3)
    chb_v_scroll = ttk.Scrollbar(chb_tree_frame, orient="vertical", command=chb_tree.yview)
    chb_h_scroll = ttk.Scrollbar(chb_tree_frame, orient="horizontal", command=chb_tree.xview)
    chb_tree.configure(yscrollcommand=chb_v_scroll.set, xscrollcommand=chb_h_scroll.set)
    chb_tree.grid(row=0, column=0, sticky="nsew")
    chb_v_scroll.grid(row=0, column=1, sticky="ns")
    chb_h_scroll.grid(row=1, column=0, sticky="ew")
    tk.Frame(chb_tree_frame, bg="white", width=16, height=16).grid(row=1, column=1, sticky="nsew")
    chb_tree_frame.grid_columnconfigure(0, weight=1)
    chb_tree_frame.grid_rowconfigure(0, weight=1)

    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", selectmode="browse")
    v_scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=tree.yview)
    h_scroll = ttk.Scrollbar(tree_frame, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=v_scroll.set, xscrollcommand=h_scroll.set)
    tree.grid(row=0, column=0, sticky="nsew")
    v_scroll.grid(row=0, column=1, sticky="ns")
    h_scroll.grid(row=1, column=0, sticky="ew")
    tk.Frame(tree_frame, bg="white", width=16, height=16).grid(row=1, column=1, sticky="nsew")
    tree_frame.grid_columnconfigure(0, weight=1)
    tree_frame.grid_rowconfigure(0, weight=1)

    style = ttk.Style()
    style.configure("Inventory.Treeview", font=("Arial", 14), rowheight=40)
    style.configure("Inventory.Treeview.Heading", font=("Arial", 15, "bold"))
    chb_tree.configure(style="Inventory.Treeview")
    tree.configure(style="Inventory.Treeview")
    chb_tree.tag_configure("blue_row", background="#93c5fd", foreground="#000000")
    chb_tree.tag_configure("white_row", background="#ffffff", foreground="#000000")
    tree.tag_configure("blue_row", background="#93c5fd", foreground="#000000")
    tree.tag_configure("white_row", background="#ffffff", foreground="#000000")

    def configure_columns(target_tree):
        for column_id, heading_text in column_headings.items():
            anchor = "w" if column_id == "Name" else "e" if column_id in ("Price", "Raw Price") else "center"
            target_tree.heading(column_id, text=heading_text)
            target_tree.column(column_id, width=120, minwidth=80, anchor=anchor, stretch=False)

    configure_columns(chb_tree)
    configure_columns(tree)

    status_labels = []
    selected_action_tree = {"tree": tree}
    selection_syncing = {"active": False}

    def auto_adjust_columns(target_tree):
        target_tree.update_idletasks()
        heading_font = tkfont.Font(font=style.lookup("Inventory.Treeview.Heading", "font"))
        extra_padding = {
            "ID": 46,
            "Name": 70,
            "Unit": 58,
            "Quantity": 54,
            "Price": 54,
            "Raw Price": 54,
            "Status": 54,
        }

        for col in columns:
            heading_text = column_headings[col]
            width = heading_font.measure(heading_text) + extra_padding[col]
            target_tree.column(col, width=width, minwidth=width, stretch=False)

    def load_chb_items():
        for row in chb_tree.get_children():
            chb_tree.delete(row)

        placeholders = ", ".join("?" for _ in CHB_SECTION_ITEMS)
        cursor.execute(
            f"""
            SELECT id, name, unit, quantity, price, raw_price, COALESCE(status, 'Active')
            FROM items
            WHERE LOWER(name) IN ({placeholders})
            ORDER BY CASE LOWER(name)
                WHEN 'cement' THEN 1
                WHEN 'fine sand' THEN 2
                WHEN 'chb blocks' THEN 3
                ELSE 4
            END
            """,
            tuple(item_name.lower() for item_name in CHB_SECTION_ITEMS)
        )
        for index, row in enumerate(cursor.fetchall()):
            tag = "blue_row" if index % 2 == 0 else "white_row"
            chb_tree.insert("", tk.END, values=row, tags=(tag,))
        auto_adjust_columns(chb_tree)

    def remove_chb_items_from_main_table():
        chb_names = {name.lower() for name in CHB_SECTION_ITEMS}
        remaining_index = 0
        for item in list(tree.get_children()):
            values = tree.item(item, "values")
            item_name = values[1].lower() if len(values) > 1 else ""
            if item_name in chb_names:
                tree.delete(item)
                continue
            status = values[6] if len(values) > 6 else "Active"
            tree.item(item, tags=(inventory_functions.status_row_tag(remaining_index, status),))
            remaining_index += 1
        auto_adjust_columns(tree)

    def set_selected_action_tree(target_tree):
        if selection_syncing["active"]:
            return

        selection_syncing["active"] = True
        selected_action_tree["tree"] = target_tree
        if target_tree is chb_tree:
            tree.selection_remove(tree.selection())
            tree.focus("")
        else:
            chb_tree.selection_remove(chb_tree.selection())
            chb_tree.focus("")
        selection_syncing["active"] = False

    def render_status_labels():
        for label in status_labels:
            label.destroy()
        status_labels.clear()

        def render_tree_status_labels(target_tree):
            target_tree.update_idletasks()
            for item in target_tree.get_children():
                bbox = target_tree.bbox(item, "Status")
                if not bbox:
                    continue

                x, y, width, height = bbox
                status = target_tree.set(item, "Status") or "Active"
                is_active = status.lower() == "active"
                row_tags = target_tree.item(item, "tags")
                bg = "#93c5fd" if row_tags and row_tags[0] == "blue_row" else "#ffffff"
                fg = "#15803d" if is_active else "#dc2626"
                label = tk.Label(
                    target_tree,
                    text=status,
                    bg=bg,
                    fg=fg,
                    font=("Arial", 14, "bold"),
                    anchor="center"
                )
                label.place(x=x + 1, y=y + 1, width=width - 2, height=height - 2)

                def select_row(event, row_id=item, selected_tree=target_tree):
                    selected_tree.selection_set(row_id)
                    selected_tree.focus(row_id)
                    set_selected_action_tree(selected_tree)

                label.bind("<Button-1>", select_row)
                status_labels.append(label)

        render_tree_status_labels(chb_tree)
        render_tree_status_labels(tree)

    def refresh_view():
        inventory_functions.refresh_current_view(conn, cursor, tree, search_entry, sort_filter_var, total_items_var)
        remove_chb_items_from_main_table()
        load_chb_items()
        render_status_labels()

    def sort_and_render(column, numeric=False):
        inventory_functions.sort_tree(tree, sort_state, column, numeric=numeric)
        remove_chb_items_from_main_table()
        render_status_labels()

    tree.heading("ID", text="ID", command=lambda: sort_and_render("ID", numeric=True))
    tree.heading("Name", text="Name", command=lambda: sort_and_render("Name", numeric=False))
    tree.heading("Unit", text="Unit of Measurement", command=lambda: sort_and_render("Unit", numeric=False))
    tree.heading("Quantity", text="Quantity", command=lambda: sort_and_render("Quantity", numeric=True))
    tree.heading("Price", text="Selling Price", command=lambda: sort_and_render("Price", numeric=True))
    tree.heading("Raw Price", text="Raw Price", command=lambda: sort_and_render("Raw Price", numeric=True))
    tree.heading("Status", text="Status", command=lambda: sort_and_render("Status", numeric=False))

    v_scroll.config(command=lambda *args: (tree.yview(*args), render_status_labels()))
    h_scroll.config(command=lambda *args: (tree.xview(*args), render_status_labels()))
    tree.bind("<Configure>", lambda event: render_status_labels())
    tree.bind("<MouseWheel>", lambda event: tree.after_idle(render_status_labels))
    tree.bind("<ButtonRelease-1>", lambda event: tree.after_idle(render_status_labels))
    chb_tree.bind("<Configure>", lambda event: render_status_labels())
    chb_tree.bind("<ButtonRelease-1>", lambda event: chb_tree.after_idle(render_status_labels))
    tree.bind("<<TreeviewSelect>>", lambda event: set_selected_action_tree(tree))
    chb_tree.bind("<<TreeviewSelect>>", lambda event: set_selected_action_tree(chb_tree))

    search_entry.bind("<KeyRelease>", lambda event: refresh_view())
    sort_filter.bind("<<ComboboxSelected>>", lambda event: refresh_view())
    inventory_refresh_callback = refresh_view

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
    tk.Button(right_frame, text="Edit Item", bg="#2196f3", fg="white", command=lambda: inventory_functions.update_item(conn, cursor, inventory_window, selected_action_tree["tree"], refresh_view), **button_options).grid(row=1, column=0, pady=14, padx=5)
    tk.Button(right_frame, text="Delete Item", bg="#ff1744", fg="white", command=lambda: inventory_functions.delete_item(conn, cursor, inventory_window, selected_action_tree["tree"], refresh_view), **button_options).grid(row=2, column=0, pady=14, padx=5)

    inventory_window.protocol("WM_DELETE_WINDOW", lambda: inventory_functions.on_close(__import__(__name__, fromlist=[''])))
    refresh_view()
