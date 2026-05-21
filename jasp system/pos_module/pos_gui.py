import tkinter as tk
from tkinter import ttk

from pos_module import pos_functions
from pos_module.pos_database import initialize_pos_database
from pos_module.pos_summary import open_pos_summary
from window_utils import close_window_and_focus_parent, enable_centered_toplevels
from jasp_theme import (
    DASHBOARD_CONTENT_BG,
    DASHBOARD_HEADER_BG,
    DASHBOARD_HEADER_BORDER,
    DASHBOARD_HEADER_FG,
    add_header_logo,
)

# Keep POS popup windows centered using the shared window helper.
enable_centered_toplevels()

# Store the active POS refresh callback and shared button styling.
pos_refresh_callback = None
BUTTON_BORDER = {
    "bd": 2,
    "relief": "solid",
    "highlightthickness": 1,
    "highlightbackground": "black",
    "highlightcolor": "black",
}
CART_PANEL_BG = "#e0f2fe"
CART_HEADER_BG = "#bfdbfe"

# ==================== POS WINDOW ====================
def open_pos(parent=None):
    global pos_refresh_callback
    # Initialize the POS database connection and shared UI context.
    conn, cursor = initialize_pos_database()

    ctx = {
        "conn": conn,
        "cursor": cursor,
        "cart": [],
        "inventory_names": [],
        "inventory_buttons": {},
        "inventory_button_job": None,
        "cart_buttons": {},
        "cart_button_job": None,
        "button_border": BUTTON_BORDER,
    }
    # Configure the shared Treeview style used by POS tables.
    pos_style = ttk.Style()
    pos_style.configure(
        "Pos.Treeview",
        font=("Arial", 15),
        rowheight=38,
        background="white",
        fieldbackground="white",
    )
    pos_style.configure(
        "Pos.Treeview.Heading",
        font=("Arial", 15, "bold"),
    )

    # ---------- GUI ----------
    # Create the POS main window and bind it to the optional parent window.
    root = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
    root.title("POS System")
    root.state("zoomed")  # Fullscreen
    root.configure(bg=DASHBOARD_CONTENT_BG)
    root.option_add("*TCombobox*Listbox.font", ("Arial", 17))

    if parent is not None:
        root.transient(parent)
    root.grab_set()         # lock focus to POS
    ctx["root"] = root

    def close_pos_window():
        # Clear the refresh hook and return focus to the parent window.
        globals().__setitem__("pos_refresh_callback", None)
        close_window_and_focus_parent(root, parent)

    root.protocol("WM_DELETE_WINDOW", close_pos_window)

    # ====== Header ======
    # Build the POS header with title, back, and refresh controls.
    header_frame = tk.Frame(
        root,
        bg=DASHBOARD_HEADER_BG,
        padx=14,
        pady=10,
        highlightthickness=1,
        highlightbackground=DASHBOARD_HEADER_BORDER,
    )
    header_frame.pack(fill="x", padx=20, pady=(12, 8))

    title_frame = tk.Frame(header_frame, bg=DASHBOARD_HEADER_BG)
    title_frame.pack(side=tk.LEFT)
    add_header_logo(title_frame, DASHBOARD_HEADER_BG, size=52)
    tk.Label(
        title_frame,
        text="POINT OF SALE (POS)",
        bg=DASHBOARD_HEADER_BG,
        fg=DASHBOARD_HEADER_FG,
        font=("Arial", 22, "bold"),
    ).pack(side=tk.LEFT)

    tk.Button(header_frame, text="← Back", bg="#2563eb", fg="white", activebackground="#1d4ed8", activeforeground="white", font=("Arial", 13, "bold"),
              command=close_pos_window, padx=12, pady=8, **BUTTON_BORDER).pack(side=tk.RIGHT, padx=6)
    tk.Button(header_frame, text="🔄 Refresh", bg="#16a34a", fg="white", font=("Arial", 13, "bold"),
              command=lambda: pos_functions.load_inventory(ctx, search_entry.get()), padx=12, pady=8, **BUTTON_BORDER).pack(side=tk.RIGHT, padx=6)

    # ====== Main Frame ======
    # Create the main two-panel layout for cart and inventory.
    main_frame = tk.Frame(root, bg=DASHBOARD_CONTENT_BG)
    main_frame.pack(fill="both", expand=True, padx=10, pady=5)

    cart_fullscreen = tk.BooleanVar(value=False)

    # Left Frame - Cart / POS
    # Build the checkout cart panel on the left side.
    left_frame = tk.Frame(
        main_frame,
        bg=CART_PANEL_BG,
        padx=10,
        pady=10,
        highlightthickness=1,
        highlightbackground="#93c5fd",
    )
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
    left_frame.configure(width=620)
    left_frame.pack_propagate(False)

    sort_var = tk.StringVar(value="Name")
    ctx["sort_var"] = sort_var

    # Build the cart header and fullscreen toggle.
    cart_header_frame = tk.Frame(left_frame, bg=CART_HEADER_BG, bd=1, relief="solid")
    cart_header_frame.pack(fill="x", pady=(10, 5))
    tk.Label(
        cart_header_frame,
        text="Checkout Cart",
        font=("Arial", 17, "bold"),
        bg=CART_HEADER_BG,
        fg="#1e40af",
    ).pack(side="left", padx=10, pady=6)
    cart_fullscreen_btn = tk.Button(
        cart_header_frame,
        text="Full Screen",
        bg="#2563eb",
        fg="white",
        activebackground="#1d4ed8",
        activeforeground="white",
        font=("Arial", 11, "bold"),
        command=lambda: toggle_cart_fullscreen(),
        padx=10,
        pady=3,
        **BUTTON_BORDER,
    )
    cart_fullscreen_btn.pack(side="right")

    cart_frame = tk.Frame(left_frame, bg=CART_PANEL_BG)
    cart_frame.pack(pady=5)
    tk.Label(cart_frame, text=" You can also Double-click an item to select it.", font=("Arial", 13),
             bg=CART_PANEL_BG).pack()
    # Cart Treeview
    # Build the cart table with scrollbars and overlay edit buttons.
    cart_table_frame = tk.Frame(left_frame, bg=CART_PANEL_BG)
    cart_table_frame.pack(fill="x", pady=(3, 4))
    cart_table_frame.configure(height=270)
    cart_table_frame.pack_propagate(False)
    cart_table_frame.grid_columnconfigure(0, weight=1)
    cart_table_frame.grid_rowconfigure(0, weight=1)

    global cart_tree
    cart_tree = ttk.Treeview(cart_table_frame, columns=("ID","Name","Unit","Qty","Selling Price","Total","Edit"), show="headings", style="Pos.Treeview")
    ctx["cart_tree"] = cart_tree
    cart_y_scroll = ttk.Scrollbar(cart_table_frame, orient="vertical", command=cart_tree.yview)
    cart_x_scroll = ttk.Scrollbar(cart_table_frame, orient="horizontal", command=cart_tree.xview)
    cart_y_scroll.configure(command=lambda *args: (cart_tree.yview(*args), pos_functions.schedule_cart_buttons(ctx)))
    cart_x_scroll.configure(command=lambda *args: (cart_tree.xview(*args), pos_functions.schedule_cart_buttons(ctx)))
    cart_tree.configure(
        yscrollcommand=lambda *args: (cart_y_scroll.set(*args), pos_functions.schedule_cart_buttons(ctx)),
        xscrollcommand=lambda *args: (cart_x_scroll.set(*args), pos_functions.schedule_cart_buttons(ctx)),
    )
    cart_tree.grid(row=0, column=0, sticky="nsew")
    cart_y_scroll.grid(row=0, column=1, sticky="ns")
    cart_x_scroll.grid(row=1, column=0, sticky="ew")
    tk.Frame(cart_table_frame, bg=CART_PANEL_BG, width=16, height=16).grid(row=1, column=1, sticky="nsew")
    cart_column_specs = {
        "ID": (60, 55, 0.8),
        "Name": (170, 130, 2.4),
        "Unit": (90, 75, 1.0),
        "Qty": (65, 60, 0.8),
        "Selling Price": (115, 105, 1.4),
        "Total": (100, 90, 1.2),
        "Edit": (80, 75, 1.0),
    }
    ctx["cart_column_specs"] = cart_column_specs
    for col, (width, minwidth, _weight) in cart_column_specs.items():
        cart_tree.heading(col, text=col)
        cart_tree.column(col, width=width, minwidth=minwidth, anchor="center", stretch=False)
    cart_tree.tag_configure("oddrow", background="#ffffff", foreground="#000000")
    cart_tree.tag_configure("evenrow", background="#e0f2fe", foreground="#000000")
    cart_tree.bind("<Configure>", lambda event: (
        pos_functions.auto_fit_tree_columns(cart_tree, cart_column_specs),
        pos_functions.schedule_cart_buttons(ctx),
    ))
    cart_tree.bind("<MouseWheel>", lambda event: pos_functions.schedule_cart_buttons(ctx))
    cart_tree.bind("<ButtonRelease-1>", lambda event: pos_functions.schedule_cart_buttons(ctx))
    root.after_idle(lambda: (
        pos_functions.auto_fit_tree_columns(cart_tree, cart_column_specs),
        pos_functions.schedule_cart_buttons(ctx),
    ))
    root.after(250, lambda: (
        pos_functions.auto_fit_tree_columns(cart_tree, cart_column_specs),
        pos_functions.schedule_cart_buttons(ctx),
    ))

    # Show the running total and checkout controls.
    global total_label
    total_label = tk.Label(
        left_frame,
        text=f"Amount Due: {pos_functions.format_money_value(0)}",
        font=("Arial", 21, "bold"),
        bg=CART_PANEL_BG,
        fg="#991b1b",
    )
    ctx["total_label"] = total_label
    total_label.pack(fill="x", pady=(8, 6))

    checkout_button_frame = tk.Frame(left_frame, bg=CART_PANEL_BG)
    checkout_button_frame.pack(fill="x", pady=(0, 6))
    checkout_button_inner = tk.Frame(checkout_button_frame, bg=CART_PANEL_BG)
    checkout_button_inner.pack(fill="x")
    clear_cart_btn = tk.Button(
        checkout_button_inner,
        text="Clear Cart",
        bg="#dc3545",
        fg="white",
        activebackground="#b91c1c",
        activeforeground="white",
        font=("Arial", 16, "bold"),
        command=lambda: pos_functions.clear_cart(ctx),
        padx=15,
        pady=12,
        **BUTTON_BORDER,
    )
    clear_cart_btn.pack(side="left", fill="x", expand=True, padx=(0, 5))
    pay_checkout_btn = tk.Button(
        checkout_button_inner,
        text="Pay / Checkout",
        bg="#ffc107",
        fg="black",
        activebackground="#eab308",
        activeforeground="black",
        font=("Arial", 16, "bold"),
        command=lambda: pos_functions.open_payment_modal(ctx),
        padx=15,
        pady=12,
        **BUTTON_BORDER,
    )
    pay_checkout_btn.pack(side="left", fill="x", expand=True, padx=(5, 0))

    # Right Frame - Inventory
    # Build the inventory search, sort, and summary controls.
    right_outer = tk.Frame(main_frame, bg=DASHBOARD_CONTENT_BG)
    right_outer.pack(side="right", fill="both", expand=True, padx=(5, 0))

    inventory_controls_frame = tk.Frame(right_outer, bg=DASHBOARD_CONTENT_BG)
    inventory_controls_frame.pack(fill="x", pady=(0, 6))

    tk.Label(inventory_controls_frame, text="Search Inventory:", bg=DASHBOARD_CONTENT_BG, font=("Arial", 13, "bold")).pack(side=tk.LEFT, padx=(0, 6))
    search_entry = tk.Entry(inventory_controls_frame, width=22, font=("Arial", 14), bd=2, relief="solid")
    ctx["search_entry"] = search_entry
    search_entry.pack(side=tk.LEFT, padx=(0, 10), ipady=2)
    search_entry.bind("<KeyRelease>", lambda e: pos_functions.load_inventory(ctx, search_entry.get()))

    tk.Label(inventory_controls_frame, text="Sort By:", bg=DASHBOARD_CONTENT_BG, font=("Arial", 13, "bold")).pack(side=tk.LEFT, padx=(0, 6))
    sort_menu = ttk.Combobox(
        inventory_controls_frame,
        textvariable=sort_var,
        values=["Name", "Newest"],
        state="readonly",
        width=10,
        font=("Arial", 14)
    )
    sort_menu.pack(side=tk.LEFT, ipady=2)

    tk.Button(
        inventory_controls_frame,
        text="Summary",
        bg="#8b5cf6",
        fg="white",
        activebackground="#7c3aed",
        activeforeground="white",
        font=("Arial", 13, "bold"),
        command=lambda: open_pos_summary(root),
        padx=14,
        pady=5,
        **BUTTON_BORDER,
    ).pack(side=tk.LEFT, padx=(10, 0))

    inventory_fullscreen = tk.BooleanVar(value=False)
    other_items_fullscreen = tk.BooleanVar(value=False)

    sort_menu.bind("<<ComboboxSelected>>", lambda e: pos_functions.load_inventory(ctx, search_entry.get()))
    pos_refresh_callback = lambda: pos_functions.load_inventory(ctx, search_entry.get())

    # Build the inventory table container and fullscreen control.
    right_frame = tk.Frame(right_outer, bg="white", padx=10, pady=10)
    right_frame.pack(fill="both", expand=True)
    inventory_header = tk.Frame(right_frame, bg="#dbeafe", bd=1, relief="solid")
    inventory_header.pack(fill="x", pady=(0, 10))
    tk.Label(
        inventory_header,
        text="Items In Inventory",
        font=("Arial", 18, "bold"),
        bg="#dbeafe",
        fg="#1e40af"
    ).pack(side="left", padx=12, pady=8)
    fullscreen_btn = tk.Button(
        inventory_header,
        text="Full Screen Display",
        bg="#0f766e",
        fg="white",
        activebackground="#0f766e",
        activeforeground="white",
        font=("Arial", 13, "bold"),
        command=lambda: toggle_inventory_fullscreen(),
        padx=14,
        pady=6,
        **BUTTON_BORDER,
    )
    fullscreen_btn.pack(side="right", padx=10, pady=6)

    inventory_columns = {
        "ID": (60, 55, 0.7),
        "Name": (205, 150, 2.4),
        "Unit": (105, 90, 1.1),
        "Quantity": (125, 105, 1.3),
        "Price": (115, 100, 1.3),
        "Add": (110, 100, 1.2),
    }
    ctx["inventory_column_specs"] = inventory_columns

    def refresh_inventory_table_layout():
        # Resize both inventory tables and reposition their Add buttons.
        pos_functions.auto_fit_tree_columns(chb_inv_tree, inventory_columns)
        pos_functions.auto_fit_tree_columns(inv_tree, inventory_columns)
        pos_functions.schedule_inventory_buttons(ctx)

    def create_inventory_section(parent, title, height, include_fullscreen=False):
        # Create one inventory section with a labeled table and optional fullscreen button.
        section = tk.Frame(parent, bg="white")
        section.pack(fill="x", pady=(0, 10))
        header = tk.Frame(section, bg="white")
        header.pack(fill="x", pady=(0, 4))
        tk.Label(header, text=title, font=("Arial", 15, "bold"), bg="white", fg="#1e40af").pack(side="left")
        if include_fullscreen:
            other_fullscreen_btn = tk.Button(
                header,
                text="Full Screen",
                bg="#0f766e",
                fg="white",
                activebackground="#0f766e",
                activeforeground="white",
                font=("Arial", 11, "bold"),
                command=lambda: toggle_other_items_fullscreen(),
                padx=10,
                pady=3,
                **BUTTON_BORDER,
            )
            other_fullscreen_btn.pack(side="right")
            ctx["other_fullscreen_btn"] = other_fullscreen_btn
        table_frame = tk.Frame(section, bg="white")
        table_frame.pack(fill="x", padx=(0, 8), pady=(0, 8))
        table_frame.grid_columnconfigure(0, weight=1)
        table_frame.grid_rowconfigure(0, weight=1)
        tree = ttk.Treeview(
            table_frame,
            columns=("ID","Name","Unit","Quantity","Price","Add"),
            show="headings",
            style="Pos.Treeview",
            height=height,
        )
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=tree.yview)
        x_scroll = ttk.Scrollbar(table_frame, orient="horizontal", command=tree.xview)
        y_scroll.configure(command=lambda *args: (tree.yview(*args), pos_functions.schedule_inventory_buttons(ctx)))
        x_scroll.configure(command=lambda *args: (tree.xview(*args), pos_functions.schedule_inventory_buttons(ctx)))
        tree.configure(
            yscrollcommand=lambda *args: (y_scroll.set(*args), pos_functions.schedule_inventory_buttons(ctx)),
            xscrollcommand=lambda *args: (x_scroll.set(*args), pos_functions.schedule_inventory_buttons(ctx)),
        )
        tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        tk.Frame(table_frame, bg="white", width=16, height=16).grid(row=1, column=1, sticky="nsew")
        for col, (width, minwidth, _weight) in inventory_columns.items():
            heading_text = "Selling Price" if col == "Price" else col
            heading_text = "Add to Cart" if col == "Add" else heading_text
            heading_text = "Quantity Available" if col == "Quantity" else heading_text
            tree.heading(col, text=heading_text)
            tree.column(col, width=width, minwidth=minwidth, anchor="center", stretch=False)
        tree.tag_configure("oddrow", background="#ffffff", foreground="#000000")
        tree.tag_configure("evenrow", background="#bfdbfe", foreground="#000000")
        tree.tag_configure("emptyrow", background="#f8fafc", foreground="#64748b")
        tree.bind("<Configure>", lambda event, tree_widget=tree: (
            pos_functions.auto_fit_tree_columns(tree_widget, inventory_columns),
            pos_functions.schedule_inventory_buttons(ctx),
        ))
        tree.bind("<MouseWheel>", lambda event: pos_functions.schedule_inventory_buttons(ctx))
        tree.bind("<B1-Motion>", lambda event: pos_functions.schedule_inventory_buttons(ctx))
        tree.bind("<ButtonRelease-1>", lambda event: pos_functions.schedule_inventory_buttons(ctx))
        tree.bind("<Double-1>", lambda event, tree_widget=tree: pos_functions.open_add_to_cart_modal(ctx, event, tree_widget=tree_widget))
        return section, table_frame, tree

    # Create separate inventory sections for CHB and other items.
    global chb_inv_tree, inv_tree
    chb_inv_section, chb_inv_table_frame, chb_inv_tree = create_inventory_section(right_frame, "CHB Items", 3)
    inv_section, inv_table_frame, inv_tree = create_inventory_section(right_frame, "Other Items", 5, include_fullscreen=True)
    inv_section.pack_configure(fill="both", expand=True, pady=(0, 14))
    inv_table_frame.pack_configure(fill="both", expand=True)
    inventory_no_results_label = tk.Label(
        inv_table_frame,
        text="No matching product found.",
        font=("Arial", 16, "bold"),
        bg="#fef2f2",
        fg="#dc2626",
        padx=18,
        pady=10,
        bd=1,
        relief="solid",
    )
    ctx["chb_inv_tree"] = chb_inv_tree
    ctx["inv_tree"] = inv_tree
    ctx["inventory_no_results_label"] = inventory_no_results_label

    def refresh_cart_table_layout():
        # Resize the cart table and reposition edit buttons.
        pos_functions.auto_fit_tree_columns(cart_tree, cart_column_specs)
        pos_functions.schedule_cart_buttons(ctx)

    def restore_cart_table_size():
        # Return the cart table to its standard split-screen size.
        cart_table_frame.pack_configure(fill="x", expand=False, pady=(3, 4))
        cart_table_frame.configure(height=270)
        cart_table_frame.pack_propagate(False)
        checkout_button_frame.pack_configure(pady=(0, 6))
        checkout_button_inner.pack_configure(fill="x")
        clear_cart_btn.pack_configure(fill="x", expand=True, padx=(0, 5), ipadx=0)
        pay_checkout_btn.pack_configure(fill="x", expand=True, padx=(5, 0), ipadx=0)
        cart_tree._fill_available_width = False
        for button in (clear_cart_btn, pay_checkout_btn):
            button.config(font=("Arial", 16, "bold"), pady=12)
        cart_fullscreen_btn.config(text="Full Screen", bg="#2563eb", activebackground="#1d4ed8")
        cart_fullscreen.set(False)

    def show_cart_panel():
        # Restore the normal cart-and-inventory split layout.
        left_frame.pack_forget()
        right_outer.pack_forget()
        restore_cart_table_size()
        left_frame.pack(side="left", fill="both", expand=False, padx=(0, 5))
        left_frame.configure(width=620)
        left_frame.pack_propagate(False)
        right_outer.pack(side="right", fill="both", expand=True, padx=(5, 0))
        root.after(50, refresh_cart_table_layout)

    def hide_cart_panel():
        # Hide the cart panel so inventory can use the full window width.
        left_frame.pack_forget()
        right_outer.pack_forget()
        restore_cart_table_size()
        right_outer.pack(side="right", fill="both", expand=True, padx=0)

    def show_cart_only():
        # Expand the cart panel to fullscreen mode.
        left_frame.pack_forget()
        right_outer.pack_forget()
        cart_table_frame.pack_configure(fill="both", expand=True, pady=(5, 0))
        cart_tree._fill_available_width = True
        checkout_button_frame.pack_configure(pady=(0, 48))
        checkout_button_inner.pack_configure(fill="none")
        clear_cart_btn.pack_configure(fill="none", expand=False, padx=(0, 10), ipadx=80)
        pay_checkout_btn.pack_configure(fill="none", expand=False, padx=(10, 0), ipadx=80)
        for button in (clear_cart_btn, pay_checkout_btn):
            button.config(font=("Arial", 15, "bold"), pady=8)
        cart_fullscreen_btn.config(text="Exit Full Screen", bg="#334155", activebackground="#334155")
        cart_fullscreen.set(True)
        left_frame.pack(side="left", fill="both", expand=True, padx=0)
        left_frame.pack_propagate(True)
        root.after(50, refresh_cart_table_layout)

    def restore_other_items_section():
        # Restore the CHB section when exiting other-items fullscreen mode.
        if not other_items_fullscreen.get():
            return
        chb_inv_section.pack_forget()
        inv_section.pack_forget()
        chb_inv_section.pack(fill="x", pady=(0, 10))
        inv_section.pack(fill="both", expand=True, pady=(0, 14))
        inv_table_frame.pack_configure(fill="both", expand=True)
        inv_tree._fill_available_width = bool(inventory_fullscreen.get())
        ctx["other_fullscreen_btn"].config(text="Full Screen", bg="#0f766e", activebackground="#0f766e")
        other_items_fullscreen.set(False)

    def toggle_inventory_fullscreen():
        # Toggle fullscreen mode for the full inventory area.
        if inventory_fullscreen.get():
            show_cart_panel()
            for tree_widget in (chb_inv_tree, inv_tree):
                tree_widget._fill_available_width = False
            fullscreen_btn.config(text="Full Screen Display", bg="#0f766e", activebackground="#0f766e")
            inventory_fullscreen.set(False)
        else:
            if cart_fullscreen.get():
                show_cart_panel()
            restore_other_items_section()
            hide_cart_panel()
            for tree_widget in (chb_inv_tree, inv_tree):
                tree_widget._fill_available_width = True
            fullscreen_btn.config(text="Exit Full Screen", bg="#334155", activebackground="#334155")
            inventory_fullscreen.set(True)
        root.after(50, refresh_inventory_table_layout)

    def toggle_other_items_fullscreen():
        # Toggle fullscreen mode for only the other-items inventory table.
        if other_items_fullscreen.get():
            restore_other_items_section()
        else:
            if cart_fullscreen.get():
                show_cart_panel()
            if inventory_fullscreen.get():
                show_cart_panel()
                for tree_widget in (chb_inv_tree, inv_tree):
                    tree_widget._fill_available_width = False
                fullscreen_btn.config(text="Full Screen Display", bg="#0f766e", activebackground="#0f766e")
                inventory_fullscreen.set(False)
            chb_inv_section.pack_forget()
            inv_section.pack_configure(fill="both", expand=True, pady=(0, 14))
            inv_table_frame.pack_configure(fill="both", expand=True)
            inv_tree._fill_available_width = True
            ctx["other_fullscreen_btn"].config(text="Exit Full Screen", bg="#334155", activebackground="#334155")
            other_items_fullscreen.set(True)
        root.after(50, refresh_inventory_table_layout)

    def toggle_cart_fullscreen():
        # Toggle fullscreen mode for the checkout cart.
        if cart_fullscreen.get():
            show_cart_panel()
        else:
            if inventory_fullscreen.get():
                for tree_widget in (chb_inv_tree, inv_tree):
                    tree_widget._fill_available_width = False
                fullscreen_btn.config(text="Full Screen Display", bg="#0f766e", activebackground="#0f766e")
                inventory_fullscreen.set(False)
            restore_other_items_section()
            show_cart_only()
        root.after(50, refresh_inventory_table_layout)

    # Schedule initial table fitting after Tk finishes drawing widgets.
    root.after_idle(lambda: (
        pos_functions.auto_fit_tree_columns(chb_inv_tree, inventory_columns),
        pos_functions.auto_fit_tree_columns(inv_tree, inventory_columns),
        pos_functions.schedule_inventory_buttons(ctx),
    ))
    root.after(250, lambda: (
        pos_functions.auto_fit_tree_columns(chb_inv_tree, inventory_columns),
        pos_functions.auto_fit_tree_columns(inv_tree, inventory_columns),
        pos_functions.schedule_inventory_buttons(ctx),
    ))

    # Wire cart editing and load initial inventory data.
    cart_tree.bind("<Double-1>", lambda event: pos_functions.open_cart_item_modal(ctx, event))

    pos_functions.load_inventory(ctx)
    if parent is None:
        root.mainloop()
    return root


if __name__ == "__main__":
    # Allow this module to run the POS window directly during manual testing.
    open_pos()
