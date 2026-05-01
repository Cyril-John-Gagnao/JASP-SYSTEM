import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from .inventory_database import (
    CHB_ITEM_NAME,
    CHB_DEFAULT_UNIT,
    PREDEFINED_ITEMS,
    UNIT_OPTIONS,
    ensure_chb_item,
    normalize_predefined_units,
    fetch_items,
    count_items,
    log_restock,
    log_inventory_action,
    fetch_existing_item_for_stack,
    update_stacked_item,
    insert_item,
    update_item_record,
    restock_item_record,
    delete_item_record,
)


FORM_BG = "#fef3c7"
SAVE_GREEN = "#00c853"
CANCEL_RED = "#dc2626"
LOW_STOCK_ROW = "low_stock_row"
LOW_STOCK_LIMITS = {
    "cement": 20,
    "fine sand": 20,
    "chb blocks": 200,
}
DEFAULT_LOW_STOCK_LIMIT = 10


def show_inventory_error(parent, title, message):
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)

    tk.Frame(popup, bg=CANCEL_RED, height=12).pack(fill="x")

    content = tk.Frame(popup, bg="#ffffff", padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text=title,
        bg="#ffffff",
        fg=CANCEL_RED,
        font=("Arial", 28, "bold")
    ).pack(pady=(0, 14))

    tk.Label(
        content,
        text=message,
        bg="#ffffff",
        fg="#111827",
        font=("Arial", 17),
        wraplength=430,
        justify="center"
    ).pack(pady=(0, 28))

    def close_popup():
        popup.destroy()

    ok_btn = tk.Button(
        content,
        text="OK",
        command=close_popup,
        bg=CANCEL_RED,
        fg="white",
        activebackground="#b91c1c",
        font=("Arial", 15, "bold"),
        relief="flat",
        width=14,
        pady=9
    )
    ok_btn.pack()
    ok_btn.focus_set()

    popup.bind("<Return>", lambda _event: close_popup())
    popup.bind("<Escape>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    center_window(popup, 540, 290, parent)
    parent.wait_window(popup)


def show_inventory_success(parent, title, message):
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)

    tk.Frame(popup, bg=SAVE_GREEN, height=12).pack(fill="x")

    content = tk.Frame(popup, bg="#ffffff", padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text=title,
        bg="#ffffff",
        fg=SAVE_GREEN,
        font=("Arial", 28, "bold")
    ).pack(pady=(0, 14))

    tk.Label(
        content,
        text=message,
        bg="#ffffff",
        fg="#111827",
        font=("Arial", 17),
        wraplength=430,
        justify="center"
    ).pack(pady=(0, 28))

    def close_popup():
        popup.destroy()

    ok_btn = tk.Button(
        content,
        text="OK",
        command=close_popup,
        bg=SAVE_GREEN,
        fg="white",
        activebackground="#16a34a",
        font=("Arial", 15, "bold"),
        relief="flat",
        width=14,
        pady=9
    )
    ok_btn.pack()
    ok_btn.focus_set()

    popup.bind("<Return>", lambda _event: close_popup())
    popup.bind("<Escape>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    center_window(popup, 540, 290, parent)
    parent.wait_window(popup)


def low_stock_limit(item_name):
    return LOW_STOCK_LIMITS.get(str(item_name).strip().lower(), DEFAULT_LOW_STOCK_LIMIT)


def is_low_stock_item(item_name, quantity):
    try:
        quantity_value = int(float(quantity))
    except (TypeError, ValueError):
        return False
    return quantity_value <= low_stock_limit(item_name)


def inventory_row_tag(index, values):
    item_name = values[1] if len(values) > 1 else ""
    quantity = values[3] if len(values) > 3 else 0
    if is_low_stock_item(item_name, quantity):
        return LOW_STOCK_ROW
    return "blue_row" if index % 2 == 0 else "white_row"


def status_row_tag(index, status, item_name="", quantity=None):
    if item_name and quantity is not None and is_low_stock_item(item_name, quantity):
        return LOW_STOCK_ROW
    return "blue_row" if index % 2 == 0 else "white_row"


def view_items(conn, cursor, tree, filter_text="", sort_by="Latest Date", total_var=None):
    ensure_chb_item(conn, cursor)
    for row in tree.get_children():
        tree.delete(row)
    rows = fetch_items(cursor, filter_text, sort_by)
    for index, row in enumerate(rows):
        tag = inventory_row_tag(index, row)
        tree.insert("", tk.END, values=row, tags=(tag,))
    if total_var is not None:
        total_var.set(f"Total Items in Inventory: {count_items(cursor):,}")


def refresh_current_view(conn, cursor, tree, search_entry, sort_var=None, total_var=None):
    sort_by = sort_var.get() if sort_var is not None else "Latest Date"
    view_items(conn, cursor, tree, search_entry.get(), sort_by, total_var)


def sort_tree(tree, sort_state, column, numeric=False):
    data = [(tree.set(k, column), k) for k in tree.get_children("")]
    if numeric:
        def to_num(val):
            try:
                return float(val)
            except ValueError:
                return 0
        data = [(to_num(val), k) for val, k in data]
    ascending = not (sort_state["column"] == column and sort_state["ascending"])
    data.sort(reverse=not ascending)
    for index, (_, k) in enumerate(data):
        tree.move(k, "", index)
        values = tree.item(k, "values")
        tree.item(k, tags=(inventory_row_tag(index, values),))
    sort_state["column"] = column
    sort_state["ascending"] = ascending


def center_window(window, width=560, height=430, parent=None):
    window.update_idletasks()
    if parent and parent.winfo_exists():
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    else:
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def open_item_form(conn, cursor, inventory_window, tree, mode, item_values=None, refresh_view=None):
    form = tk.Toplevel(inventory_window)
    form.title("Add Item" if mode == "add" else "Edit Item")
    form.transient(inventory_window)
    form.grab_set()
    form.configure(bg=FORM_BG)
    form.resizable(False, False)
    form.option_add("*TCombobox*Listbox.font", ("Arial", 16))

    form_card = tk.Frame(form, bg=FORM_BG)
    form_card.pack(expand=True)

    tk.Label(form_card, text="Item Name", font=("Arial", 16, "bold"), bg=FORM_BG).grid(row=0, column=0, padx=18, pady=10, sticky="w")
    name_var = tk.StringVar()
    name_entry = tk.Entry(form_card, textvariable=name_var, width=28, font=("Arial", 16))
    name_entry.grid(row=0, column=1, pady=10)

    tk.Label(form_card, text="Measurement Unit", font=("Arial", 16, "bold"), bg=FORM_BG).grid(row=1, column=0, padx=18, pady=10, sticky="w")
    unit_var = tk.StringVar()
    unit_entry = ttk.Combobox(form_card, textvariable=unit_var, values=UNIT_OPTIONS, width=26, font=("Arial", 16))
    unit_entry.grid(row=1, column=1, pady=10)

    tk.Label(form_card, text="Quantity", font=("Arial", 16, "bold"), bg=FORM_BG).grid(row=2, column=0, padx=18, pady=10, sticky="w")
    quantity_entry = tk.Entry(form_card, width=28, font=("Arial", 16))
    quantity_entry.grid(row=2, column=1, pady=10)

    tk.Label(form_card, text="Selling Price", font=("Arial", 16, "bold"), bg=FORM_BG).grid(row=3, column=0, padx=18, pady=10, sticky="w")
    price_entry = tk.Entry(form_card, width=28, font=("Arial", 16))
    price_entry.grid(row=3, column=1, pady=10)

    tk.Label(form_card, text="Raw Price", font=("Arial", 16, "bold"), bg=FORM_BG).grid(row=4, column=0, padx=18, pady=10, sticky="w")
    raw_price_entry = tk.Entry(form_card, width=28, font=("Arial", 16))
    raw_price_entry.grid(row=4, column=1, pady=10)

    tk.Label(form_card, text="Status", font=("Arial", 16, "bold"), bg=FORM_BG).grid(row=5, column=0, padx=18, pady=10, sticky="w")
    status_var = tk.StringVar(value="Active")
    status_entry = ttk.Combobox(form_card, textvariable=status_var, values=["Active", "Inactive"], width=26, font=("Arial", 16), state="readonly")
    status_entry.grid(row=5, column=1, pady=10)

    def sync_unit_from_name(event=None):
        selected_item = name_var.get().strip()
        if selected_item in PREDEFINED_ITEMS:
            unit_var.set(PREDEFINED_ITEMS[selected_item])

    name_entry.bind("<KeyRelease>", sync_unit_from_name)
    name_entry.bind("<FocusOut>", sync_unit_from_name)

    if mode == "edit" and item_values:
        name_var.set(item_values[1])
        unit_var.set(item_values[2] if len(item_values) > 2 else "")
        quantity_entry.insert(0, item_values[3])
        price_entry.insert(0, item_values[4])
        raw_price_entry.insert(0, item_values[5])
        status_var.set(item_values[6] if len(item_values) > 6 and item_values[6] else "Active")

        if not unit_var.get() and item_values[1] in PREDEFINED_ITEMS:
            unit_var.set(PREDEFINED_ITEMS[item_values[1]])

        if item_values[1] == CHB_ITEM_NAME:
            name_entry.config(state="disabled")
            quantity_entry.config(state="disabled")
            raw_price_entry.config(state="disabled")
            unit_entry.config(state="disabled")
            unit_var.set(CHB_DEFAULT_UNIT)
            tk.Label(form_card, text="Quantity is auto from CHB production. Only price and status can be updated.", fg="#dc2626", bg=FORM_BG, font=("Arial", 12, "italic")).grid(row=7, column=0, columnspan=2, pady=(4, 0))

    def submit():
        name = name_var.get().strip()
        unit = unit_var.get().strip()
        quantity = quantity_entry.get().strip()
        price = price_entry.get().strip()
        raw = raw_price_entry.get().strip()
        status = status_var.get().strip() or "Active"

        if not name or not unit or not quantity:
            show_inventory_error(form, "Error", "All fields are required!")
            return
        if status not in ("Active", "Inactive"):
            show_inventory_error(form, "Error", "Status must be Active or Inactive.")
            return

        if mode == "add" and name == CHB_ITEM_NAME:
            show_inventory_error(form, "Error", "CHB quantity is auto-generated. Edit price only via the existing CHB item.")
            return

        try:
            quantity_val = int(quantity)
            price = price or "0"
            raw = raw or "0"
            price_val = float(price)
            raw_val = float(raw)
        except ValueError:
            show_inventory_error(form, "Error", "Quantity must be a whole number and prices must be numeric.")
            return

        if mode == "edit" and item_values and item_values[1] == CHB_ITEM_NAME:
            name = CHB_ITEM_NAME
            quantity_val = int(item_values[3])
            raw_val = float(item_values[5])
            unit = CHB_DEFAULT_UNIT

        if name in PREDEFINED_ITEMS and not unit:
            unit = PREDEFINED_ITEMS[name]

        if mode == "add":
            existing = fetch_existing_item_for_stack(cursor, name, price_val)

            if existing:
                item_id, current_qty = existing
                new_qty = int(current_qty) + quantity_val
                update_stacked_item(cursor, item_id, new_qty, raw_val, unit)
                success_msg = "Item quantity updated successfully!"
                log_restock(conn, cursor, name, quantity_val, price_val, raw_val, item_id, "Restock")
            else:
                item_id = insert_item(cursor, name, quantity_val, price_val, raw_val, unit, status)
                success_msg = "Item added successfully!"
                log_inventory_action(conn, cursor, item_id, name, quantity_val, status)
        else:
            item_id = item_values[0]
            previous_qty = int(item_values[3])
            previous_status = item_values[6] if len(item_values) > 6 and item_values[6] else "Active"
            update_item_record(cursor, item_id, name, quantity_val, price_val, raw_val, unit, status)
            success_msg = "Item updated successfully!"
            if quantity_val != previous_qty:
                cursor.execute(
                    "UPDATE items SET date_added=? WHERE id=?",
                    (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), item_id)
                )
            if quantity_val < previous_qty:
                log_inventory_action(conn, cursor, item_id, name, previous_qty - quantity_val, "Remove")
            if status != previous_status:
                log_inventory_action(conn, cursor, item_id, name, quantity_val, status)

        conn.commit()
        show_inventory_success(form, "Success", success_msg)
        form.destroy()
        if callable(refresh_view):
            refresh_view()
        else:
            view_items(conn, cursor, tree)

    tk.Button(form_card, text="Save", width=18, bg=SAVE_GREEN, fg="white", font=("Arial", 16, "bold"), bd=2, relief="solid", highlightbackground="black", highlightcolor="black", highlightthickness=1, padx=8, pady=8, command=submit).grid(row=6, column=0, padx=10, pady=26)
    tk.Button(form_card, text="Cancel", width=18, bg=CANCEL_RED, fg="white", font=("Arial", 16, "bold"), bd=2, relief="solid", highlightbackground="black", highlightcolor="black", highlightthickness=1, padx=8, pady=8, command=form.destroy).grid(row=6, column=1, padx=10, pady=26)
    center_window(form, 720, 620, inventory_window)


