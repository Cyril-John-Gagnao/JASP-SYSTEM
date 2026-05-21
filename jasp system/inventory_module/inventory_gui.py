import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk

from .inventory_database import open_inventory_connection, setup_inventory_database, ensure_chb_item, ensure_chb_material_items, normalize_predefined_units
from . import inventory_functions
from .summary import open_inventory_summary
from main_dashboard.navigation_menu import create_hamburger_menu
from jasp_theme import (
    DASHBOARD_CONTENT_BG,
    DASHBOARD_HEADER_BG,
    DASHBOARD_HEADER_BORDER,
    DASHBOARD_HEADER_FG,
    add_header_logo,
)

inventory_window = None
inventory_refresh_callback = None
inventory_refresh_job = None

# Keep CHB-related inventory items grouped in their own section.
CHB_SECTION_ITEMS = ("Cement", "Fine Sand", "CHB Blocks")


def open_inventory(parent=None):
    # Reuse the existing inventory window if it is already open.
    global inventory_window, inventory_refresh_callback, inventory_refresh_job
    if inventory_window and inventory_window.winfo_exists():
        inventory_window.focus()
        return

    # Open the inventory database connection and ensure required records exist.
    conn, cursor = open_inventory_connection()
    setup_inventory_database(conn, cursor)
    ensure_chb_item(conn, cursor)
    ensure_chb_material_items(conn, cursor)
    normalize_predefined_units(conn, cursor)

    # ---------- GUI ----------
    # Create the main inventory window.
    if parent is not None and parent.winfo_exists():
        inventory_window = tk.Toplevel(parent)
    else:
        inventory_window = tk.Toplevel()
    inventory_window.title("Inventory Management")
    inventory_window.state("zoomed")
    inventory_window.configure(bg=DASHBOARD_CONTENT_BG)
    inventory_window.option_add("*TCombobox*Listbox.font", ("Arial", 18))

    # Build the header with logo, title, refresh, and back actions.
    header_frame = tk.Frame(inventory_window, bg=DASHBOARD_HEADER_BG, padx=14, pady=10, highlightthickness=1, highlightbackground=DASHBOARD_HEADER_BORDER)
    header_frame.pack(fill="x", padx=30, pady=(15, 8))

    title_frame = tk.Frame(header_frame, bg=DASHBOARD_HEADER_BG)
    title_frame.pack(side="left")
    add_header_logo(title_frame, DASHBOARD_HEADER_BG, size=52)

    tk.Label(
        title_frame,
        text="INVENTORY MANAGEMENT",
        font=("Arial", 22, "bold"),
        bg=DASHBOARD_HEADER_BG,
        fg=DASHBOARD_HEADER_FG,
        padx=12,
        pady=4
    ).pack(side="left")
    create_hamburger_menu(header_frame, inventory_window, parent, lambda: close_inventory_window(), pack_side=tk.LEFT, pack_padx=(14, 6))

    # Reuse header button styling for Back and Refresh.
    header_button_options = {
        "width": 12,
        "font": ("Arial", 13, "bold"),
        "bd": 2,
        "relief": "solid",
        "padx": 10,
        "pady": 7,
    }

    tk.Button(
        header_frame,
        text="← Back",
        bg="#2563eb",
        fg="white",
        command=lambda: close_inventory_window(),
        **header_button_options
    ).pack(side="right", padx=(6, 0))
    tk.Button(
        header_frame,
        text="🔄 Refresh",
        bg="#16a34a",
        fg="white",
        command=lambda: refresh_view(),
        **header_button_options
    ).pack(side="right", padx=(6, 0))
    main_frame = tk.Frame(inventory_window, bg=DASHBOARD_CONTENT_BG)
    main_frame.pack(fill="both", expand=True, padx=20, pady=10)

    # -------- Left Frame: Table + Search ----------
    # Build the main left area for search, stock counts, and tables.
    left_frame = tk.Frame(main_frame, bg=DASHBOARD_CONTENT_BG, padx=10, pady=10)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 10), pady=5)

    # Build search, sort, and summary controls.
    controls_frame = tk.Frame(left_frame, bg=DASHBOARD_CONTENT_BG)
    controls_frame.pack(fill="x", pady=(0, 4), anchor="n")

    tk.Label(controls_frame, text="Search by Item Name:", font=("Arial", 16, "bold"), bg=DASHBOARD_CONTENT_BG).pack(side="left", padx=(0, 10))
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

    tk.Label(controls_frame, text="Sort By:", font=("Arial", 16, "bold"), bg=DASHBOARD_CONTENT_BG).pack(side="left", padx=(0, 10))
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
        font=("Arial", 13, "bold"),
        bd=2,
        relief="solid",
        padx=14,
        pady=3,
        command=lambda: open_inventory_summary(inventory_window, left_frame)
    ).pack(side="left")

    # Show total inventory count and low-stock controls.
    stock_counts_frame = tk.Frame(left_frame, bg=DASHBOARD_CONTENT_BG)
    stock_counts_frame.pack(anchor="w", pady=(6, 8))

    total_items_var = tk.StringVar(value="Total Items in Inventory: 0")
    low_stock_var = tk.StringVar(value="Low Stock Items: 0")
    tk.Label(stock_counts_frame, textvariable=total_items_var, font=("Arial", 18, "bold"), bg=DASHBOARD_CONTENT_BG, fg="#1e40af").pack(side="left")
    tk.Button(
        stock_counts_frame,
        textvariable=low_stock_var,
        font=("Arial", 13, "bold"),
        bg="#fed7aa",
        fg="#9a3412",
        activebackground="#fdba74",
        activeforeground="#7c2d12",
        cursor="hand2",
        bd=2,
        relief="solid",
        padx=10,
        pady=2,
        command=lambda: show_low_stock_items()
    ).pack(side="left", padx=(28, 0))
    tk.Button(
        stock_counts_frame,
        text="Show All Items",
        font=("Arial", 12, "bold"),
        bg="#16a34a",
        fg="white",
        activebackground="#15803d",
        activeforeground="white",
        cursor="hand2",
        bd=2,
        relief="solid",
        padx=10,
        pady=4,
        command=lambda: show_all_items()
    ).pack(side="left", padx=(10, 0))

    fullscreen_btn = tk.Button(
        stock_counts_frame,
        text="Full Screen Display",
        font=("Arial", 12, "bold"),
        bg="#0f766e",
        fg="white",
        activebackground="#0f766e",
        activeforeground="white",
        cursor="hand2",
        bd=2,
        relief="solid",
        padx=10,
        pady=4,
        command=lambda: toggle_display_fullscreen()
    )
    fullscreen_btn.pack(side="right", padx=(10, 0))

    # ---------- CRUD Functions ----------
    # Track sorting and low-stock filter state for the table.
    sort_state = {"column": None, "ascending": True}
    low_stock_filter = {"active": False}

    # Split the content between tables and the right action panel.
    content_frame = tk.Frame(left_frame, bg=DASHBOARD_CONTENT_BG)
    content_frame.pack(fill="both", expand=True, pady=10)

    table_area = tk.Frame(content_frame, bg=DASHBOARD_CONTENT_BG)

    # Build the separate CHB inventory section.
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

    chb_header = tk.Frame(chb_section, bg="white")
    chb_header.pack(fill="x", pady=(0, 8))

    tk.Label(
        chb_header,
        text="CHB Items",
        font=("Arial", 18, "bold"),
        bg="white",
        fg="#1e40af"
    ).pack(side="left")

    chb_items_count_var = tk.StringVar(value="Total: 0")
    tk.Label(
        chb_header,
        textvariable=chb_items_count_var,
        font=("Arial", 14, "bold"),
        bg="white",
        fg="#15803d"
    ).pack(side="left", padx=(14, 0))

    chb_tree_frame = tk.Frame(chb_section, bg="white")
    chb_tree_frame.pack(fill="x")

    # Build the lower section for all other inventory items.
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

    other_header = tk.Frame(lower_section, bg="white")
    other_header.pack(fill="x", pady=(0, 8))

    tk.Label(
        other_header,
        text="Other Inventory Items",
        font=("Arial", 18, "bold"),
        bg="white",
        fg="#1e40af"
    ).pack(side="left")

    other_items_count_var = tk.StringVar(value="Total: 0")
    tk.Label(
        other_header,
        textvariable=other_items_count_var,
        font=("Arial", 14, "bold"),
        bg="white",
        fg="#15803d"
    ).pack(side="left", padx=(14, 0))

    other_items_fullscreen = tk.BooleanVar(value=False)

    def toggle_other_items_fullscreen():
        # Toggle the Other Inventory Items section into fullscreen mode.
        clear_status_labels()
        if other_items_fullscreen.get():
            table_area.pack_forget()
            right_frame.pack_forget()
            right_frame.pack(side="right", fill="y", padx=(10, 0))
            table_area.pack(side="left", fill="both", expand=True, padx=(0, 10))
            lower_section.pack_forget()
            chb_section.pack(fill="x", pady=(0, 10))
            lower_section.pack(fill="both", expand=True)
            other_fullscreen_btn.config(text="Full Screen", bg="#0f766e", activebackground="#0f766e")
            other_items_fullscreen.set(False)
        else:
            if display_fullscreen.get():
                restore_normal_inventory_layout()
                fullscreen_btn.config(text="Full Screen Display", bg="#0f766e", activebackground="#0f766e")
                display_fullscreen.set(False)
            chb_section.pack_forget()
            table_area.pack_forget()
            right_frame.pack_forget()
            table_area.pack(side="left", fill="both", expand=True, padx=0)
            lower_section.pack_configure(fill="both", expand=True)
            other_fullscreen_btn.config(text="Exit Full Screen", bg="#334155", activebackground="#334155")
            other_items_fullscreen.set(True)
        inventory_window.after(50, lambda: (auto_adjust_columns(tree), schedule_status_labels(tree)))

    other_fullscreen_btn = tk.Button(
        other_header,
        text="Full Screen",
        font=("Arial", 11, "bold"),
        bg="#0f766e",
        fg="white",
        activebackground="#0f766e",
        activeforeground="white",
        cursor="hand2",
        bd=2,
        relief="solid",
        padx=10,
        pady=4,
        command=lambda: toggle_other_items_fullscreen()
    )
    other_fullscreen_btn.pack(side="right")

    tree_frame = tk.Frame(lower_section, bg="white")
    tree_frame.pack(fill="both", expand=True)

    # -------- Right Frame: Actions ----------
    # Build the fixed action panel for add, edit, and delete.
    right_frame = tk.Frame(
        content_frame,
        bg="#dbeafe",
        padx=14,
        pady=20,
        bd=0,
        relief="flat",
        highlightthickness=0
    )
    right_frame.configure(width=294)
    right_frame.pack_propagate(False)
    right_frame.grid_propagate(False)
    right_frame.grid_columnconfigure(0, weight=1)
    right_frame.pack(side="right", fill="y", padx=(10, 0))
    table_area.pack(side="left", fill="both", expand=True, padx=(0, 10))

    display_fullscreen = tk.BooleanVar(value=False)

    def restore_normal_inventory_layout():
        # Restore the normal split layout with tables and action panel.
        clear_status_labels()
        table_area.pack_forget()
        right_frame.pack_forget()
        right_frame.pack(side="right", fill="y", padx=(10, 0))
        table_area.pack(side="left", fill="both", expand=True, padx=(0, 10))
        right_frame.lift()
        inventory_window.update_idletasks()

    def toggle_display_fullscreen():
        # Toggle the whole inventory table area into fullscreen mode.
        clear_status_labels()
        if display_fullscreen.get():
            restore_normal_inventory_layout()
            fullscreen_btn.config(text="Full Screen Display", bg="#0f766e", activebackground="#0f766e")
            display_fullscreen.set(False)
        else:
            if other_items_fullscreen.get():
                lower_section.pack_forget()
                chb_section.pack(fill="x", pady=(0, 10))
                lower_section.pack(fill="both", expand=True)
                other_fullscreen_btn.config(text="Full Screen", bg="#0f766e", activebackground="#0f766e")
                other_items_fullscreen.set(False)
            table_area.pack_forget()
            right_frame.pack_forget()
            table_area.pack(side="left", fill="both", expand=True, padx=0)
            fullscreen_btn.config(text="Exit Full Screen", bg="#334155", activebackground="#334155")
            display_fullscreen.set(True)
        inventory_window.after(50, lambda: (auto_adjust_columns(chb_tree), auto_adjust_columns(tree), schedule_status_labels()))

    # Define inventory table columns and display headings.
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
    # Build the CHB items table with scrollbars.
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

    # Build the other inventory items table with scrollbars.
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

    # Prepare an overlay label for searches with no matching results.
    no_results_label = tk.Label(
        tree_frame,
        text="No matching product found.",
        font=("Arial", 16, "bold"),
        bg="#fef2f2",
        fg="#dc2626",
        padx=18,
        pady=10,
        bd=1,
        relief="solid"
    )

    # Configure table style and row tags.
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
        # Apply common headings, widths, and alignment to an inventory table.
        for column_id, heading_text in column_headings.items():
            anchor = "w" if column_id == "Name" else "e" if column_id in ("Price", "Raw Price") else "center"
            target_tree.heading(column_id, text=heading_text)
            target_tree.column(column_id, width=120, minwidth=80, anchor=anchor, stretch=False)

    configure_columns(chb_tree)
    configure_columns(tree)

    # Track overlay widgets and scheduled render jobs for status/restock buttons.
    overlay_widgets = {}
    status_render_job = {"id": None}
    column_adjust_job = {"id": None}
    status_rendering = {"active": False}
    selected_action_tree = {"tree": tree}
    selection_syncing = {"active": False}

    def close_inventory_window():
        # Close inventory, cancel pending jobs, close DB, and restore parent focus.
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
        # Measure headings and row values to keep inventory columns readable.
        clear_status_labels()
        target_tree.update_idletasks()
        heading_font = tkfont.Font(font=style.lookup("Inventory.Treeview.Heading", "font"))
        body_font = tkfont.Font(font=style.lookup("Inventory.Treeview", "font"))
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
        max_widths = {
            "ID": 90,
            "Name": 240,
            "Unit": 190,
            "Quantity": 330,
            "Price": 330,
            "Raw Price": 170,
            "Status": 140,
            "Restock": 130,
        }

        tree_columns = list(target_tree["columns"])
        measured_widths = {}
        for col in columns:
            heading_text = column_headings[col]
            width = heading_font.measure(heading_text) + extra_padding[col]
            col_index = tree_columns.index(col)
            for item in target_tree.get_children():
                values = target_tree.item(item, "values")
                if col_index >= len(values):
                    continue
                value_width = body_font.measure(str(values[col_index])) + extra_padding[col]
                width = max(width, value_width)
            width = min(width, max_widths[col])
            measured_widths[col] = width

        if target_tree is tree:
            # Spread extra width across flexible columns in the main table.
            target_tree.update_idletasks()
            total_width = sum(measured_widths.values())
            available_width = max(target_tree.winfo_width() - 24, total_width)
            if available_width > total_width:
                flexible_columns = ["Name", "Unit", "Quantity", "Price", "Raw Price", "Status", "Restock"]
                extra_width = available_width - total_width
                per_column = extra_width // len(flexible_columns)
                remainder = extra_width % len(flexible_columns)
                for index, col in enumerate(flexible_columns):
                    measured_widths[col] += per_column + (1 if index < remainder else 0)

        for col in columns:
            target_tree.column(col, width=measured_widths[col], minwidth=measured_widths[col], stretch=False)

    def schedule_column_adjust(target_tree=None):
        # Schedule one idle column adjustment instead of recalculating repeatedly.
        if column_adjust_job["id"] is not None:
            return

        def run_adjust():
            # Run the pending column adjustment for one or both tables.
            column_adjust_job["id"] = None
            if target_tree is not None:
                auto_adjust_columns(target_tree)
            else:
                auto_adjust_columns(chb_tree)
                auto_adjust_columns(tree)
            schedule_status_labels(target_tree)

        parent_widget = target_tree if target_tree is not None else inventory_window
        column_adjust_job["id"] = parent_widget.after_idle(run_adjust)

    def clear_status_labels():
        # Remove overlay status labels and restock buttons.
        for widget in overlay_widgets.values():
            if widget.winfo_exists():
                widget.destroy()
        overlay_widgets.clear()

    def schedule_status_labels(target_tree=None):
        # Schedule overlay rendering for status labels and restock buttons.
        if status_rendering["active"]:
            return

        if status_render_job["id"] is not None:
            inventory_window.after_cancel(status_render_job["id"])

        parent = target_tree if target_tree is not None else inventory_window
        status_render_job["id"] = parent.after_idle(render_status_labels)

    def open_restock_target(row_values):
        # Open CHB production for CHB Blocks or restock form for other items.
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
        # Load Cement, Fine Sand, and CHB Blocks into the CHB section.
        for row in chb_tree.get_children():
            chb_tree.delete(row)

        chb_count = 0
        placeholders = ", ".join("?" for _ in CHB_SECTION_ITEMS)
        params = [item_name.lower() for item_name in CHB_SECTION_ITEMS]

        cursor.execute(
            f"""
            SELECT id, name, unit, quantity, price, raw_price, COALESCE(status, 'Active'), COALESCE(fine_sand_bag_price, 0)
            FROM items
            WHERE LOWER(name) IN ({placeholders})
            ORDER BY CASE LOWER(name)
                WHEN 'cement' THEN 1
                WHEN 'fine sand' THEN 2
                WHEN 'chb blocks' THEN 3
                ELSE 4
            END
            """,
            tuple(params)
        )
        for index, row in enumerate(cursor.fetchall()):
            display_row = inventory_functions.display_inventory_row(row)
            tag = inventory_functions.inventory_row_tag(index, display_row)
            chb_tree.insert("", tk.END, values=display_row + ("",), tags=(tag,))
            chb_count += 1
        chb_items_count_var.set(f"Total: {chb_count:,}")
        auto_adjust_columns(chb_tree)

    def remove_chb_items_from_main_table():
        # Remove CHB-section items from the lower other-items table.
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
        other_items_count_var.set(f"Total: {remaining_index:,}")
        auto_adjust_columns(tree)

    def update_low_stock_count():
        # Count low-stock items and update the low-stock button text.
        low_stock_count = 0
        for row in inventory_functions.fetch_items(cursor, "", "Latest Date"):
            item_name = row[1] if len(row) > 1 else ""
            quantity = row[3] if len(row) > 3 else 0
            if inventory_functions.is_low_stock_item(item_name, quantity):
                low_stock_count += 1
        prefix = "Showing Low Stock" if low_stock_filter["active"] else "Low Stock Items"
        low_stock_var.set(f"{prefix}: {low_stock_count:,}")

    def apply_low_stock_filter():
        # Hide non-low-stock rows when the low-stock filter is active.
        if not low_stock_filter["active"]:
            return

        for target_tree in (tree,):
            visible_index = 0
            for item in list(target_tree.get_children()):
                values = target_tree.item(item, "values")
                item_name = values[1] if len(values) > 1 else ""
                quantity = values[3] if len(values) > 3 else 0
                if not inventory_functions.is_low_stock_item(item_name, quantity):
                    target_tree.delete(item)
                    continue
                target_tree.item(item, tags=(inventory_functions.LOW_STOCK_ROW,))
                visible_index += 1
            other_items_count_var.set(f"Total: {visible_index:,}")
            auto_adjust_columns(target_tree)

    def update_no_results_message():
        # Show the no-results message only for empty search results.
        has_search = bool(search_entry.get().strip())
        has_other_results = bool(tree.get_children())
        if has_search and not has_other_results:
            no_results_label.place(relx=0.5, rely=0.12, anchor="n")
            no_results_label.lift()
        else:
            no_results_label.place_forget()

    def show_low_stock_items():
        # Activate the low-stock-only view.
        low_stock_filter["active"] = True
        search_entry.delete(0, tk.END)
        refresh_view()

    def show_all_items():
        # Clear search/filter state and show all inventory items.
        if not low_stock_filter["active"] and search_entry.get() == "":
            return
        low_stock_filter["active"] = False
        search_entry.delete(0, tk.END)
        refresh_view()

    def set_selected_action_tree(target_tree):
        # Keep one active table selection for edit/delete actions.
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
        # Render simple status and restock overlays on visible table rows.
        status_render_job["id"] = None
        status_rendering["active"] = True
        try:
            visible_keys = set()

            def render_tree_status_labels(target_tree):
                # Render overlays for one inventory table.
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
                        # Select the row behind an overlay widget.
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
        # Render reusable overlay widgets for low-stock, status, and restock cells.
        global inventory_refresh_job
        if not inventory_window or not inventory_window.winfo_exists():
            return
        status_render_job["id"] = None
        inventory_refresh_job = None
        status_rendering["active"] = True
        try:
            visible_keys = set()

            def select_row(target_tree, row_id):
                # Select the row behind an overlay widget.
                target_tree.selection_set(row_id)
                target_tree.focus(row_id)
                set_selected_action_tree(target_tree)

            def get_row_bg(target_tree, item):
                # Pick overlay background color from the row tag.
                row_tags = target_tree.item(item, "tags")
                if row_tags and row_tags[0] == inventory_functions.LOW_STOCK_ROW:
                    return "#fed7aa"
                return "#93c5fd" if row_tags and row_tags[0] == "blue_row" else "#ffffff"

            def get_overlay(target_tree, item, kind, factory):
                # Reuse existing overlay widgets when possible.
                key = (str(target_tree), item, kind)
                visible_keys.add(key)
                widget = overlay_widgets.get(key)
                if widget is None or not widget.winfo_exists():
                    widget = factory()
                    overlay_widgets[key] = widget
                return widget

            def render_tree_overlays(target_tree):
                # Position overlay widgets over visible status/restock cells.
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
        # Reload inventory tables, filters, counters, and overlays.
        inventory_functions.refresh_current_view(conn, cursor, tree, search_entry, sort_filter_var, total_items_var)
        remove_chb_items_from_main_table()
        load_chb_items()
        apply_low_stock_filter()
        update_low_stock_count()
        update_no_results_message()
        schedule_column_adjust()
        schedule_status_labels()

    def sort_and_render(column, numeric=False):
        # Sort the main table and refresh row overlays.
        inventory_functions.sort_tree(tree, sort_state, column, numeric=numeric)
        remove_chb_items_from_main_table()
        schedule_status_labels()

    # Wire sortable headings for the main inventory table.
    tree.heading("ID", text="ID", command=lambda: sort_and_render("ID", numeric=True))
    tree.heading("Name", text="Name", command=lambda: sort_and_render("Name", numeric=False))
    tree.heading("Unit", text="Unit of Measurement", command=lambda: sort_and_render("Unit", numeric=False))
    tree.heading("Quantity", text="Quantity", command=lambda: sort_and_render("Quantity", numeric=True))
    tree.heading("Price", text="Selling Price", command=lambda: sort_and_render("Price", numeric=True))
    tree.heading("Raw Price", text="Raw Price", command=lambda: sort_and_render("Raw Price", numeric=True))
    tree.heading("Status", text="Status", command=lambda: sort_and_render("Status", numeric=False))
    tree.heading("Restock", text="Restock")

    # Keep overlays aligned while scrolling both tables.
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
    # Recalculate columns and overlays after table layout or selection changes.
    tree.bind("<Configure>", lambda event: schedule_column_adjust(tree))
    tree.bind("<MouseWheel>", lambda event: schedule_status_labels(tree))
    tree.bind("<B1-Motion>", lambda event: schedule_status_labels(tree))
    tree.bind("<ButtonRelease-1>", lambda event: schedule_status_labels(tree))
    tree_frame.bind("<Configure>", lambda event: schedule_column_adjust(tree))
    chb_tree.bind("<Configure>", lambda event: schedule_column_adjust(chb_tree))
    chb_tree.bind("<MouseWheel>", lambda event: schedule_status_labels(chb_tree))
    chb_tree.bind("<B1-Motion>", lambda event: schedule_status_labels(chb_tree))
    chb_tree.bind("<ButtonRelease-1>", lambda event: schedule_status_labels(chb_tree))
    chb_tree_frame.bind("<Configure>", lambda event: schedule_column_adjust(chb_tree))
    tree.bind("<<TreeviewSelect>>", lambda event: set_selected_action_tree(tree))
    chb_tree.bind("<<TreeviewSelect>>", lambda event: set_selected_action_tree(chb_tree))

    # Bind search and sort controls to refresh the inventory view.
    search_entry.bind("<KeyRelease>", lambda event: refresh_view())
    sort_filter.bind("<<ComboboxSelected>>", lambda event: refresh_view())
    inventory_refresh_callback = refresh_view

    # ---------- Buttons ----------
    # Define shared action button styling.
    button_options = {
        "font": ("Arial", 13, "bold"),
        "bd": 2,
        "relief": "solid",
        "highlightbackground": "black",
        "highlightcolor": "black",
        "highlightthickness": 1,
        "padx": 8,
        "pady": 12,
    }
    tk.Button(right_frame, text="Add Item", bg="#00c853", fg="white", command=lambda: inventory_functions.add_item(conn, cursor, inventory_window, tree, refresh_view), **button_options).grid(row=0, column=0, sticky="ew", pady=12, padx=4)
    tk.Button(right_frame, text="Edit Item", bg="#2196f3", fg="white", command=lambda: inventory_functions.update_item(conn, cursor, inventory_window, selected_action_tree["tree"], refresh_view), **button_options).grid(row=1, column=0, sticky="ew", pady=12, padx=4)
    tk.Button(right_frame, text="Adjust Stock", bg="#f59e0b", fg="white", command=lambda: inventory_functions.open_adjust_stock_form(conn, cursor, inventory_window, selected_action_tree["tree"].item(selected_action_tree["tree"].focus(), "values") if selected_action_tree["tree"].focus() else None, refresh_view), **button_options).grid(row=2, column=0, sticky="ew", pady=12, padx=4)
    tk.Button(right_frame, text="Delete Item", bg="#ff1744", fg="white", command=lambda: inventory_functions.delete_item(conn, cursor, inventory_window, selected_action_tree["tree"], refresh_view), **button_options).grid(row=3, column=0, sticky="ew", pady=12, padx=4)

    # Close cleanly and load the initial inventory data.
    inventory_window.protocol("WM_DELETE_WINDOW", close_inventory_window)
    refresh_view()
