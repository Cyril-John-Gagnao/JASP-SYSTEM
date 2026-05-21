import tkinter as tk
from tkinter import ttk

from . import user_database
from . import user_functions
from jasp_theme import (
    DASHBOARD_CONTENT_BG,
    DASHBOARD_HEADER_BG,
    DASHBOARD_HEADER_BORDER,
    DASHBOARD_HEADER_FG,
    add_header_logo,
)


# Define the user-management color palette and shared button border style.
BG = DASHBOARD_CONTENT_BG
CARD = "#ffffff"
PRIMARY = "#2563eb"
SUCCESS = "#16a34a"
WARNING = "#f59e0b"
DANGER = "#dc2626"
TEXT = "#0f172a"
HEADER_BG = DASHBOARD_HEADER_BG
FORM_BG = "#fef3c7"

BUTTON_BORDER = {
    "bd": 2,
    "relief": "solid",
    "highlightthickness": 1,
    "highlightbackground": "black",
    "highlightcolor": "black",
}

# Define the columns shown in the user list.
USER_COLUMNS = ("ID", "Username", "Contact Number", "Role", "Edit", "Delete")


def open_user_management(root):
    # Confirm access before clearing the current dashboard screen.
    try:
        from main_dashboard import session
        active_role = session.current_user.get("role") or user_functions.current_user_role
    except Exception:
        active_role = user_functions.current_user_role
    if active_role != "Admin":
        user_functions.show_user_error(root, "Error", "Access denied. Unauthorized action.")
        return

    # Open the user database before clearing the screen so failures keep the dashboard visible.
    try:
        conn, cursor = user_database.open_user_connection()
        user_database.setup_user_database(conn, cursor)
    except Exception as exc:
        user_functions.show_user_error(root, "Error", f"Unable to open User Management.\n\n{exc}")
        return

    # Clear the current screen and prepare the user-management page.
    for widget in list(root.winfo_children()):
        try:
            if widget.winfo_exists():
                widget.destroy()
        except tk.TclError:
            pass

    root.title("User Management")
    root.configure(bg=BG)
    root.option_add("*TCombobox*Listbox.font", ("Arial", 15))

    selected_user_id = tk.StringVar()
    search_var = tk.StringVar()
    role_filter_var = tk.StringVar(value="All Users")
    selected_row_id = tk.StringVar()
    table_buttons = []

    # Build the page header with refresh and back actions.
    header = tk.Frame(root, bg=HEADER_BG, padx=14, pady=10, highlightthickness=1, highlightbackground=DASHBOARD_HEADER_BORDER)
    header.pack(fill="x", padx=20, pady=10)
    header.columnconfigure(0, weight=1)
    header.columnconfigure(1, weight=0)

    title_frame = tk.Frame(header, bg=HEADER_BG)
    title_frame.grid(row=0, column=0, sticky="w")
    add_header_logo(title_frame, HEADER_BG, size=52)

    tk.Label(
        title_frame,
        text="USER MANAGEMENT",
        font=("Arial", 22, "bold"),
        bg=HEADER_BG,
        fg=DASHBOARD_HEADER_FG
    ).pack(side="left")

    header_buttons = tk.Frame(header, bg=HEADER_BG)
    header_buttons.grid(row=0, column=1, sticky="e")

    tk.Button(
        header_buttons,
        text="🔄 Refresh",
        command=lambda: refresh_display(),
        bg=SUCCESS,
        fg="white",
        font=("Arial", 11, "bold"),
        padx=12,
        pady=6,
        **BUTTON_BORDER
    ).grid(row=0, column=0, padx=(0, 8))

    tk.Button(
        header_buttons,
        text="← Back",
        command=lambda: user_functions.go_back_to_dashboard(root, conn),
        bg=PRIMARY,
        fg="white",
        font=("Arial", 11, "bold"),
        padx=12,
        pady=6,
        **BUTTON_BORDER
    ).grid(row=0, column=1)

    # Build the main two-column layout.
    main = tk.Frame(root, bg=BG)
    main.pack(fill="both", expand=True, padx=20, pady=10)
    main.columnconfigure(0, weight=7)
    main.columnconfigure(1, weight=3)
    main.rowconfigure(0, weight=1)

    left = tk.Frame(main, bg=CARD)
    left.grid(row=0, column=0, sticky="nsew", padx=(10, 8), pady=10)
    left.columnconfigure(0, weight=1)
    left.rowconfigure(2, weight=1)

    tk.Label(left, text="USER LIST", font=("Arial", 18, "bold"), bg=CARD, fg=PRIMARY).grid(row=0, column=0, sticky="w", padx=10, pady=(10, 8))

    # Build search and role filter controls for the user list.
    search_frame = tk.Frame(left, bg=CARD)
    search_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
    tk.Label(search_frame, text="Search:", font=("Arial", 15, "bold"), bg=CARD, fg=TEXT).pack(side="left", padx=(0, 8))
    search_entry = tk.Entry(search_frame, textvariable=search_var, font=("Arial", 15), width=22, bd=1, relief="solid")
    search_entry.pack(side="left", ipady=4)
    search_entry.bind("<KeyRelease>", lambda _event: refresh_display())
    tk.Label(search_frame, text="Sort by Role:", font=("Arial", 15, "bold"), bg=CARD, fg=TEXT).pack(side="left", padx=(18, 8))
    role_filter = ttk.Combobox(
        search_frame,
        textvariable=role_filter_var,
        values=["All Users", "Admin", "Cashier"],
        state="readonly",
        font=("Arial", 15),
        width=13
    )
    role_filter.pack(side="left", ipady=3)
    role_filter.bind("<<ComboboxSelected>>", lambda _event: refresh_display())

    # Build the user table area with scrollbars.
    display_frame = tk.Frame(left, bg=CARD)
    display_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 10))
    display_frame.columnconfigure(0, weight=1)
    display_frame.rowconfigure(0, weight=1)

    # Configure the Treeview style for the user list.
    style = ttk.Style()
    style.configure("UserManagement.Treeview", font=("Arial", 14), rowheight=38)
    style.configure("UserManagement.Treeview.Heading", font=("Arial", 14, "bold"))
    style.map("UserManagement.Treeview", background=[("selected", "#93c5fd")], foreground=[("selected", "#0f172a")])

    user_tree = ttk.Treeview(display_frame, columns=USER_COLUMNS, show="headings", selectmode="browse", style="UserManagement.Treeview")
    y_scrollbar = ttk.Scrollbar(display_frame, orient="vertical", command=user_tree.yview)
    x_scrollbar = ttk.Scrollbar(display_frame, orient="horizontal", command=user_tree.xview)
    user_tree.configure(yscrollcommand=y_scrollbar.set, xscrollcommand=x_scrollbar.set)
    user_tree.grid(row=0, column=0, sticky="nsew")
    y_scrollbar.grid(row=0, column=1, sticky="ns")
    x_scrollbar.grid(row=1, column=0, sticky="ew")

    column_widths = {
        "ID": 90,
        "Username": 260,
        "Contact Number": 250,
        "Role": 150,
        "Edit": 120,
        "Delete": 120,
    }
    for column in USER_COLUMNS:
        user_tree.heading(column, text=column, anchor="w")
        user_tree.column(column, width=column_widths[column], minwidth=column_widths[column], anchor="w", stretch=True)

    user_tree.tag_configure("oddrow", background="#ffffff")
    user_tree.tag_configure("evenrow", background="#e0f2fe")

    def clear_table_buttons():
        # Remove overlay Edit/Delete buttons before redrawing them.
        for button in table_buttons:
            if button.winfo_exists():
                button.destroy()
        table_buttons.clear()

    def schedule_table_buttons():
        # Queue table button rendering after the Treeview layout updates.
        user_tree.after_idle(render_table_buttons)

    def render_table_buttons():
        # Place Edit and Delete buttons over their table cells.
        clear_table_buttons()
        user_tree.update_idletasks()
        for item in user_tree.get_children():
            values = user_tree.item(item, "values")
            if not values:
                continue
            user_id = values[0]
            update_bbox = user_tree.bbox(item, "Edit")
            delete_bbox = user_tree.bbox(item, "Delete")
            if update_bbox:
                x, y, width, height = update_bbox
                button = tk.Button(
                    user_tree,
                    text="Save" if str(selected_user_id.get()) == str(user_id) else "Edit",
                    command=lambda item_id=user_id: table_update_user(item_id),
                    bg=PRIMARY,
                    fg="white",
                    font=("Arial", 10, "bold"),
                    bd=1,
                    relief="solid"
                )
                button.place(x=x + 5, y=y + 5, width=max(width - 10, 70), height=max(height - 10, 24))
                table_buttons.append(button)
            if delete_bbox:
                x, y, width, height = delete_bbox
                button = tk.Button(
                    user_tree,
                    text="Delete",
                    command=lambda item_id=user_id: user_functions.delete_user_by_id(
                        conn,
                        cursor,
                        item_id,
                        selected_user_id,
                        username_entry,
                        password_entry,
                        confirm_password_entry,
                        role_var,
                        contact_entry,
                        refresh_display
                    ),
                    bg=DANGER,
                    fg="white",
                    font=("Arial", 10, "bold"),
                    bd=1,
                    relief="solid"
                )
                button.place(x=x + 5, y=y + 5, width=max(width - 10, 70), height=max(height - 10, 24))
                table_buttons.append(button)

    # Build the right-side form panel for creating and editing users.
    right = tk.Frame(main, bg=FORM_BG, highlightthickness=1, highlightbackground="#d97706", padx=18, pady=16)
    right.grid(row=0, column=1, sticky="nsew", padx=(8, 10), pady=10)

    tk.Label(right, text="User Form", font=("Arial", 18, "bold"), bg=FORM_BG, fg=PRIMARY).pack(pady=(0, 14))

    form = tk.Frame(right, bg=FORM_BG)
    form.pack(fill="x", pady=6)

    tk.Label(form, text="Username", bg=FORM_BG, font=("Arial", 13, "bold"), fg=TEXT).grid(row=0, column=0, sticky="w", pady=8)
    username_entry = tk.Entry(form, font=("Arial", 13), width=24, bd=1, relief="solid")
    username_entry.grid(row=0, column=1, sticky="ew", pady=8, padx=(12, 0), ipady=3)

    tk.Label(form, text="Password", bg=FORM_BG, font=("Arial", 13, "bold"), fg=TEXT).grid(row=1, column=0, sticky="w", pady=8)
    password_entry = tk.Entry(form, font=("Arial", 13), show="*", width=24, bd=1, relief="solid")
    password_entry.grid(row=1, column=1, sticky="ew", pady=8, padx=(12, 0), ipady=3)

    tk.Label(form, text="Confirm Password", bg=FORM_BG, font=("Arial", 13, "bold"), fg=TEXT).grid(row=2, column=0, sticky="w", pady=8)
    confirm_password_entry = tk.Entry(form, font=("Arial", 13), show="*", width=24, bd=1, relief="solid")
    confirm_password_entry.grid(row=2, column=1, sticky="ew", pady=8, padx=(12, 0), ipady=3)

    tk.Label(
        form,
        text="Password fields are for new users only. Use Change Password for existing users.",
        bg=FORM_BG,
        fg="#92400e",
        font=("Arial", 10, "bold"),
        wraplength=280,
        justify="left",
    ).grid(row=3, column=0, columnspan=2, sticky="w", pady=(0, 6))

    tk.Label(form, text="Contact Number", bg=FORM_BG, font=("Arial", 13, "bold"), fg=TEXT).grid(row=4, column=0, sticky="w", pady=8)
    contact_entry = tk.Entry(form, font=("Arial", 13), width=24, bd=1, relief="solid")
    contact_entry.grid(row=4, column=1, sticky="ew", pady=8, padx=(12, 0), ipady=3)

    tk.Label(form, text="Role", bg=FORM_BG, font=("Arial", 13, "bold"), fg=TEXT).grid(row=5, column=0, sticky="w", pady=8)
    role_var = tk.StringVar(value="Select Role")
    ttk.Combobox(
        form,
        textvariable=role_var,
        values=["Admin", "Cashier"],
        state="readonly",
        font=("Arial", 15),
        width=18
    ).grid(row=5, column=1, sticky="ew", pady=8, padx=(12, 0), ipady=3)
    form.columnconfigure(1, weight=1)

    def load_user(user_id):
        # Select a user and load the account details into the form.
        selected_row_id.set(str(user_id))
        user_functions.load_user_by_id(
            cursor,
            user_id,
            selected_user_id,
            username_entry,
            password_entry,
            confirm_password_entry,
            role_var,
            contact_entry
        )

    def table_update_user(user_id):
        # First click loads a user; second click saves changes for that user.
        if str(selected_user_id.get()) != str(user_id):
            load_user(user_id)
            return

        user_functions.update_user(
            conn,
            cursor,
            selected_user_id,
            username_entry,
            password_entry,
            confirm_password_entry,
            role_var,
            contact_entry,
            refresh_display
        )

    def on_user_select(_event=None):
        # Load the clicked table row into the form.
        selected = user_tree.selection()
        if not selected:
            return
        values = user_tree.item(selected[0], "values")
        if values:
            load_user(values[0])

    user_tree.bind("<<TreeviewSelect>>", on_user_select)

    def clear_user_selection():
        # Clear the selected table row and reset the form.
        user_functions.clear_user_form(
            username_entry,
            password_entry,
            confirm_password_entry,
            role_var,
            contact_entry,
            selected_user_id
        )
        selected_row_id.set("")
        user_tree.selection_remove(user_tree.selection())
        user_tree.focus("")

    def clear_on_empty_click(event):
        # Clear selection when clicking empty space outside controls.
        widget = event.widget
        widget_class = widget.winfo_class()
        if widget is user_tree:
            if user_tree.identify_row(event.y):
                return
            clear_user_selection()
            return

        ignored_classes = {
            "Button",
            "Entry",
            "TCombobox",
            "Treeview",
            "Scrollbar",
            "TScrollbar",
            "Label",
        }
        if widget_class in ignored_classes:
            return
        clear_user_selection()

    for empty_area in (root, main, left, display_frame, right, form):
        empty_area.bind("<Button-1>", clear_on_empty_click, add="+")

    def refresh_display():
        # Reload the table using the current search and role filters.
        search_text = search_var.get().strip().lower()
        selected_role = role_filter_var.get()
        users = []
        for user in user_database.get_users(cursor):
            username = user[1] or ""
            role = user[2] or ""
            contact_number = user[4] or ""
            if selected_role != "All Users" and role.lower() != selected_role.lower():
                continue
            if search_text and search_text not in username.lower() and search_text not in role.lower() and search_text not in contact_number.lower():
                continue
            users.append(user)
        selected_id = selected_row_id.get()
        # Clear and rebuild rows while preserving the selected user when possible.
        for item in user_tree.get_children():
            user_tree.delete(item)

        selected_iid = None
        for row_index, user in enumerate(users):
            user_id, username, role, _question, contact_number = user
            tag = "evenrow" if row_index % 2 else "oddrow"
            iid = user_tree.insert("", "end", values=(user_id, username, contact_number, role, "", ""), tags=(tag,))
            if str(user_id) == selected_id:
                selected_iid = iid

        if selected_iid:
            user_tree.selection_set(selected_iid)
            user_tree.focus(selected_iid)
        schedule_table_buttons()

    # Build form action buttons.
    btn = tk.Frame(right, bg=FORM_BG)
    btn.pack(pady=18, fill="x", padx=8)
    btn.bind("<Button-1>", clear_on_empty_click, add="+")

    tk.Button(
        btn,
        text="Create",
        command=lambda: user_functions.create_user(
            conn,
            cursor,
            username_entry,
            password_entry,
            confirm_password_entry,
            role_var,
            contact_entry,
            selected_user_id,
            refresh_display
        ),
        bg=SUCCESS,
        fg="white",
        font=("Arial", 14, "bold"),
        width=10,
        pady=8,
        **BUTTON_BORDER
    ).pack(fill="x", pady=5)

    tk.Button(
        btn,
        text="Change Password",
        command=lambda: user_functions.open_change_password_form(
            conn,
            cursor,
            root,
            selected_user_id
        ),
        bg=PRIMARY,
        fg="white",
        font=("Arial", 14, "bold"),
        width=10,
        pady=8,
        **BUTTON_BORDER
    ).pack(fill="x", pady=5)

    # Keep overlay buttons aligned during resizing and scrolling, then load data.
    user_tree.bind("<Configure>", lambda _event: schedule_table_buttons())
    user_tree.bind("<ButtonRelease-1>", lambda _event: schedule_table_buttons())
    user_tree.bind("<MouseWheel>", lambda _event: schedule_table_buttons())
    y_scrollbar.configure(command=lambda *args: (user_tree.yview(*args), schedule_table_buttons()))
    x_scrollbar.configure(command=lambda *args: (user_tree.xview(*args), schedule_table_buttons()))
    refresh_display()
