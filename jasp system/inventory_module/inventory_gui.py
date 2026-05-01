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


def open_inventory(parent=None):
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
    if parent is not None and parent.winfo_exists():
        inventory_window = tk.Toplevel(parent)
    else:
        inventory_window = tk.Toplevel()
    inventory_window.title("Inventory Management")
    inventory_window.state("zoomed")
    inventory_window.configure(bg="#f4f6f9")
    inventory_window.option_add("*TCombobox*Listbox.font", ("Arial", 18))

    header_frame = tk.Frame(inventory_window, bg="#dbeafe", padx=14, pady=10, highlightthickness=1, highlightbackground="#93c5fd")
    header_frame.pack(fill="x", padx=30, pady=(15, 8))

    tk.Label(
        header_frame,
        text="INVENTORY MANAGEMENT",
        font=("Arial", 22, "bold"),
        bg="#dbeafe",
        fg="#2563eb",
        padx=12,
        pady=4
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
        command=lambda: close_inventory_window(),
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

    stock_counts_frame = tk.Frame(left_frame, bg="#f4f6f9")
    stock_counts_frame.pack(anchor="w", pady=(6, 8))

    total_items_var = tk.StringVar(value="Total Items in Inventory: 0")
    low_stock_var = tk.StringVar(value="Low Stock Items: 0")
    tk.Label(stock_counts_frame, textvariable=total_items_var, font=("Arial", 18, "bold"), bg="#f4f6f9", fg="#1e40af").pack(side="left")
    tk.Label(stock_counts_frame, textvariable=low_stock_var, font=("Arial", 18, "bold"), bg="#f4f6f9", fg="#c2410c").pack(side="left", padx=(28, 0))

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
    right_frame = tk.Frame(
        content_frame,
        bg="#dbeafe",
        padx=14,
        pady=20,
        bd=0,
        relief="flat",
        highlightthickness=0
    )
    right_frame.pack(side="right", fill="y", padx=(10, 0))

    columns = ("ID", "Name", "Unit", "Quantity", "Price", "Raw Price", "Status", "Restock")
    column_headings = {
        "ID": "ID",
        "Name": "Name",
        "Unit": "Unit of Measurement",
        "Quantity": "Quantity",
        "Price": "Selling Price",
        "Raw Price": "Raw Price",
        "Status": "Status",
        "Restock": "Restock",
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
    chb_tree.tag_configure(inventory_functions.LOW_STOCK_ROW, background="#fed7aa", foreground="#000000")
    tree.tag_configure("blue_row", background="#93c5fd", foreground="#000000")
    tree.tag_configure("white_row", background="#ffffff", foreground="#000000")
    tree.tag_configure(inventory_functions.LOW_STOCK_ROW, background="#fed7aa", foreground="#000000")

    def configure_columns(target_tree):
        for column_id, heading_text in column_headings.items():
            anchor = "w" if column_id == "Name" else "e" if column_id in ("Price", "Raw Price") else "center"
            target_tree.heading(column_id, text=heading_text)
            target_tree.column(column_id, width=120, minwidth=80, anchor=anchor, stretch=False)

    configure_columns(chb_tree)
    configure_columns(tree)

    overlay_widgets = {}
    status_render_job = {"id": None}
    status_rendering = {"active": False}
    selected_action_tree = {"tree": tree}
    selection_syncing = {"active": False}

    def close_inventory_window():
        global inventory_window, inventory_refresh_callback, inventory_refresh_job
        window = inventory_window
        parent_window = window.master if window and window.winfo_exists() else parent

        inventory_refresh_callback = None
        inventory_refresh_job = None

        if status_render_job["id"] is not None and window and window.winfo_exists():
            try:
                window.after_cancel(status_render_job["id"])
            except Exception:
                pass
            status_render_job["id"] = None

        clear_status_labels()

        if window and window.winfo_exists():
            try:
                window.withdraw()
            except Exception:
                pass
            try:
                window.destroy()
            except Exception:
                pass
        inventory_window = None

        try:
            conn.close()
        except Exception:
            pass

        if parent_window and parent_window.winfo_exists():
            try:
                parent_window.deiconify()
                parent_window.lift()
                parent_window.focus_force()
            except Exception:
                pass

    def auto_adjust_columns(target_tree):
        clear_status_labels()
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
            "Restock": 42,
        }

        for col in columns:
            heading_text = column_headings[col]
            width = heading_font.measure(heading_text) + extra_padding[col]
            target_tree.column(col, width=width, minwidth=width, stretch=False)

    def clear_status_labels():
        for widget in overlay_widgets.values():
            if widget.winfo_exists():
                widget.destroy()
        overlay_widgets.clear()

    def schedule_status_labels(target_tree=None):
        if status_rendering["active"]:
            return

        if status_render_job["id"] is not None:
            inventory_window.after_cancel(status_render_job["id"])

        parent = target_tree if target_tree is not None else inventory_window
        status_render_job["id"] = parent.after_idle(render_status_labels)

    def open_restock_target(row_values):
        if row_values and len(row_values) > 1 and str(row_values[1]).strip().lower() == "chb blocks":
            try:
                from chb_module.gui import open_chb_dashboard
            except Exception:
                inventory_functions.show_inventory_error(
                    inventory_window,
                    "Error",
                    "Unable to open the CHB Production form."
                )
                return

            close_inventory_window()
            open_chb_dashboard()
            return

        inventory_functions.open_restock_form(conn, cursor, inventory_window, row_values, refresh_view)

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
            tag = inventory_functions.inventory_row_tag(index, row)
            chb_tree.insert("", tk.END, values=row + ("",), tags=(tag,))
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
            tree.item(item, tags=(inventory_functions.status_row_tag(remaining_index, status, values[1], values[3]),))
            remaining_index += 1
        auto_adjust_columns(tree)

    def update_low_stock_count():
        low_stock_count = 0
        for target_tree in (chb_tree, tree):
            for item in target_tree.get_children():
                values = target_tree.item(item, "values")
                item_name = values[1] if len(values) > 1 else ""
                quantity = values[3] if len(values) > 3 else 0
                if inventory_functions.is_low_stock_item(item_name, quantity):
                    low_stock_count += 1
        low_stock_var.set(f"Low Stock Items: {low_stock_count:,}")

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
        status_render_job["id"] = None
        status_rendering["active"] = True
        try:
            visible_keys = set()

            def render_tree_status_labels(target_tree):
                target_tree.update_idletasks()
                for item in target_tree.get_children():
                    name_bbox = target_tree.bbox(item, "Name")
                    status_bbox = target_tree.bbox(item, "Status")
                    restock_bbox = target_tree.bbox(item, "Restock")
                    values = target_tree.item(item, "values")
                    item_name = values[1] if len(values) > 1 else ""
                    quantity = values[3] if len(values) > 3 else 0
                    status = target_tree.set(item, "Status") or "Active"
                    is_active = status.lower() == "active"
                    is_low_stock = inventory_functions.is_low_stock_item(item_name, quantity)
                    row_tags = target_tree.item(item, "tags")
                    if row_tags and row_tags[0] == inventory_functions.LOW_STOCK_ROW:
                        bg = "#fed7aa"
                    else:
                        bg = "#93c5fd" if row_tags and row_tags[0] == "blue_row" else "#ffffff"
                    fg = "#15803d" if is_active else "#dc2626"

                    def select_row(event, row_id=item, selected_tree=target_tree):
                        selected_tree.selection_set(row_id)
                        selected_tree.focus(row_id)
                        set_selected_action_tree(selected_tree)

                    if name_bbox and is_low_stock:
                        x, y, width, height = name_bbox
                        icon = tk.Label(
                            target_tree,
                            text="⚠",
                            bg=bg,
                            fg="#c2410c",
                            font=("Arial", 14, "bold"),
                            anchor="center"
                        )
                        icon.place(x=x + max(width - 30, 4), y=y + 1, width=26, height=height - 2)
                        icon.bind("<Button-1>", select_row)
                        status_labels.append(icon)

                    if status_bbox:
                        x, y, width, height = status_bbox
                        label = tk.Label(
                            target_tree,
                            text=status,
                            bg=bg,
                            fg=fg,
                            font=("Arial", 14, "bold"),
                            anchor="center"
                        )
                        label.place(x=x + 1, y=y + 1, width=width - 2, height=height - 2)
                        label.bind("<Button-1>", select_row)
                        status_labels.append(label)

                    if restock_bbox:
                        x, y, width, height = restock_bbox
                        can_restock = status.lower() == "active"
                        button = tk.Button(
                            target_tree,
                            text="Restock",
                            bg="#16a34a" if can_restock else "#9ca3af",
                            fg="white",
                            activebackground="#15803d",
                            font=("Arial", 10, "bold"),
                            relief="solid",
                            bd=1,
                            cursor="hand2" if can_restock else "arrow",
                            state="normal" if can_restock else "disabled",
                            command=lambda row_values=values, selected_tree=target_tree, row_id=item: (
                                selected_tree.selection_set(row_id),
                                selected_tree.focus(row_id),
                                set_selected_action_tree(selected_tree),
                                open_restock_target(row_values)
                            )
                        )
                        button.place(x=x + 4, y=y + 5, width=max(width - 8, 70), height=max(height - 10, 28))
                        status_labels.append(button)

            render_tree_status_labels(chb_tree)
            render_tree_status_labels(tree)
        finally:
            status_rendering["active"] = False

    def render_status_labels():
        global inventory_refresh_job
        if not inventory_window or not inventory_window.winfo_exists():
            return
        status_render_job["id"] = None
        inventory_refresh_job = None
        status_rendering["active"] = True
        try:
            visible_keys = set()

            def select_row(target_tree, row_id):
                target_tree.selection_set(row_id)
                target_tree.focus(row_id)
                set_selected_action_tree(target_tree)

            def get_row_bg(target_tree, item):
                row_tags = target_tree.item(item, "tags")
                if row_tags and row_tags[0] == inventory_functions.LOW_STOCK_ROW:
                    return "#fed7aa"
                return "#93c5fd" if row_tags and row_tags[0] == "blue_row" else "#ffffff"

            def get_overlay(target_tree, item, kind, factory):
                key = (str(target_tree), item, kind)
                visible_keys.add(key)
                widget = overlay_widgets.get(key)
                if widget is None or not widget.winfo_exists():
                    widget = factory()
                    overlay_widgets[key] = widget
                return widget

            def render_tree_overlays(target_tree):
                target_tree.update_idletasks()
                for item in target_tree.get_children():
                    values = target_tree.item(item, "values")
                    item_name = values[1] if len(values) > 1 else ""
                    quantity = values[3] if len(values) > 3 else 0
                    status = target_tree.set(item, "Status") or "Active"
                    bg = get_row_bg(target_tree, item)
                    fg = "#15803d" if status.lower() == "active" else "#dc2626"

                    name_bbox = target_tree.bbox(item, "Name")
                    if name_bbox and inventory_functions.is_low_stock_item(item_name, quantity):
                        x, y, width, height = name_bbox
                        icon = get_overlay(
                            target_tree,
                            item,
                            "low_stock",
                            lambda: tk.Label(target_tree, text="!", font=("Arial", 14, "bold"), anchor="center")
                        )
                        icon.configure(bg=bg, fg="#c2410c")
                        icon.bind("<Button-1>", lambda _event, t=target_tree, row=item: select_row(t, row))
                        icon.place(x=x + max(width - 30, 4), y=y + 1, width=26, height=height - 2)

                    status_bbox = target_tree.bbox(item, "Status")
                    if status_bbox:
                        x, y, width, height = status_bbox
                        label = get_overlay(
                            target_tree,
                            item,
                            "status",
                            lambda: tk.Label(target_tree, font=("Arial", 14, "bold"), anchor="center")
                        )
                        label.configure(text=status, bg=bg, fg=fg)
                        label.bind("<Button-1>", lambda _event, t=target_tree, row=item: select_row(t, row))
                        label.place(x=x + 1, y=y + 1, width=width - 2, height=height - 2)

                    restock_bbox = target_tree.bbox(item, "Restock")
                    if restock_bbox:
                        x, y, width, height = restock_bbox
                        can_restock = status.lower() == "active"
                        button = get_overlay(
                            target_tree,
                            item,
                            "restock",
                            lambda: tk.Button(
                                target_tree,
                                text="Restock",
                                fg="white",
                                activebackground="#15803d",
                                font=("Arial", 10, "bold"),
                                relief="solid",
                                bd=1
                            )
                        )
                        button.configure(
                            bg="#16a34a" if can_restock else "#9ca3af",
                            cursor="hand2" if can_restock else "arrow",
                            state="normal" if can_restock else "disabled",
                            command=lambda row_values=values, selected_tree=target_tree, row_id=item: (
                                select_row(selected_tree, row_id),
                                open_restock_target(row_values)
                            )
                        )
                        button.place(x=x + 4, y=y + 5, width=max(width - 8, 70), height=max(height - 10, 28))

            render_tree_overlays(chb_tree)
            render_tree_overlays(tree)

            for key, widget in overlay_widgets.items():
                if key not in visible_keys and widget.winfo_exists():
                    widget.place_forget()
        finally:
            status_rendering["active"] = False

    def refresh_view():
        inventory_functions.refresh_current_view(conn, cursor, tree, search_entry, sort_filter_var, total_items_var)
        remove_chb_items_from_main_table()
        load_chb_items()
        update_low_stock_count()
        schedule_status_labels()

    def sort_and_render(column, numeric=False):
        inventory_functions.sort_tree(tree, sort_state, column, numeric=numeric)
        remove_chb_items_from_main_table()
        schedule_status_labels()

    tree.heading("ID", text="ID", command=lambda: sort_and_render("ID", numeric=True))
    tree.heading("Name", text="Name", command=lambda: sort_and_render("Name", numeric=False))
    tree.heading("Unit", text="Unit of Measurement", command=lambda: sort_and_render("Unit", numeric=False))
    tree.heading("Quantity", text="Quantity", command=lambda: sort_and_render("Quantity", numeric=True))
    tree.heading("Price", text="Selling Price", command=lambda: sort_and_render("Price", numeric=True))
    tree.heading("Raw Price", text="Raw Price", command=lambda: sort_and_render("Raw Price", numeric=True))
    tree.heading("Status", text="Status", command=lambda: sort_and_render("Status", numeric=False))
    tree.heading("Restock", text="Restock")

    v_scroll.config(command=lambda *args: (tree.yview(*args), schedule_status_labels(tree)))
    h_scroll.config(command=lambda *args: (tree.xview(*args), schedule_status_labels(tree)))
    chb_v_scroll.config(command=lambda *args: (chb_tree.yview(*args), schedule_status_labels(chb_tree)))
    chb_h_scroll.config(command=lambda *args: (chb_tree.xview(*args), schedule_status_labels(chb_tree)))
    tree.configure(
        yscrollcommand=lambda *args: (v_scroll.set(*args), schedule_status_labels(tree)),
        xscrollcommand=lambda *args: (h_scroll.set(*args), schedule_status_labels(tree))
    )
    chb_tree.configure(
        yscrollcommand=lambda *args: (chb_v_scroll.set(*args), schedule_status_labels(chb_tree)),
        xscrollcommand=lambda *args: (chb_h_scroll.set(*args), schedule_status_labels(chb_tree))
    )
    tree.bind("<Configure>", lambda event: schedule_status_labels(tree))
    tree.bind("<MouseWheel>", lambda event: schedule_status_labels(tree))
    tree.bind("<B1-Motion>", lambda event: schedule_status_labels(tree))
    tree.bind("<ButtonRelease-1>", lambda event: schedule_status_labels(tree))
    chb_tree.bind("<Configure>", lambda event: schedule_status_labels(chb_tree))
    chb_tree.bind("<MouseWheel>", lambda event: schedule_status_labels(chb_tree))
    chb_tree.bind("<B1-Motion>", lambda event: schedule_status_labels(chb_tree))
    chb_tree.bind("<ButtonRelease-1>", lambda event: schedule_status_labels(chb_tree))
    tree.bind("<<TreeviewSelect>>", lambda event: set_selected_action_tree(tree))
    chb_tree.bind("<<TreeviewSelect>>", lambda event: set_selected_action_tree(chb_tree))

    search_entry.bind("<KeyRelease>", lambda event: refresh_view())
    sort_filter.bind("<<ComboboxSelected>>", lambda event: refresh_view())
    inventory_refresh_callback = refresh_view

    # ---------- Buttons ----------
    button_options = {
        "width": 21,
        "font": ("Arial", 13, "bold"),
        "bd": 2,
        "relief": "solid",
        "highlightbackground": "black",
        "highlightcolor": "black",
        "highlightthickness": 1,
        "padx": 8,
        "pady": 12,
    }
    tk.Button(right_frame, text="Add Item", bg="#00c853", fg="white", command=lambda: inventory_functions.add_item(conn, cursor, inventory_window, tree, refresh_view), **button_options).grid(row=0, column=0, pady=12, padx=4)
    tk.Button(right_frame, text="Edit Item", bg="#2196f3", fg="white", command=lambda: inventory_functions.update_item(conn, cursor, inventory_window, selected_action_tree["tree"], refresh_view), **button_options).grid(row=1, column=0, pady=12, padx=4)
    tk.Button(right_frame, text="Delete Item", bg="#ff1744", fg="white", command=lambda: inventory_functions.delete_item(conn, cursor, inventory_window, selected_action_tree["tree"], refresh_view), **button_options).grid(row=2, column=0, pady=12, padx=4)

    inventory_window.protocol("WM_DELETE_WINDOW", close_inventory_window)
    refresh_view()
