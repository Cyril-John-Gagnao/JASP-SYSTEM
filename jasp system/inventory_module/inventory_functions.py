import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime

from .inventory_database import (
    CHB_ITEM_NAME,
    CHB_DEFAULT_UNIT,
    PREDEFINED_ITEMS,
    UNIT_OPTIONS,
    fetch_inventory_unit_options,
    add_inventory_unit_option,
    delete_inventory_unit_option,
    ensure_chb_item,
    normalize_predefined_units,
    fetch_items,
    count_items,
    log_restock,
    log_inventory_action,
    product_name_exists,
    fetch_fine_sand_bag_price,
    insert_item,
    update_item_record,
    update_fine_sand_item_record,
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
FINE_SAND_BAGS_PER_CUBIC_METER = 40
FINE_SAND_BASE_UNIT = "cubic meters"
FINE_SAND_TRANSACTION_UNITS = (FINE_SAND_BASE_UNIT, "bag")


def is_fine_sand(item_name):
    return str(item_name or "").strip().lower() == "fine sand"


def parse_inventory_quantity(quantity, item_name):
    quantity_text = str(quantity).strip().split(" ", 1)[0].replace(",", "")
    return float(quantity_text) if is_fine_sand(item_name) else int(quantity_text)


def fine_sand_to_cubic_meters(quantity, unit):
    quantity = float(quantity or 0)
    return quantity / FINE_SAND_BAGS_PER_CUBIC_METER if str(unit or "").strip().lower() == "bag" else quantity


def format_inventory_quantity(quantity):
    try:
        value = float(quantity or 0)
    except (TypeError, ValueError):
        return str(quantity)
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def format_fine_sand_display(quantity):
    cubic_stock = float(quantity or 0)
    equivalent_bags = cubic_stock * FINE_SAND_BAGS_PER_CUBIC_METER
    return f"{format_inventory_quantity(cubic_stock)} cubic meters ({format_inventory_quantity(equivalent_bags)} bags)"


def format_money_value(value):
    return f"{float(value or 0):.2f}"


def format_peso_value(value):
    return f"{chr(8369)}{float(value or 0):,.2f}"


def parse_money_text(value):
    cleaned = "".join(ch for ch in str(value) if ch.isdigit() or ch in ".-")
    return cleaned or "0"


def format_fine_sand_prices(cubic_price, bag_price):
    return f"Cubic: {format_peso_value(cubic_price)} | Bag: {format_peso_value(bag_price)}"


def display_inventory_row(row):
    values = list(row)
    if len(values) > 3 and is_fine_sand(values[1]):
        values[2] = FINE_SAND_BASE_UNIT
        values[3] = format_fine_sand_display(values[3])
        bag_price = values[7] if len(values) > 7 else 0
        values[4] = format_fine_sand_prices(values[4], bag_price)
        values = values[:7]
    elif len(values) > 5:
        values[4] = format_peso_value(values[4])
        values[5] = format_peso_value(values[5])
    return tuple(values)


def fetch_item_quantity(cursor, item_id):
    cursor.execute("SELECT COALESCE(quantity, 0) FROM items WHERE id=?", (item_id,))
    row = cursor.fetchone()
    return float(row[0] or 0) if row else 0


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
    if is_fine_sand(item_name):
        quantity = str(quantity).split(" ", 1)[0].replace(",", "")
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
        display_row = display_inventory_row(row)
        tag = inventory_row_tag(index, display_row)
        tree.insert("", tk.END, values=display_row, tags=(tag,))
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
                return float(parse_money_text(val))
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

    unit_label = tk.Label(form_card, text="Measurement Unit", font=("Arial", 16, "bold"), bg=FORM_BG)
    unit_label.grid(row=1, column=0, padx=18, pady=10, sticky="w")
    unit_var = tk.StringVar()
    unit_frame = tk.Frame(form_card, bg=FORM_BG)
    unit_frame.grid(row=1, column=1, pady=10, sticky="w")
    unit_entry = ttk.Combobox(unit_frame, textvariable=unit_var, values=fetch_inventory_unit_options(conn, cursor), width=21, font=("Arial", 16))
    unit_entry.grid(row=0, column=0, sticky="w")

    def refresh_unit_dropdown():
        unit_entry.config(values=fetch_inventory_unit_options(conn, cursor))

    def open_unit_manager():
        manager = tk.Toplevel(form)
        manager.title("Unit of Measurement")
        manager.transient(form)
        manager.grab_set()
        manager.configure(bg="#ffffff")
        manager.resizable(False, False)

        content = tk.Frame(manager, bg="#ffffff", padx=22, pady=18)
        content.pack(fill="both", expand=True)

        tk.Label(content, text="Unit of Measurement", bg="#ffffff", fg="#2563eb", font=("Arial", 18, "bold")).pack(anchor="w", pady=(0, 12))

        add_row = tk.Frame(content, bg="#ffffff")
        add_row.pack(fill="x", pady=(0, 12))
        new_unit_var = tk.StringVar()
        new_unit_entry = tk.Entry(add_row, textvariable=new_unit_var, width=24, font=("Arial", 13), bd=1, relief="solid")
        new_unit_entry.pack(side="left", fill="x", expand=True, padx=(0, 8))

        list_frame = tk.Frame(content, bg="#ffffff")
        list_frame.pack(fill="both", expand=True)

        def render_units():
            for child in list_frame.winfo_children():
                child.destroy()

            for unit in fetch_inventory_unit_options(conn, cursor):
                row = tk.Frame(list_frame, bg="#f8fafc", bd=1, relief="solid")
                row.pack(fill="x", pady=3)
                tk.Label(row, text=unit, bg="#f8fafc", fg="#1e293b", font=("Arial", 12, "bold"), anchor="w").pack(side="left", fill="x", expand=True, padx=10, pady=6)

                def remove_unit(unit_to_remove=unit):
                    if unit_var.get() == unit_to_remove:
                        unit_var.set("")
                    delete_inventory_unit_option(conn, cursor, unit_to_remove)
                    refresh_unit_dropdown()
                    render_units()

                tk.Button(row, text="X", command=remove_unit, bg="#dc2626", fg="white", font=("Arial", 10, "bold"), width=3, bd=1, relief="solid").pack(side="right", padx=6, pady=4)

        def add_unit():
            new_unit = new_unit_var.get().strip()
            if not new_unit:
                show_inventory_error(manager, "Error", "Enter a unit of measurement.")
                return
            add_inventory_unit_option(conn, cursor, new_unit)
            unit_var.set(new_unit)
            new_unit_var.set("")
            refresh_unit_dropdown()
            render_units()

        tk.Button(add_row, text="Add", command=add_unit, bg=SAVE_GREEN, fg="white", font=("Arial", 11, "bold"), bd=1, relief="solid", padx=10, pady=5).pack(side="left")
        tk.Button(content, text="Close", command=manager.destroy, bg=CANCEL_RED, fg="white", font=("Arial", 11, "bold"), bd=1, relief="solid", padx=12, pady=6).pack(anchor="e", pady=(12, 0))

        render_units()
        center_window(manager, 420, 460, form)

    unit_manager_button = tk.Button(unit_frame, text="+ Unit", command=open_unit_manager, bg="#2563eb", fg="white", font=("Arial", 11, "bold"), bd=1, relief="solid", padx=8, pady=4)
    unit_manager_button.grid(row=0, column=1, padx=(8, 0), sticky="w")

    tk.Label(form_card, text="Quantity", font=("Arial", 16, "bold"), bg=FORM_BG).grid(row=2, column=0, padx=18, pady=10, sticky="w")
    quantity_entry = tk.Entry(form_card, width=28, font=("Arial", 16))
    quantity_entry.grid(row=2, column=1, pady=10)

    price_label = tk.Label(form_card, text="Selling Price", font=("Arial", 16, "bold"), bg=FORM_BG)
    price_label.grid(row=3, column=0, padx=18, pady=10, sticky="w")
    price_entry = tk.Entry(form_card, width=28, font=("Arial", 16))
    price_entry.grid(row=3, column=1, pady=10)

    bag_price_label = tk.Label(form_card, text="Bag Price", font=("Arial", 16, "bold"), bg=FORM_BG)
    bag_price_entry = tk.Entry(form_card, width=28, font=("Arial", 16))

    raw_price_label = tk.Label(form_card, text="Raw Price", font=("Arial", 16, "bold"), bg=FORM_BG)
    raw_price_label.grid(row=4, column=0, padx=18, pady=10, sticky="w")
    raw_price_entry = tk.Entry(form_card, width=28, font=("Arial", 16))
    raw_price_entry.grid(row=4, column=1, pady=10)

    status_label = tk.Label(form_card, text="Status", font=("Arial", 16, "bold"), bg=FORM_BG)
    status_label.grid(row=5, column=0, padx=18, pady=10, sticky="w")
    status_var = tk.StringVar(value="Active")
    status_entry = ttk.Combobox(form_card, textvariable=status_var, values=["Active", "Inactive"], width=26, font=("Arial", 16), state="readonly")
    status_entry.grid(row=5, column=1, pady=10)

    def sync_fine_sand_transaction_unit(*_args):
        if is_fine_sand(name_var.get().strip()):
            unit_label.config(text="Quantity Unit")
            price_label.config(text="Cubic Meter Price")
            unit_entry.config(values=FINE_SAND_TRANSACTION_UNITS, state="readonly")
            unit_manager_button.grid_remove()
            if unit_var.get() not in FINE_SAND_TRANSACTION_UNITS:
                unit_var.set(FINE_SAND_BASE_UNIT)
            bag_price_label.grid(row=4, column=0, padx=18, pady=10, sticky="w")
            bag_price_entry.grid(row=4, column=1, pady=10)
            raw_price_label.grid(row=5, column=0, padx=18, pady=10, sticky="w")
            raw_price_entry.grid(row=5, column=1, pady=10)
            status_label.grid(row=6, column=0, padx=18, pady=10, sticky="w")
            status_entry.grid(row=6, column=1, pady=10)
        else:
            unit_label.config(text="Measurement Unit")
            price_label.config(text="Selling Price")
            unit_entry.config(values=fetch_inventory_unit_options(conn, cursor), state="normal")
            unit_manager_button.grid(row=0, column=1, padx=(8, 0), sticky="w")
            bag_price_label.grid_remove()
            bag_price_entry.grid_remove()
            raw_price_label.grid(row=4, column=0, padx=18, pady=10, sticky="w")
            raw_price_entry.grid(row=4, column=1, pady=10)
            status_label.grid(row=5, column=0, padx=18, pady=10, sticky="w")
            status_entry.grid(row=5, column=1, pady=10)

    def sync_unit_from_name(event=None):
        selected_item = name_var.get().strip()
        if selected_item in PREDEFINED_ITEMS:
            unit_var.set(PREDEFINED_ITEMS[selected_item])
        sync_fine_sand_transaction_unit()

    name_entry.bind("<KeyRelease>", sync_unit_from_name)
    name_entry.bind("<FocusOut>", sync_unit_from_name)

    if mode == "edit" and item_values:
        name_var.set(item_values[1])
        unit_var.set(item_values[2] if len(item_values) > 2 else "")
        quantity_entry.insert(0, format_inventory_quantity(fetch_item_quantity(cursor, item_values[0])) if is_fine_sand(item_values[1]) else item_values[3])
        if is_fine_sand(item_values[1]):
            cursor.execute("SELECT COALESCE(price, 0), COALESCE(fine_sand_bag_price, 0) FROM items WHERE id=?", (item_values[0],))
            price_row = cursor.fetchone() or (0, 0)
            price_entry.insert(0, format_money_value(price_row[0]))
            bag_price_entry.insert(0, format_money_value(price_row[1]))
        else:
            price_entry.insert(0, parse_money_text(item_values[4]))
        raw_price_entry.insert(0, parse_money_text(item_values[5]))
        status_var.set(item_values[6] if len(item_values) > 6 and item_values[6] else "Active")

        if not unit_var.get() and item_values[1] in PREDEFINED_ITEMS:
            unit_var.set(PREDEFINED_ITEMS[item_values[1]])
        sync_fine_sand_transaction_unit()

        if item_values[1] == CHB_ITEM_NAME:
            quantity_entry.config(state="disabled")
            raw_price_entry.config(state="disabled")
            unit_entry.config(state="disabled")
            unit_var.set(CHB_DEFAULT_UNIT)
            tk.Label(form_card, text="Quantity is auto from CHB production. Name, price, and status can be updated.", fg="#dc2626", bg=FORM_BG, font=("Arial", 12, "italic")).grid(row=8, column=0, columnspan=2, pady=(4, 0))

    def submit():
        name = name_var.get().strip()
        unit = unit_var.get().strip()
        quantity = quantity_entry.get().strip()
        price = price_entry.get().strip()
        bag_price = bag_price_entry.get().strip()
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
            quantity_val = parse_inventory_quantity(quantity, name)
            price = price or "0"
            bag_price = bag_price or "0"
            raw = raw or "0"
            price_val = float(price)
            bag_price_val = float(bag_price)
            raw_val = float(raw)
        except ValueError:
            show_inventory_error(form, "Error", "Quantity must be numeric and prices must be numeric.")
            return
        if quantity_val <= 0:
            show_inventory_error(form, "Error", "Quantity must be greater than zero.")
            return

        if mode == "edit" and item_values and item_values[1] == CHB_ITEM_NAME:
            quantity_val = int(item_values[3])
            raw_val = float(parse_money_text(item_values[5]))
            unit = CHB_DEFAULT_UNIT

        if name in PREDEFINED_ITEMS and not unit:
            unit = PREDEFINED_ITEMS[name]

        if is_fine_sand(name):
            transaction_unit = unit
            unit = FINE_SAND_BASE_UNIT
            quantity_val = fine_sand_to_cubic_meters(quantity_val, transaction_unit)
        else:
            bag_price_val = 0

        if mode == "add":
            if product_name_exists(cursor, name):
                show_inventory_error(form, "Error", "Product or product name already exists.")
                return

            item_id = insert_item(cursor, name, quantity_val, price_val, raw_val, unit, status)
            if is_fine_sand(name):
                update_fine_sand_item_record(cursor, item_id, name, quantity_val, price_val, bag_price_val, raw_val, unit, status)
            success_msg = "Item added successfully!"
            log_inventory_action(conn, cursor, item_id, name, quantity_val, status)
        else:
            item_id = item_values[0]
            if product_name_exists(cursor, name, item_id):
                show_inventory_error(form, "Error", "Product or product name already exists.")
                return
            previous_qty = fetch_item_quantity(cursor, item_id)
            previous_status = item_values[6] if len(item_values) > 6 and item_values[6] else "Active"
            if is_fine_sand(name):
                update_fine_sand_item_record(cursor, item_id, name, quantity_val, price_val, bag_price_val, raw_val, unit, status)
            else:
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

    tk.Button(form_card, text="Save", width=18, bg=SAVE_GREEN, fg="white", font=("Arial", 16, "bold"), bd=2, relief="solid", highlightbackground="black", highlightcolor="black", highlightthickness=1, padx=8, pady=8, command=submit).grid(row=7, column=0, padx=10, pady=26)
    tk.Button(form_card, text="Cancel", width=18, bg=CANCEL_RED, fg="white", font=("Arial", 16, "bold"), bd=2, relief="solid", highlightbackground="black", highlightcolor="black", highlightthickness=1, padx=8, pady=8, command=form.destroy).grid(row=7, column=1, padx=10, pady=26)
    center_window(form, 720, 680, inventory_window)


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
    current_qty = fetch_item_quantity(cursor, item_id) if is_fine_sand(item_name) else int(item_values[3] or 0)
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
    tk.Label(left_info, text=format_inventory_quantity(current_qty), font=("Arial", 18, "bold"), bg=FORM_BG, fg="#111827").pack(anchor="w", pady=(4, 0))

    tk.Label(form_card, text="+", font=("Arial", 34, "bold"), bg=FORM_BG, fg="#16a34a").grid(row=1, column=1, padx=(4, 12), sticky="n")

    input_frame = tk.Frame(form_card, bg=FORM_BG)
    input_frame.grid(row=1, column=2, sticky="n")
    tk.Label(input_frame, text="Quantity to Add", font=("Arial", 14, "bold"), bg=FORM_BG, fg="#374151").pack(anchor="w")
    qty_entry = tk.Entry(input_frame, width=14, font=("Arial", 20), justify="center")
    qty_entry.pack(anchor="w", pady=(8, 0))
    qty_entry.focus_set()

    transaction_unit_var = tk.StringVar(value=FINE_SAND_BASE_UNIT)
    if is_fine_sand(item_name):
        tk.Label(input_frame, text="Quantity Unit", font=("Arial", 14, "bold"), bg=FORM_BG, fg="#374151").pack(anchor="w", pady=(16, 0))
        ttk.Combobox(
            input_frame,
            textvariable=transaction_unit_var,
            values=FINE_SAND_TRANSACTION_UNITS,
            width=13,
            font=("Arial", 16),
            state="readonly",
        ).pack(anchor="w", pady=(8, 0))

    button_frame = tk.Frame(form_card, bg=FORM_BG)
    button_frame.grid(row=2, column=0, columnspan=3, pady=(32, 0))

    def confirm_restock():
        quantity_text = qty_entry.get().strip()
        try:
            qty_added = parse_inventory_quantity(quantity_text, item_name)
        except ValueError:
            show_inventory_error(form, "Invalid Quantity", "Quantity to add must be a positive number.")
            return

        if qty_added <= 0:
            show_inventory_error(form, "Invalid Quantity", "Quantity to add must be a positive number.")
            return
        if is_fine_sand(item_name):
            qty_added = fine_sand_to_cubic_meters(qty_added, transaction_unit_var.get())

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
    center_window(form, 650, 420 if is_fine_sand(item_name) else 360, inventory_window)


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