def add_item(conn, cursor, inventory_window, tree, refresh_view=None):
    open_item_form(conn, cursor, inventory_window, tree, "add", refresh_view=refresh_view)


def update_item(conn, cursor, inventory_window, tree, refresh_view=None):
    selected = tree.focus()
    if not selected:
        show_inventory_error(inventory_window, "Error", "Select an item to update.")
        return
    values = tree.item(selected, "values")
    open_item_form(conn, cursor, inventory_window, tree, "edit", values, refresh_view)


def open_restock_form(conn, cursor, inventory_window, item_values, refresh_view=None):
    if not item_values:
        show_inventory_error(inventory_window, "Error", "Select an item to restock.")
        return

    item_id = item_values[0]
    item_name = item_values[1]
    current_qty = int(item_values[3] or 0)
    status = item_values[6] if len(item_values) > 6 and item_values[6] else "Active"
    if status != "Active":
        show_inventory_error(inventory_window, "Inactive Item", "Inactive items cannot be restocked.")
        return

    form = tk.Toplevel(inventory_window)
    form.title("Restock Item")
    form.transient(inventory_window)
    form.grab_set()
    form.configure(bg=FORM_BG)
    form.resizable(False, False)

    form_card = tk.Frame(form, bg=FORM_BG, padx=34, pady=30)
    form_card.pack(fill="both", expand=True)

    tk.Label(
        form_card,
        text="Restock Item",
        font=("Arial", 24, "bold"),
        bg=FORM_BG,
        fg="#1e40af"
    ).grid(row=0, column=0, columnspan=3, pady=(0, 24), sticky="w")

    left_info = tk.Frame(form_card, bg=FORM_BG)
    left_info.grid(row=1, column=0, sticky="nw", padx=(0, 34))

    tk.Label(left_info, text="Item Name", font=("Arial", 14, "bold"), bg=FORM_BG, fg="#374151").pack(anchor="w")
    tk.Label(left_info, text=item_name, font=("Arial", 18, "bold"), bg=FORM_BG, fg="#111827", wraplength=250, justify="left").pack(anchor="w", pady=(4, 18))
    tk.Label(left_info, text="Current Quantity", font=("Arial", 14, "bold"), bg=FORM_BG, fg="#374151").pack(anchor="w")
    tk.Label(left_info, text=f"{current_qty:,}", font=("Arial", 18, "bold"), bg=FORM_BG, fg="#111827").pack(anchor="w", pady=(4, 0))

    tk.Label(form_card, text="+", font=("Arial", 34, "bold"), bg=FORM_BG, fg="#16a34a").grid(row=1, column=1, padx=(4, 12), sticky="n")

    input_frame = tk.Frame(form_card, bg=FORM_BG)
    input_frame.grid(row=1, column=2, sticky="n")
    tk.Label(input_frame, text="Quantity to Add", font=("Arial", 14, "bold"), bg=FORM_BG, fg="#374151").pack(anchor="w")
    qty_entry = tk.Entry(input_frame, width=14, font=("Arial", 20), justify="center")
    qty_entry.pack(anchor="w", pady=(8, 0))
    qty_entry.focus_set()

    button_frame = tk.Frame(form_card, bg=FORM_BG)
    button_frame.grid(row=2, column=0, columnspan=3, pady=(32, 0))

    def confirm_restock():
        quantity_text = qty_entry.get().strip()
        try:
            qty_added = int(quantity_text)
        except ValueError:
            show_inventory_error(form, "Invalid Quantity", "Quantity to add must be a positive number.")
            return

        if qty_added <= 0:
            show_inventory_error(form, "Invalid Quantity", "Quantity to add must be a positive number.")
            return

        result = restock_item_record(conn, cursor, item_id, qty_added)
        if not result:
            show_inventory_error(form, "Error", "Item was not found.")
            return
        if result == "inactive":
            show_inventory_error(form, "Inactive Item", "Inactive items cannot be restocked.")
            return

        form.destroy()
        show_inventory_success(inventory_window, "Success", f"{item_name} restocked successfully!")
        inventory_window.lift()
        inventory_window.focus_force()
        if callable(refresh_view):
            refresh_view()

    tk.Button(button_frame, text="Confirm", width=14, bg=SAVE_GREEN, fg="white", font=("Arial", 15, "bold"), bd=2, relief="solid", highlightbackground="black", highlightcolor="black", highlightthickness=1, padx=8, pady=8, command=confirm_restock).grid(row=0, column=0, padx=10)
    tk.Button(button_frame, text="Cancel", width=14, bg=CANCEL_RED, fg="white", font=("Arial", 15, "bold"), bd=2, relief="solid", highlightbackground="black", highlightcolor="black", highlightthickness=1, padx=8, pady=8, command=form.destroy).grid(row=0, column=1, padx=10)

    form.bind("<Return>", lambda _event: confirm_restock())
    form.bind("<Escape>", lambda _event: form.destroy())
    center_window(form, 650, 360, inventory_window)


