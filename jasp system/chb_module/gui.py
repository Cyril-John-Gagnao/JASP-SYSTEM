import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk
import sqlite3
from datetime import datetime
from delivery_section import open_delivery_window
from window_utils import close_window_and_focus_parent
from jasp_theme import (
    DASHBOARD_CONTENT_BG,
    DASHBOARD_HEADER_BG,
    DASHBOARD_HEADER_BORDER,
    DASHBOARD_HEADER_FG,
    add_header_logo,
)

from .chb_database import DB_NAME, init_db, ensure_chb_inventory
from . import functions as chb_functions

# 🎨 COLORS
# Define the CHB dashboard colors from the shared JASP theme.
BG_MAIN = DASHBOARD_CONTENT_BG
CARD_BG = "#ffffff"
PRIMARY = "#2563eb"
ACCENT = "#60a5fa"
TEXT = "#1e293b"
BORDER = "#dbeafe"

# Reuse a consistent bordered button style across this dashboard.
BUTTON_BORDER = {
    "bd": 2,
    "relief": "solid",
    "highlightthickness": 1,
    "highlightbackground": "black",
    "highlightcolor": "black",
}


# ================= MAIN =================
def open_chb_dashboard(parent=None):
    # Initialize required CHB database tables before opening the window.
    init_db()

    # Create the CHB dashboard window and connect it to the parent dashboard if present.
    win = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
    win.title("CHB Production Module")
    win.state("zoomed")
    win.configure(bg=BG_MAIN)
    win.option_add("*TCombobox*Listbox.font", ("Arial", 16))
    if parent is not None:
        win.transient(parent)
    win.protocol("WM_DELETE_WINDOW", lambda: close_window_and_focus_parent(win, parent))

    # Open the shared SQLite connection and make sure CHB inventory state is ready.
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    ensure_chb_inventory(conn, cursor)
    chb_functions.notify_inventory_views()

    # Use the latest saved pay rate as the default for new production entries.
    cursor.execute("SELECT pay_rate FROM chb_production ORDER BY ts DESC LIMIT 1")
    last_rate = cursor.fetchone()
    if last_rate and last_rate[0] is not None:
        try:
            pay_rate_default = float(last_rate[0])
        except Exception:
            pay_rate_default = 200
    else:
        pay_rate_default = 200

    selected_id = tk.StringVar()

    # ================= HEADER =================
    # Build the dashboard header with logo, title, refresh, and back actions.
    header_frame = tk.Frame(win, bg=DASHBOARD_HEADER_BG, padx=14, pady=10, highlightthickness=1, highlightbackground=DASHBOARD_HEADER_BORDER)
    header_frame.pack(fill="x", padx=20, pady=10)

    header_frame.columnconfigure(0, weight=1)
    header_frame.columnconfigure(1, weight=0)

    title_frame = tk.Frame(header_frame, bg=DASHBOARD_HEADER_BG)
    title_frame.grid(row=0, column=0, sticky="w")
    add_header_logo(title_frame, DASHBOARD_HEADER_BG, size=52)

    tk.Label(
        title_frame,
        text="CHB Production Management",
        font=("Arial", 26, "bold"),
        bg=DASHBOARD_HEADER_BG,
        fg=DASHBOARD_HEADER_FG
    ).pack(side="left")

    # Place the refresh and back buttons on the right side of the header.
    btn_container = tk.Frame(header_frame, bg=DASHBOARD_HEADER_BG)
    btn_container.grid(row=0, column=1, sticky="e")

    tk.Button(
        btn_container,
        text="🔄 Refresh",
        command=lambda: refresh_all(),
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
        command=lambda: close_window_and_focus_parent(win, parent),
        bg="#2563eb",
        fg="white",
        font=("Arial", 13, "bold"),
        padx=12,
        pady=5,
        **BUTTON_BORDER
    ).pack(side="left", padx=3)

    # ================= SEARCH =================
    # Build the search, sorting, summary, and delivery navigation controls.
    search_frame = tk.Frame(win, bg=BG_MAIN)
    search_frame.pack(fill="x", padx=20, pady=(0, 15))

    tk.Label(search_frame, text="🔍 Search:", bg=BG_MAIN, fg=TEXT, font=("Arial", 15, "bold"))\
        .pack(side="left", padx=10, pady=10)

    search_var = tk.StringVar()
    search_entry = tk.Entry(search_frame, textvariable=search_var, width=35, font=("Arial", 14), bd=2, relief="solid")
    search_entry.pack(side="left", padx=10, pady=10)

    tk.Label(search_frame, text="Sort By:", bg=BG_MAIN, fg=TEXT, font=("Arial", 15, "bold"))\
        .pack(side="left", padx=(30, 10), pady=10)

    sort_var = tk.StringVar(value="Date (Newest)")

    sort_menu = ttk.Combobox(
        search_frame,
        textvariable=sort_var,
        values=["Date (Newest)", "Worker Name"],
        state="readonly",
        width=22,
        font=("Arial", 14)
    )
    sort_menu.pack(side="left", pady=10)
    # Add shortcuts for CHB summaries and the delivery section.
    tk.Button(search_frame, text='Summary', command=lambda: chb_functions.open_period_summary(win, cursor, BG_MAIN, TEXT), bg='#8b5cf6', fg='white', font=('Arial', 13, 'bold'), padx=12, pady=6, **BUTTON_BORDER).pack(side='left', padx=10)
    tk.Button(search_frame, text='Open Delivery Section', command=lambda: open_delivery_window(win, BG_MAIN, CARD_BG, PRIMARY), bg='#f59e0b', fg='white', font=('Arial', 13, 'bold'), padx=12, pady=6, **BUTTON_BORDER, cursor='hand2').pack(side='left', padx=(0, 10), pady=10)

    # ================= TOTAL HOLLOW BLOCKS DISPLAY =================
    # Show current CHB availability and stock adjustment/fullscreen actions.
    total_frame = tk.Frame(win, bg=BG_MAIN)
    total_frame.pack(fill="x", padx=20, pady=(5, 10))

    total_blocks_var = tk.StringVar(value="Total Hollow Blocks Available: 0")

    total_label = tk.Label(
        total_frame,
        textvariable=total_blocks_var,
        font=("Arial", 18, "bold"),
        bg=BG_MAIN,
        fg="#1e40af"
    )
    total_label.pack(side="left")

    tk.Button(
        total_frame,
        text="Adjust CHB Stock",
        command=lambda: chb_functions.open_chb_adjustment_form(conn, cursor, win, update_total_blocks),
        bg="#7c3aed",
        fg="white",
        font=("Arial", 13, "bold"),
        padx=12,
        pady=6,
        **BUTTON_BORDER
    ).pack(side="left", padx=(18, 0))

    fullscreen_btn = tk.Button(total_frame, text='Full Screen Display', command=lambda: toggle_display_fullscreen(), bg='#0f766e', fg='white', font=('Arial', 13, 'bold'), padx=12, pady=6, **BUTTON_BORDER)
    fullscreen_btn.pack(side="right", padx=(10, 0))

    # ================= MAIN CONTAINER (51-49 Split) =================
    # Create the main split area for the production table and input form.
    main_container = tk.Frame(win, bg=CARD_BG, bd=1, relief="solid")
    main_container.pack(padx=20, pady=(0, 8), fill="both", expand=True)

    # Configure columns so the table has slightly more space than the form.
    main_container.columnconfigure(0, weight=51, minsize=620)
    main_container.columnconfigure(1, weight=49, minsize=508)
    main_container.rowconfigure(0, weight=1)

    # ================= FORM (RIGHT SIDE - 49%) =================
    # Build the right-side card that contains CHB production inputs.
    form_card = tk.Frame(main_container, bg=CARD_BG)
    form_card.grid(row=0, column=1, sticky="nsew", padx=(6, 16), pady=(8, 12))
    form_card.columnconfigure(1, weight=1)

    # Add the production form title.
    tk.Label(form_card, text="CHB Production", font=("Arial", 21, "bold"), bg=CARD_BG, fg=PRIMARY).pack(pady=(0, 8))

    # Create the highlighted form background area.
    form_bg = tk.Frame(form_card, bg="#fef3c7", bd=1, relief="flat")
    form_bg.pack(fill="x", padx=5, pady=(4, 6))

    # Configure the input grid inside the production form.
    form = tk.Frame(form_bg, bg="#fef3c7")
    form.pack(fill="x", padx=16, pady=12)
    form.columnconfigure(0, weight=0, minsize=128)
    form.columnconfigure(1, weight=1, minsize=266)

    # Production date field with calendar button.
    tk.Label(form, text="Production Date", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=0, column=0, sticky="w", pady=6)
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    date_frame = tk.Frame(form, bg="#fef3c7")
    date_frame.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=6)
    tk.Button(date_frame, text="📅", command=lambda: chb_functions.open_date_calendar(win, date_var), bg="#3b82f6", fg="white", font=("Arial", 12, "bold"), width=3, padx=4, pady=3, **BUTTON_BORDER).pack(side="left", padx=(0, 6))
    date_entry = tk.Entry(date_frame, textvariable=date_var, width=20, font=("Arial", 14), bd=1, relief="solid", bg="white")
    date_entry.pack(side="left", fill="x", expand=True)

    # Worker name input for the production record.
    tk.Label(form, text="Worker Name", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=1, column=0, sticky="w", pady=6)
    worker_entry = tk.Entry(form, width=20, font=("Arial", 14), bd=1, relief="solid", bg="white")
    worker_entry.grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=6)

    # Cement input with the current cement stock display below it.
    tk.Label(form, text="Bag/s of Cement", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=2, column=0, sticky="w", pady=6)
    cement_frame = tk.Frame(form, bg="#fef3c7")
    cement_frame.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=6)
    cement_frame.columnconfigure(0, weight=1)
    cement_stock_var = tk.StringVar()
    cement_entry = tk.Entry(cement_frame, width=12, font=("Arial", 14), bd=1, relief="solid", bg="white")
    cement_entry.grid(row=0, column=0, sticky="ew")
    cement_stock_combo = ttk.Combobox(
        cement_frame,
        textvariable=cement_stock_var,
        values=[],
        state="readonly",
        width=16,
        font=("Arial", 12)
    )
    cement_stock_combo.grid(row=1, column=0, sticky="ew", pady=(4, 0))

    # Fine sand field is auto-calculated from cement and shows available stock.
    tk.Label(form, text="Bag/s of Fine Sand", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=3, column=0, sticky="nw", pady=6)
    sand_frame = tk.Frame(form, bg="#fef3c7")
    sand_frame.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=6)
    sand_frame.columnconfigure(0, weight=1)
    sand_stock_var = tk.StringVar()
    sand_entry = tk.Entry(sand_frame, width=12, font=("Arial", 15), bd=1, relief="solid", bg="white")
    sand_entry.grid(row=0, column=0, sticky="ew", ipady=3)
    sand_stock_combo = tk.Label(
        sand_frame,
        textvariable=sand_stock_var,
        bg="#fff7ed",
        fg="#92400e",
        font=("Arial", 11, "bold"),
        justify="left",
        anchor="w",
        bd=1,
        relief="solid",
        padx=7,
        pady=4,
        width=36,
        wraplength=297
    )
    sand_stock_combo.grid(row=1, column=0, sticky="w", pady=(4, 0))

    # Pay rate input controls the computed worker pay.
    tk.Label(form, text="Salary / 75 Blocks", bg="#fef3c7", font=("Arial", 13, "bold"), fg="#1e293b").grid(row=4, column=0, sticky="w", pady=6)
    pay_rate_var = tk.DoubleVar(value=pay_rate_default)
    pay_rate_entry = tk.Entry(form, textvariable=pay_rate_var, width=20, font=("Arial", 14), bd=1, relief="solid", bg="white")
    pay_rate_entry.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=6)

    # Show computed block count and pay beside the form inputs.
    result_frame = tk.Frame(form_card, bg="#e0f2fe")
    result_frame.pack(pady=8, fill="x", padx=5)

    tk.Label(
        result_frame,
        text="Blocks:",
        font=("Arial", 15, "bold"),
        bg="#e0f2fe",
        fg="#0369a1",
        pady=7
    ).pack(side="left", padx=(12, 6))

    blocks_var = tk.StringVar(value="0")
    blocks_entry = tk.Entry(
        result_frame,
        textvariable=blocks_var,
        width=10,
        font=("Arial", 15, "bold"),
        bd=1,
        relief="solid",
        justify="center",
        bg="white",
        fg="#0369a1"
    )
    blocks_entry.pack(side="left", padx=6, pady=5)

    result_label = tk.Label(
        result_frame,
        text="| Pay: ₱0",
        font=("Arial", 15, "bold"),
        bg="#e0f2fe",
        fg="#0369a1",
        pady=7
    )
    result_label.pack(side="left", padx=6)

    # Build the bottom action button row for the production form.
    btn_frame = tk.Frame(form_card, bg=CARD_BG)
    btn_frame.pack(side="bottom", pady=(0, 16), fill="x")
    btn_frame.columnconfigure(0, weight=1)
    btn_frame.columnconfigure(1, weight=1)
    btn_frame.columnconfigure(2, weight=1)
    btn_frame.columnconfigure(3, weight=1)

    # ================= AUTO CALC =================
    # Wire live calculations for fine sand, blocks, and pay.
    auto_sand = lambda event=None: chb_functions.auto_sand(event, cement_entry, sand_entry, pay_rate_var, blocks_entry, result_label)
    update_pay = lambda event=None: chb_functions.update_pay(event, cement_entry, pay_rate_var, result_label)

    cement_entry.bind("<KeyRelease>", auto_sand)
    pay_rate_entry.bind("<KeyRelease>", update_pay)

    # ================= FUNCTIONS =================
    # Wrap CHB actions so they can access this window's widgets and database cursor.
    clear_form = lambda: chb_functions.clear_form(worker_entry, cement_entry, sand_entry, blocks_entry, result_label, selected_id)
    confirm_clear = lambda: chb_functions.confirm_clear_form(win, worker_entry, cement_entry, sand_entry, blocks_entry, result_label, selected_id)
    update_total_blocks = lambda: chb_functions.update_total_blocks(conn, cursor, total_blocks_var)
    refresh_materials = lambda: chb_functions.refresh_material_dropdowns(cursor, cement_stock_var, sand_stock_var, cement_stock_combo, sand_stock_combo)
    refresh_all = lambda: (chb_functions.refresh_data(load_data, update_total_blocks), refresh_materials())
    save = lambda: chb_functions.save(conn, cursor, win, worker_entry, date_var, cement_entry, blocks_entry, pay_rate_var, load_data, update_total_blocks, clear_form, refresh_materials)
    update = lambda: chb_functions.update(conn, cursor, win, selected_id, worker_entry, date_var, cement_entry, blocks_entry, pay_rate_var, load_data, update_total_blocks, clear_form, refresh_materials)
    delete = lambda: chb_functions.delete(conn, cursor, win, selected_id, worker_entry, load_data, update_total_blocks, clear_form, refresh_materials)

    # ================= BUTTONS =================
    # Define and place the Save, Update, Delete, and Clear production actions.
    action_button_options = {
        "fg": "white",
        "font": ("Arial", 12, "bold"),
        "padx": 7,
        "pady": 9,
        "cursor": "hand2",
        **BUTTON_BORDER,
    }
    tk.Button(btn_frame, text="✓ Save", command=save, bg="#15803d", **action_button_options).grid(row=0, column=0, sticky="ew", padx=4, pady=3)
    tk.Button(btn_frame, text="🔁 Update", command=update, bg="#1e40af", **action_button_options).grid(row=0, column=1, sticky="ew", padx=4, pady=3)
    tk.Button(btn_frame, text="🗑 Delete", command=delete, bg="#dc2626", **action_button_options).grid(row=0, column=2, sticky="ew", padx=4, pady=3)
    tk.Button(btn_frame, text="✋ Clear", command=confirm_clear, bg="#64748b", **action_button_options).grid(row=0, column=3, sticky="ew", padx=4, pady=3)

    # ================= TABLE (LEFT SIDE - 60%) =================
    # Build the left-side card that displays today's production records.
    table_card = tk.Frame(main_container, bg=CARD_BG)
    table_card.grid(row=0, column=0, sticky="nsew", padx=(10, 6), pady=(8, 12))
    table_card.columnconfigure(0, weight=1)
    table_card.rowconfigure(0, weight=1)

    display_fullscreen = tk.BooleanVar(value=False)

    def toggle_display_fullscreen():
        # Toggle between split form/table view and full-width table view.
        if display_fullscreen.get():
            form_card.grid(row=0, column=1, sticky="nsew", padx=(6, 16), pady=(8, 12))
            table_card.grid_configure(row=0, column=0, columnspan=1, sticky="nsew", padx=(10, 6), pady=(8, 12))
            main_container.columnconfigure(0, weight=51, minsize=620)
            main_container.columnconfigure(1, weight=49, minsize=508)
            fullscreen_btn.config(text="Full Screen Display", bg="#0f766e")
            display_fullscreen.set(False)
        else:
            form_card.grid_remove()
            table_card.grid_configure(row=0, column=0, columnspan=2, sticky="nsew", padx=12, pady=(8, 12))
            main_container.columnconfigure(0, weight=1, minsize=0)
            main_container.columnconfigure(1, weight=0, minsize=0)
            fullscreen_btn.config(text="Exit Full Screen", bg="#334155")
            display_fullscreen.set(True)
        win.after(50, auto_adjust_columns)

    columns = ("id", "date", "worker", "cement", "Fine Sand", "blocks", "pay", "user")
    
    # Configure the production table style and heading sizes.
    style = ttk.Style()
    tree_style_name = "CHBProduction.Treeview"
    style.configure(tree_style_name, font=('Arial', 13), rowheight=44)
    style.configure(f'{tree_style_name}.Heading', font=('Arial', 16, 'bold'), padding=(6, 10, 6, 10))
    
    # Configure selection and row background colors.
    style.configure(tree_style_name, background="white", fieldbackground="white")
    style.map(tree_style_name, background=[('selected', '#2563eb')])
    
    # Create the table container with scrollbars.
    tree_frame = tk.Frame(table_card, bg=CARD_BG)
    tree_frame.grid(row=0, column=0, sticky="nsew")
    tree_frame.columnconfigure(0, weight=1)
    tree_frame.rowconfigure(0, weight=1)

    # Prepare an overlay label for searches with no matching records.
    no_results_label = tk.Label(
        tree_frame,
        text="No matching production records found.",
        font=("Arial", 16, "bold"),
        bg="#fef2f2",
        fg="#dc2626",
        padx=18,
        pady=10,
        bd=1,
        relief="solid"
    )
    
    # Add a vertical scrollbar for long production lists.
    vsb = ttk.Scrollbar(tree_frame, orient="vertical")
    vsb.grid(row=0, column=1, sticky="ns")
    
    # Add a horizontal scrollbar for wide production columns.
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal")
    hsb.grid(row=1, column=0, sticky="ew")
    
    # Create the production Treeview and connect it to both scrollbars.
    tree = ttk.Treeview(tree_frame, columns=columns, show="headings", style=tree_style_name, yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    
    # Link scrollbar movements back to the table.
    vsb.config(command=tree.yview)
    hsb.config(command=tree.xview)

    # Define user-facing column labels for the production table.
    column_labels = {
        "id": "Id",
        "date": "Prod. Date",
        "worker": "Worker Name",
        "cement": "Cement Bags",
        "Fine Sand": "Fine Sand Bags",
        "blocks": "Blocks",
        "pay": "Pay",
        "user": "User",
    }

    def auto_adjust_columns():
        # Measure headings and row values to keep table columns readable.
        tree.update_idletasks()
        heading_font = tkfont.Font(font=style.lookup(f"{tree_style_name}.Heading", "font"))
        row_font = tkfont.Font(font=style.lookup(tree_style_name, "font"))
        column_padding = {
            "id": 50,
            "date": 65,
            "worker": 85,
            "cement": 70,
            "Fine Sand": 80,
            "blocks": 70,
            "pay": 75,
            "user": 70,
        }
        base_min_widths = {
            "id": 40,
            "date": 75,
            "worker": 90,
            "cement": 80,
            "Fine Sand": 95,
            "blocks": 70,
            "pay": 80,
            "user": 100,
        }
        max_widths = {
            "id": 90,
            "date": 170,
            "worker": 260,
            "cement": 210,
            "Fine Sand": 230,
            "blocks": 150,
            "pay": 160,
            "user": 220,
        }
        measured_widths = {}
        min_widths = {}

        for col in columns:
            header_text = column_labels.get(col, col.upper())
            header_width = heading_font.measure(header_text) + column_padding[col]
            min_widths[col] = max(base_min_widths[col], min(header_width, max_widths[col]))
            width = header_width
            for item in tree.get_children():
                width = max(width, row_font.measure(str(tree.set(item, col))) + column_padding[col])
            measured_widths[col] = max(min_widths[col], min(width, max_widths[col]))

        if display_fullscreen.get():
            # Spread extra width across visible columns in fullscreen table mode.
            total_width = sum(measured_widths.values())
            available_width = max(tree.winfo_width() - 24, total_width)
            if available_width > total_width:
                flexible_columns = ["date", "worker", "cement", "Fine Sand", "blocks", "pay", "user"]
                extra_width = available_width - total_width
                per_column = extra_width // len(flexible_columns)
                remainder = extra_width % len(flexible_columns)
                for index, col in enumerate(flexible_columns):
                    measured_widths[col] += per_column + (1 if index < remainder else 0)

        for col in columns:
            tree.column(col, width=measured_widths[col], minwidth=min_widths[col], stretch=False)

    # Set initial table column widths before dynamic measurement runs.
    initial_widths = {
        "id": 45,
        "date": 80,
        "worker": 100,
        "cement": 90,
        "Fine Sand": 105,
        "blocks": 75,
        "pay": 90,
        "user": 110,
    }
    for col in columns:
        tree.heading(col, text=column_labels.get(col, col.upper()))
        tree.column(col, anchor="center", width=initial_widths[col], minwidth=initial_widths[col], stretch=False)

    # Recalculate table columns after resize events.
    on_tree_configure = lambda event=None: (chb_functions.on_tree_configure(event, tree), auto_adjust_columns())
    
    tree.bind('<Configure>', on_tree_configure)
    
    # Configure alternating row colors for easier scanning.
    tree.tag_configure('oddrow', background='#ffffff', foreground='#000000')
    tree.tag_configure('evenrow', background='#93c5fd', foreground='#000000')

    # Load a clicked table row into the production form for editing.
    on_select = lambda event: chb_functions.on_select(event, tree, selected_id, date_var, worker_entry, cement_entry, sand_entry, blocks_entry, cursor, pay_rate_var, update_pay)

    tree.bind("<ButtonRelease-1>", on_select)

    # ================= LOAD DATA =================
    def load_data(event=None):
        # Reload production rows and show a no-results notice when search is empty.
        row_count = chb_functions.load_data(event, tree, search_var, sort_var, cursor)
        if search_var.get().strip() and row_count == 0:
            no_results_label.place(relx=0.5, rely=0.12, anchor="n")
            no_results_label.lift()
        else:
            no_results_label.place_forget()
        auto_adjust_columns()

    # ✅ BINDINGS (LIVE SEARCH)
    # Bind live search and sort changes to reload the production table.
    search_entry.bind("<KeyRelease>", load_data)
    sort_menu.bind("<<ComboboxSelected>>", load_data)

    # ✅ INITIAL LOAD
    # Load initial dashboard data, CHB total, and material stock displays.
    load_data()
    update_total_blocks()
    refresh_materials()
