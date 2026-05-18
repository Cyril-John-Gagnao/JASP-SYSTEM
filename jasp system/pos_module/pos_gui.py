import tkinter as tk
from tkinter import ttk

from pos_module import pos_functions
from pos_module.pos_database import initialize_pos_database
from pos_module.pos_summary import open_pos_summary
from window_utils import enable_centered_toplevels
from jasp_theme import (
    DASHBOARD_CONTENT_BG,
    DASHBOARD_HEADER_BG,
    DASHBOARD_HEADER_BORDER,
    DASHBOARD_HEADER_FG,
    add_header_logo,
)

enable_centered_toplevels()

pos_refresh_callback = None
BUTTON_BORDER = {
    "bd": 2,
    "relief": "solid",
    "highlightthickness": 1,
    "highlightbackground": "black",
    "highlightcolor": "black",
}

# ==================== POS WINDOW ====================
def open_pos():
    global pos_refresh_callback
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
    root = tk.Toplevel()
    root.title("POS System")
    root.state("zoomed")  # Fullscreen
    root.configure(bg=DASHBOARD_CONTENT_BG)
    root.option_add("*TCombobox*Listbox.font", ("Arial", 17))

    root.transient()        # link to main window
    root.grab_set()         # lock focus to POS
    ctx["root"] = root
    root.protocol("WM_DELETE_WINDOW", lambda: (globals().__setitem__("pos_refresh_callback", None), root.destroy()))

    # ====== Header ======
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

    tk.Button(header_frame, text="← Back", bg="#dc3545", fg="white", font=("Arial", 13, "bold"),
              command=lambda: (globals().__setitem__("pos_refresh_callback", None), root.destroy()), padx=12, pady=8, **BUTTON_BORDER).pack(side=tk.RIGHT, padx=6)
    tk.Button(header_frame, text="🔄 Refresh", bg="#16a34a", fg="white", font=("Arial", 13, "bold"),
              command=lambda: pos_functions.load_inventory(ctx, search_entry.get()), padx=12, pady=8, **BUTTON_BORDER).pack(side=tk.RIGHT, padx=6)

    # ====== Main Frame ======
    main_frame = tk.Frame(root, bg=DASHBOARD_CONTENT_BG)
    main_frame.pack(fill="both", expand=True, padx=10, pady=5)

    # Left Frame - Cart / POS
    left_frame = tk.Frame(main_frame, bg=DASHBOARD_CONTENT_BG, padx=10, pady=10)
    left_frame.pack(side="left", fill="both", expand=True, padx=(0, 5))
    left_frame.configure(width=620)
    left_frame.pack_propagate(False)

    tk.Label(left_frame, text="Checkout Cart", font=("Arial", 17, "bold"), bg=DASHBOARD_CONTENT_BG).pack(pady=5)

    cart_frame = tk.Frame(left_frame, bg=DASHBOARD_CONTENT_BG)
    cart_frame.pack(pady=5)
    tk.Label(cart_frame, text=" You can also Double-click an item to select it.", font=("Arial", 13),
             bg=DASHBOARD_CONTENT_BG).pack()
    # Cart Treeview
    cart_table_frame = tk.Frame(left_frame, bg=DASHBOARD_CONTENT_BG)
    cart_table_frame.pack(fill="x", pady=5)
    cart_table_frame.configure(height=315)
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
    tk.Frame(cart_table_frame, bg=DASHBOARD_CONTENT_BG, width=16, height=16).grid(row=1, column=1, sticky="nsew")
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

    global total_label
    total_label = tk.Label(
        left_frame,
        text="Amount Due: P0.00",
        font=("Arial", 22, "bold"),
        bg=DASHBOARD_CONTENT_BG,
        fg="#991b1b",
    )
    ctx["total_label"] = total_label
    total_label.pack(fill="x", pady=(18, 10))

    # Right Frame - Search + Inventory
    right_outer = tk.Frame(main_frame, bg=DASHBOARD_CONTENT_BG)
    right_outer.pack(side="right", fill="both", expand=True, padx=(5, 0))

    controls_frame = tk.Frame(right_outer, bg=DASHBOARD_CONTENT_BG)
    controls_frame.pack(fill="x", pady=(0, 6))

    tk.Label(controls_frame, text="Search Inventory:", bg=DASHBOARD_CONTENT_BG, font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=(0, 8))
    search_entry = tk.Entry(controls_frame, width=22, font=("Arial", 15), bd=2, relief="solid")
    ctx["search_entry"] = search_entry
    search_entry.pack(side=tk.LEFT, padx=(0, 8), ipady=3)
    search_entry.bind("<KeyRelease>", lambda e: pos_functions.load_inventory(ctx, search_entry.get()))

    tk.Label(controls_frame, text="Sort By:", bg=DASHBOARD_CONTENT_BG, font=("Arial", 14, "bold")).pack(side=tk.LEFT, padx=(0, 8))

    sort_var = tk.StringVar(value="Name")
    ctx["sort_var"] = sort_var
    sort_menu = ttk.Combobox(
        controls_frame,
        textvariable=sort_var,
        values=["Name", "Newest"],
        state="readonly",
        width=12,
        font=("Arial", 15)
    )
    sort_menu.pack(side=tk.LEFT, ipady=3)

    tk.Button(
        controls_frame,
        text="Summary",
        bg="#8b5cf6",
        fg="white",
        activebackground="#7c3aed",
        activeforeground="white",
        font=("Arial", 13, "bold"),
        command=lambda: open_pos_summary(root),
        padx=14,
        pady=6,
        **BUTTON_BORDER,
    ).pack(side=tk.RIGHT, padx=(10, 0))

    sort_menu.bind("<<ComboboxSelected>>", lambda e: pos_functions.load_inventory(ctx, search_entry.get()))
    pos_refresh_callback = lambda: pos_functions.load_inventory(ctx, search_entry.get())

    right_frame = tk.Frame(right_outer, bg="white", padx=10, pady=10)
    right_frame.pack(fill="both", expand=True)
    tk.Label(right_frame, text="Items In Inventory", font=("Arial", 18, "bold"), bg="white").pack(pady=5)

    inventory_columns = {
        "ID": (60, 55, 0.7),
        "Name": (205, 150, 2.4),
        "Unit": (105, 90, 1.1),
        "Quantity": (125, 105, 1.3),
        "Price": (115, 100, 1.3),
        "Add": (110, 100, 1.2),
    }
    ctx["inventory_column_specs"] = inventory_columns

    def create_inventory_section(parent, title, height):
        section = tk.Frame(parent, bg="white")
        section.pack(fill="x", pady=(0, 10))
        tk.Label(section, text=title, font=("Arial", 15, "bold"), bg="white", fg="#1e40af").pack(anchor="w", pady=(0, 4))
        table_frame = tk.Frame(section, bg="white")
        table_frame.pack(fill="x")
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
        return tree

    global chb_inv_tree, inv_tree
    chb_inv_tree = create_inventory_section(right_frame, "CHB Items", 3)
    inv_tree = create_inventory_section(right_frame, "Other Items", 5)
    ctx["chb_inv_tree"] = chb_inv_tree
    ctx["inv_tree"] = inv_tree
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

    checkout_button_frame = tk.Frame(right_frame, bg="white")
    checkout_button_frame.pack(side="bottom", pady=(12, 10))
    tk.Button(checkout_button_frame, text="Clear Cart", bg="#dc3545", fg="white", width=25, font=("Arial", 14, "bold"),
              command=lambda: pos_functions.clear_cart(ctx), padx=15, pady=10, **BUTTON_BORDER).pack(side="left", padx=5)
    tk.Button(checkout_button_frame, text="Pay / Checkout", bg="#ffc107", fg="black", width=25, font=("Arial", 14, "bold"),
              command=lambda: pos_functions.open_payment_modal(ctx), padx=15, pady=10, **BUTTON_BORDER).pack(side="left", padx=5)

    cart_tree.bind("<Double-1>", lambda event: pos_functions.open_cart_item_modal(ctx, event))

    pos_functions.load_inventory(ctx)
    root.mainloop()


if __name__ == "__main__":
    open_pos()