def delete_item(conn, cursor, inventory_window, tree, refresh_view=None):
    selected = tree.focus()
    if not selected:
        show_inventory_error(inventory_window, "Error", "Select an item to delete.")
        return
    values = tree.item(selected, "values")
    if values[1] == CHB_ITEM_NAME:
        show_inventory_error(inventory_window, "Error", "CHB item cannot be deleted. Its stock is managed separately.")
        return

    confirm = tk.Toplevel(inventory_window)
    confirm.title("Delete Item")
    confirm.transient(inventory_window)
    confirm.grab_set()
    confirm.configure(bg=FORM_BG)
    confirm.resizable(False, False)

    confirm_card = tk.Frame(confirm, bg=FORM_BG)
    confirm_card.pack(expand=True)

    tk.Label(confirm_card, text="Delete Item", font=("Arial", 24, "bold"), bg=FORM_BG, fg="#991b1b").pack(pady=(0, 16))
    tk.Label(confirm_card, text=f"Are you sure you want to delete {values[1]}?", font=("Arial", 17, "bold"), bg=FORM_BG, wraplength=560, justify="center").pack(pady=10)

    button_frame = tk.Frame(confirm_card, bg=FORM_BG)
    button_frame.pack(pady=22)

    def confirm_delete():
        item_id = values[0]
        delete_item_record(conn, cursor, item_id)
        confirm.destroy()
        show_inventory_success(inventory_window, "Success", "Item deleted successfully!")
        inventory_window.lift()
        inventory_window.focus_force()
        if callable(refresh_view):
            refresh_view()
        else:
            view_items(conn, cursor, tree)

    tk.Button(button_frame, text="Delete", width=16, bg="#ff1744", fg="white", font=("Arial", 16, "bold"), bd=2, relief="solid", highlightbackground="black", highlightcolor="black", highlightthickness=1, padx=8, pady=8, command=confirm_delete).grid(row=0, column=0, padx=12)
    tk.Button(button_frame, text="Cancel", width=16, bg="#ff5252", fg="white", font=("Arial", 16, "bold"), bd=2, relief="solid", highlightbackground="black", highlightcolor="black", highlightthickness=1, padx=8, pady=8, command=confirm.destroy).grid(row=0, column=1, padx=12)
    center_window(confirm, 680, 340, inventory_window)


def search_items(event, conn, cursor, tree, search_entry, sort_var=None, total_var=None):
    sort_by = sort_var.get() if sort_var is not None else "Latest Date"
    view_items(conn, cursor, tree, search_entry.get(), sort_by, total_var)


def _close_inventory_window(inventory_gui_module, window=None):
    window = window or inventory_gui_module.inventory_window
    parent = window.master if window and window.winfo_exists() else None

    inventory_gui_module.inventory_refresh_callback = None
    if inventory_gui_module.inventory_refresh_job and window and window.winfo_exists():
        try:
            window.after_cancel(inventory_gui_module.inventory_refresh_job)
        except Exception:
            pass
    inventory_gui_module.inventory_refresh_job = None

    if window and window.winfo_exists():
        window.destroy()
    inventory_gui_module.inventory_window = None

    if parent and parent.winfo_exists():
        try:
            parent.deiconify()
            parent.lift()
            parent.focus_force()
        except Exception:
            pass
    return parent


def back_to_main(inventory_gui_module, window=None):
    _close_inventory_window(inventory_gui_module, window)


def direct_back_to_dashboard(inventory_gui_module, window=None):
    _close_inventory_window(inventory_gui_module, window)


def on_close(inventory_gui_module, window=None):
    _close_inventory_window(inventory_gui_module, window)
