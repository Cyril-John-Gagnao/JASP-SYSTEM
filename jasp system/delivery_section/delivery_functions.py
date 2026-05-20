import tkinter as tk
from tkinter import ttk, messagebox
import calendar
from datetime import datetime

from .delivery_database import (
    insert_delivery,
    insert_other_item_delivery,
    update_other_item_delivery_record,
    delete_other_item_delivery_record,
    update_delivery_record,
    delete_delivery_record,
    fetch_delivery_rows,
    fetch_other_item_delivery_rows,
)
from window_utils import close_window_and_focus_parent
from inventory_module.inventory_database import (
    open_inventory_connection,
    fetch_inventory_unit_options,
)

SUCCESS_GREEN = "#00c853"
CANCEL_RED = "#dc2626"


def get_delivery_unit_options():
    conn = None
    try:
        conn, cursor = open_inventory_connection()
        return fetch_inventory_unit_options(conn, cursor)
    except Exception:
        return ["pieces", "kilograms", "bag/sack", "meters", "liters", "boxes", "sets", "rolls"]
    finally:
        if conn:
            conn.close()


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


def show_delivery_popup(parent, title, message, accent_color):
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)

    tk.Frame(popup, bg=accent_color, height=12).pack(fill="x")
    content = tk.Frame(popup, bg="#ffffff", padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(content, text=title, bg="#ffffff", fg=accent_color, font=("Arial", 28, "bold")).pack(pady=(0, 14))
    tk.Label(content, text=message, bg="#ffffff", fg="#111827", font=("Arial", 17), wraplength=430, justify="center").pack(pady=(0, 28))

    def close_popup():
        popup.destroy()

    tk.Button(content, text="OK", command=close_popup, bg=accent_color, fg="white", activebackground=accent_color, font=("Arial", 15, "bold"), relief="flat", width=14, pady=9).pack()
    popup.bind("<Return>", lambda _event: close_popup())
    popup.bind("<Escape>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    center_window(popup, 540, 290, parent)
    parent.wait_window(popup)


def show_delivery_error(parent, title, message):
    show_delivery_popup(parent, title, message, CANCEL_RED)


def show_delivery_success(parent, title, message):
    show_delivery_popup(parent, title, message, SUCCESS_GREEN)


def ask_delivery_confirmation(parent, title, message, confirm_text="Yes"):
    result = {"confirmed": False}
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)

    tk.Frame(popup, bg="#2563eb", height=12).pack(fill="x")
    content = tk.Frame(popup, bg="#ffffff", padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(content, text=title, bg="#ffffff", fg="#2563eb", font=("Arial", 26, "bold")).pack(pady=(0, 14))
    tk.Label(content, text=message, bg="#ffffff", fg="#111827", font=("Arial", 16), wraplength=470, justify="center").pack(pady=(0, 28))

    button_row = tk.Frame(content, bg="#ffffff")
    button_row.pack()

    def confirm():
        result["confirmed"] = True
        popup.destroy()

    def cancel():
        popup.destroy()

    tk.Button(button_row, text="Cancel", command=cancel, bg="#64748b", fg="white", activebackground="#475569", font=("Arial", 14, "bold"), relief="flat", width=13, pady=9).pack(side="left", padx=8)
    tk.Button(button_row, text=confirm_text, command=confirm, bg="#2563eb", fg="white", activebackground="#1d4ed8", font=("Arial", 14, "bold"), relief="flat", width=13, pady=9).pack(side="left", padx=8)
    popup.bind("<Return>", lambda _event: confirm())
    popup.bind("<Escape>", lambda _event: cancel())
    popup.protocol("WM_DELETE_WINDOW", cancel)
    center_window(popup, 600, 330, parent)
    parent.wait_window(popup)
    return result["confirmed"]


def go_back(delivery_win):
    close_window_and_focus_parent(delivery_win)


def refresh_data(load_data):
    load_data()


def money(value):
    return f"₱{value:,.2f}"


def parse_money(value):
    cleaned = "".join(ch for ch in str(value) if ch.isdigit() or ch in ".-")
    return float(cleaned or 0)


def is_blank(value):
    return str(value or "").strip() == ""


def get_tk_var_text(var):
    try:
        return str(var.get()).strip()
    except tk.TclError:
        return str(var._tk.globalgetvar(var._name)).strip()


def parse_positive_int(value, field_name, parent):
    try:
        parsed = int(str(value).strip())
    except (TypeError, ValueError):
        show_delivery_error(parent, "Error", f"{field_name} must be an integer number.")
        return None
    if parsed <= 0:
        show_delivery_error(parent, "Error", f"{field_name} must be greater than zero.")
        return None
    return parsed


def parse_positive_number(value, field_name, parent, allow_zero=False):
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        show_delivery_error(parent, "Error", f"{field_name} must be a numeric number.")
        return None
    if allow_zero:
        if parsed < 0:
            show_delivery_error(parent, "Error", f"{field_name} must not be negative.")
            return None
    elif parsed <= 0:
        show_delivery_error(parent, "Error", f"{field_name} must be greater than zero.")
        return None
    return parsed


def open_date_calendar(parent, date_var, on_select=None):
    try:
        selected_date = datetime.strptime(date_var.get(), "%Y-%m-%d")
    except Exception:
        selected_date = datetime.now()

    cal_win = tk.Toplevel(parent)
    cal_win.title("Select Date")
    cal_win.resizable(False, False)
    cal_win.configure(bg="#ffffff")
    cal_win.transient(parent)
    cal_win.grab_set()

    year_var = tk.IntVar(value=selected_date.year)
    month_var = tk.IntVar(value=selected_date.month)

    header = tk.Frame(cal_win, bg="#ffffff")
    header.pack(fill="x", padx=10, pady=(10, 4))

    grid_frame = tk.Frame(cal_win, bg="#ffffff")
    grid_frame.pack(padx=10, pady=(0, 10))

    title_var = tk.StringVar()

    def select_date(day):
        date_var.set(f"{year_var.get():04d}-{month_var.get():02d}-{day:02d}")
        if callable(on_select):
            on_select()
        cal_win.destroy()

    def change_month(delta):
        month = month_var.get() + delta
        year = year_var.get()
        if month < 1:
            month = 12
            year -= 1
        elif month > 12:
            month = 1
            year += 1
        month_var.set(month)
        year_var.set(year)
        render_calendar()

    def render_calendar():
        for child in grid_frame.winfo_children():
            child.destroy()

        title_var.set(f"{calendar.month_name[month_var.get()]} {year_var.get()}")
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, day_name in enumerate(days):
            tk.Label(grid_frame, text=day_name, bg="#ffffff", fg="#1e293b", font=("Arial", 12, "bold"), width=6).grid(row=0, column=col, padx=2, pady=3)

        today = datetime.now()
        for row_index, week in enumerate(calendar.monthcalendar(year_var.get(), month_var.get()), start=1):
            for col_index, day in enumerate(week):
                if day == 0:
                    tk.Label(grid_frame, text="", bg="#ffffff", width=6).grid(row=row_index, column=col_index, padx=2, pady=2)
                    continue

                is_today = day == today.day and month_var.get() == today.month and year_var.get() == today.year
                tk.Button(
                    grid_frame,
                    text=str(day),
                    width=6,
                    bg="#2563eb" if is_today else "#f8fafc",
                    fg="white" if is_today else "#1e293b",
                    relief="solid",
                    bd=1,
                    font=("Arial", 12, "bold"),
                    command=lambda d=day: select_date(d)
                ).grid(row=row_index, column=col_index, padx=2, pady=2)

    tk.Button(header, text="<", command=lambda: change_month(-1), bg="#e0f2fe", relief="solid", bd=1, width=5, font=("Arial", 13, "bold")).pack(side="left")
    tk.Label(header, textvariable=title_var, bg="#ffffff", fg="#1e293b", font=("Arial", 15, "bold"), width=20).pack(side="left", padx=10)
    tk.Button(header, text=">", command=lambda: change_month(1), bg="#e0f2fe", relief="solid", bd=1, width=5, font=("Arial", 13, "bold")).pack(side="left")

    render_calendar()

    cal_win.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (cal_win.winfo_width() // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (cal_win.winfo_height() // 2)
    cal_win.geometry(f"470x390+{x}+{y}")


from .delivery_summary import open_delivery_summary


def open_other_items_form(parent_win, conn, cursor, load_data, display_option_var, record_values=None):
    is_edit_mode = bool(record_values and record_values[0])
    selected_other_id = str(record_values[0]) if is_edit_mode else ""

    form_win = tk.Toplevel(parent_win)
    form_win.title("Edit Other Item Delivery" if is_edit_mode else "Other Items to Deliver")
    form_win.configure(bg="#ffffff")
    form_win.transient(parent_win)
    form_win.grab_set()
    form_win.resizable(False, False)

    transaction_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    delivery_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    delivery_datetime_var = delivery_date_var

    button_border = {
        "bd": 2,
        "relief": "solid",
        "highlightthickness": 1,
        "highlightbackground": "black",
        "highlightcolor": "black",
    }

    content = tk.Frame(form_win, bg="#ffffff", padx=24, pady=20)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text="Edit Other Item Delivery" if is_edit_mode else "Other Items to Deliver",
        bg="#ffffff",
        fg="#2563eb",
        font=("Arial", 22, "bold")
    ).pack(anchor="w", pady=(0, 12))

    form_bg = tk.Frame(content, bg="#fef3c7", bd=1, relief="flat")
    form_bg.pack(fill="x")

    form = tk.Frame(form_bg, bg="#fef3c7")
    form.pack(fill="x", padx=16, pady=12)
    form.columnconfigure(0, weight=0)
    form.columnconfigure(1, weight=1)

    tk.Label(
        form,
        text="Transaction Date",
        bg="#fef3c7",
        fg="#1e293b",
        font=("Arial", 13, "bold")
    ).grid(row=0, column=0, sticky="w", padx=(0, 14), pady=6)
    transaction_date_frame = tk.Frame(form, bg="#fef3c7")
    transaction_date_frame.grid(row=0, column=1, sticky="ew", pady=6)
    tk.Entry(
        transaction_date_frame,
        textvariable=transaction_date_var,
        width=20,
        font=("Arial", 13),
        bd=1,
        relief="solid",
        bg="white"
    ).pack(side="left", fill="x", expand=True)
    tk.Button(
        transaction_date_frame,
        text="Calendar",
        command=lambda: open_date_calendar(form_win, transaction_date_var),
        bg="#3b82f6",
        fg="white",
        font=("Arial", 10, "bold"),
        padx=6,
        pady=2,
        **button_border
    ).pack(side="left", padx=(5, 0))

    tk.Label(
        form,
        text="Delivery Date",
        bg="#fef3c7",
        fg="#1e293b",
        font=("Arial", 13, "bold")
    ).grid(row=1, column=0, sticky="w", padx=(0, 14), pady=6)
    date_frame = tk.Frame(form, bg="#fef3c7")
    date_frame.grid(row=1, column=1, sticky="ew", pady=6)
    date_entry = tk.Entry(
        date_frame,
        textvariable=delivery_datetime_var,
        width=24,
        font=("Arial", 13),
        bd=1,
        relief="solid",
        bg="white"
    )
    date_entry.pack(side="left", fill="x", expand=True)
    tk.Button(
        date_frame,
        text="ðŸ“…",
        command=lambda: open_date_calendar(form_win, delivery_datetime_var),
        bg="#3b82f6",
        fg="white",
        font=("Arial", 11, "bold"),
        pady=2,
        **button_border
    ).pack(side="left", padx=(5, 0))
    date_frame.winfo_children()[-1].config(text="Calendar", font=("Arial", 10, "bold"), padx=6)

    fields = [
        ("Item Name", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
        ("Quantity", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
        ("Unit of Measurement", ttk.Combobox(form, values=get_delivery_unit_options(), width=26, font=("Arial", 13))),
        ("Delivery Address", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
        ("Delivery Driver", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
        ("Helper", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
        ("Delivery Fee", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
    ]

    entry_by_label = {}
    for row_index, (label_text, entry) in enumerate(fields, start=2):
        tk.Label(
            form,
            text=label_text,
            bg="#fef3c7",
            fg="#1e293b",
            font=("Arial", 13, "bold")
        ).grid(row=row_index, column=0, sticky="w", padx=(0, 14), pady=6)
        entry.grid(row=row_index, column=1, sticky="ew", pady=6)
        entry_by_label[label_text] = entry

    button_row = tk.Frame(content, bg="#ffffff")
    button_row.pack(fill="x", pady=(18, 0))

    if is_edit_mode:
        transaction_date_var.set(str(record_values[1])[:10])
        delivery_date_var.set(str(record_values[2])[:10])
        entry_by_label["Item Name"].insert(0, record_values[3])
        entry_by_label["Quantity"].insert(0, record_values[4])
        entry_by_label["Unit of Measurement"].insert(0, record_values[5])
        entry_by_label["Delivery Address"].insert(0, record_values[6])
        entry_by_label["Delivery Driver"].insert(0, record_values[7])
        entry_by_label["Helper"].insert(0, record_values[8])
        entry_by_label["Delivery Fee"].insert(0, record_values[9])

    def get_other_item_form_values():
        transaction_date = transaction_date_var.get().strip()
        delivery_date = delivery_date_var.get().strip()
        item_name = entry_by_label["Item Name"].get().strip()
        quantity_text = entry_by_label["Quantity"].get().strip()
        unit_of_measurement = entry_by_label["Unit of Measurement"].get().strip()
        delivery_address = entry_by_label["Delivery Address"].get().strip()
        delivery_driver = entry_by_label["Delivery Driver"].get().strip()
        helper = entry_by_label["Helper"].get().strip()
        delivery_fee_text = entry_by_label["Delivery Fee"].get().strip()

        required_values = (
            transaction_date,
            delivery_date,
            item_name,
            quantity_text,
            unit_of_measurement,
            delivery_address,
            delivery_driver,
            helper,
            delivery_fee_text,
        )
        if any(is_blank(value) for value in required_values):
            show_delivery_error(form_win, "Error", "All fields must not be empty.")
            return None

        quantity = parse_positive_int(quantity_text, "Quantity", form_win)
        if quantity is None:
            return None

        delivery_fee = parse_positive_number(delivery_fee_text, "Delivery fee", form_win, allow_zero=True)
        if delivery_fee is None:
            return None

        return transaction_date, delivery_date, item_name, quantity, unit_of_measurement, delivery_address, delivery_driver, helper, delivery_fee

    def save_other_item_delivery():
        form_values = get_other_item_form_values()
        if not form_values:
            return

        transaction_date, delivery_date, item_name, quantity, unit_of_measurement, delivery_address, delivery_driver, helper, delivery_fee = form_values

        if not ask_delivery_confirmation(form_win, "Confirm Save", f"Save delivery record for {item_name}?", "Save"):
            return

        insert_other_item_delivery(
            conn,
            cursor,
            transaction_date,
            delivery_date,
            item_name,
            quantity,
            unit_of_measurement,
            delivery_address,
            delivery_driver,
            helper,
            delivery_fee,
        )
        display_option_var.set("Option 2")
        load_data()
        form_win.destroy()
        show_delivery_success(parent_win, "Success", "Other item delivery saved successfully!")

    def update_other_item_delivery():
        form_values = get_other_item_form_values()
        if not form_values:
            return

        transaction_date, delivery_date, item_name, quantity, unit_of_measurement, delivery_address, delivery_driver, helper, delivery_fee = form_values

        if not ask_delivery_confirmation(form_win, "Confirm Update", f"Update delivery record for {item_name}?", "Update"):
            return

        update_other_item_delivery_record(
            conn,
            cursor,
            selected_other_id,
            transaction_date,
            delivery_date,
            item_name,
            quantity,
            unit_of_measurement,
            delivery_address,
            delivery_driver,
            helper,
            delivery_fee,
        )
        display_option_var.set("Option 2")
        load_data()
        form_win.destroy()
        show_delivery_success(parent_win, "Success", "Other item delivery updated successfully!")

    def delete_other_item_delivery():
        item_name = entry_by_label["Item Name"].get().strip() or "this item"
        if not ask_delivery_confirmation(form_win, "Confirm Delete", f"Delete delivery record for {item_name}?\n\nThis action cannot be undone.", "Delete"):
            return

        delete_other_item_delivery_record(conn, cursor, selected_other_id)
        display_option_var.set("Option 2")
        load_data()
        form_win.destroy()
        show_delivery_success(parent_win, "Success", "Other item delivery deleted successfully!")

    tk.Button(button_row, text="Cancel", command=form_win.destroy, bg="#64748b", fg="white", font=("Arial", 12, "bold"), width=12, pady=7, cursor="hand2", **button_border).pack(side="right", padx=6)
    if is_edit_mode:
        tk.Button(button_row, text="Delete", command=delete_other_item_delivery, bg="#dc2626", fg="white", font=("Arial", 12, "bold"), width=12, pady=7, cursor="hand2", **button_border).pack(side="right", padx=6)
        tk.Button(button_row, text="Update", command=update_other_item_delivery, bg="#1e40af", fg="white", font=("Arial", 12, "bold"), width=12, pady=7, cursor="hand2", **button_border).pack(side="right", padx=6)
    else:
        tk.Button(button_row, text="Save", command=save_other_item_delivery, bg="#15803d", fg="white", font=("Arial", 12, "bold"), width=12, pady=7, cursor="hand2", **button_border).pack(side="right", padx=6)

    center_window(form_win, 600, 500, parent_win)


def auto_calc(event, blocks_entry, payment_var, result_label):
    try:
        blocks = int(blocks_entry.get() or 0)
        payment_per = float(payment_var.get() or 2.0)
        total = blocks * payment_per

        result_label.config(text=f"Total Payment for Worker: ₱{total:,.2f}")

    except:
        blocks_entry.delete(0, tk.END)
        result_label.config(text="Total Payment for Worker: ₱0")


def clear_form(transaction_date_var, date_var, worker_entry, driver_entry, address_entry, blocks_entry, delivery_fee_entry, payment_var, result_label, selected_id):
    transaction_date_var.set(datetime.now().strftime("%Y-%m-%d"))
    date_var.set(datetime.now().strftime("%Y-%m-%d"))
    worker_entry.delete(0, tk.END)
    driver_entry.delete(0, tk.END)
    address_entry.delete(0, tk.END)
    blocks_entry.delete(0, tk.END)
    delivery_fee_entry.delete(0, tk.END)
    payment_var.set(2.0)
    result_label.config(text="Total Payment: ₱0")
    selected_id.set("")


def save_delivery(conn, cursor, delivery_win, transaction_date_var, worker_entry, date_var, driver_entry, address_entry, blocks_entry, delivery_fee_entry, payment_var, load_data, clear_form):
    transaction_date = transaction_date_var.get().strip()
    date = date_var.get().strip()
    worker = worker_entry.get().strip()
    driver_name = driver_entry.get().strip()
    address = address_entry.get().strip()
    blocks_text = blocks_entry.get().strip()
    delivery_fee_text = delivery_fee_entry.get().strip()
    payment_text = get_tk_var_text(payment_var)

    required_values = (
        transaction_date,
        date,
        worker,
        driver_name,
        address,
        blocks_text,
        delivery_fee_text,
        payment_text,
    )
    if any(is_blank(value) for value in required_values):
        show_delivery_error(delivery_win, "Error", "All fields must not be empty.")
        return

    blocks = parse_positive_int(blocks_text, "Blocks to be delivered", delivery_win)
    if blocks is None:
        return

    delivery_fee = parse_positive_number(delivery_fee_text, "Delivery fee", delivery_win, allow_zero=True)
    if delivery_fee is None:
        return

    payment_per = parse_positive_number(payment_text, "Worker salary", delivery_win)
    if payment_per is None:
        return

    total = blocks * payment_per

    if not ask_delivery_confirmation(delivery_win, "Confirm Save", f"Save delivery record for {worker}?", "Save"):
        return

    insert_delivery(conn, cursor, transaction_date, date, worker, driver_name, address, blocks, delivery_fee, payment_per, total)
    load_data()
    clear_form()
    show_delivery_success(delivery_win, "Success", "Delivery record saved successfully!")


def update_delivery(conn, cursor, delivery_win, selected_id, transaction_date_var, worker_entry, date_var, driver_entry, address_entry, blocks_entry, delivery_fee_entry, payment_var, load_data, clear_form):
    if not selected_id.get():
        show_delivery_error(delivery_win, "Error", "Select a record")
        return

    transaction_date = transaction_date_var.get().strip()
    date = date_var.get().strip()
    worker = worker_entry.get().strip()
    driver_name = driver_entry.get().strip()
    address = address_entry.get().strip()
    blocks_text = blocks_entry.get().strip()
    delivery_fee_text = delivery_fee_entry.get().strip()
    payment_text = get_tk_var_text(payment_var)

    required_values = (
        transaction_date,
        date,
        worker,
        driver_name,
        address,
        blocks_text,
        delivery_fee_text,
        payment_text,
    )
    if any(is_blank(value) for value in required_values):
        show_delivery_error(delivery_win, "Error", "All fields must not be empty.")
        return

    blocks = parse_positive_int(blocks_text, "Blocks to be delivered", delivery_win)
    if blocks is None:
        return

    delivery_fee = parse_positive_number(delivery_fee_text, "Delivery fee", delivery_win, allow_zero=True)
    if delivery_fee is None:
        return

    payment_per = parse_positive_number(payment_text, "Worker salary", delivery_win)
    if payment_per is None:
        return

    total = blocks * payment_per

    if not ask_delivery_confirmation(delivery_win, "Confirm Update", f"Update record for {worker}?", "Update"):
        return

    update_delivery_record(conn, cursor, selected_id.get(), transaction_date, date, worker, driver_name, address, blocks, delivery_fee, payment_per, total)
    load_data()
    clear_form()
    show_delivery_success(delivery_win, "Success", "Record updated successfully!")


def delete_delivery(conn, cursor, delivery_win, selected_id, worker_entry, load_data, clear_form):
    if not selected_id.get():
        show_delivery_error(delivery_win, "Error", "Select a record")
        return

    if not ask_delivery_confirmation(delivery_win, "Confirm Delete", f"Delete record for {worker_entry.get()}?\n\nThis action cannot be undone.", "Delete"):
        return

    delete_delivery_record(conn, cursor, selected_id.get())
    load_data()
    clear_form()
    show_delivery_success(delivery_win, "Success", "Record deleted successfully!")


def on_tree_configure(event, tree):
    tree.update_idletasks()


def on_select(event, tree, selected_id, transaction_date_var, date_var, worker_entry, driver_entry, address_entry, blocks_entry, delivery_fee_entry, auto_calc):
    selected = tree.focus()
    values = tree.item(selected, "values")

    if values and values[0]:
        selected_id.set(values[0])
        transaction_date_var.set(values[1])
        date_var.set(values[2])
        worker_entry.delete(0, tk.END)
        worker_entry.insert(0, values[3])
        driver_entry.delete(0, tk.END)
        driver_entry.insert(0, values[4])
        address_entry.delete(0, tk.END)
        address_entry.insert(0, values[5])
        blocks_entry.delete(0, tk.END)
        blocks_entry.insert(0, values[6])
        delivery_fee_entry.delete(0, tk.END)
        delivery_fee_entry.insert(0, values[7])
        auto_calc()


def load_data(event, cursor, tree, search_var, sort_var, delivery_win):
    try:
        for row in tree.get_children():
            tree.delete(row)

        keyword = search_var.get().lower()
        sort_option = sort_var.get()
        today = datetime.now().strftime("%Y-%m-%d")
        rows = fetch_delivery_rows(cursor, keyword, sort_option, today)

        row_index = 0
        if not rows:
            message = "No matching records found." if keyword else "No deliveries for today"
            tree.insert("", "end", values=("", today, today, message, "", "", "", "", "", ""), tags=('oddrow',))
            return

        for row in rows:
            tag = 'evenrow' if row_index % 2 == 0 else 'oddrow'
            tree.insert("", "end", values=tuple(row), tags=(tag,))
            row_index += 1
    except Exception as e:
        show_delivery_error(delivery_win, "Error", f"Failed to load data: {str(e)}")


def load_other_items_data(event, cursor, tree, search_var, sort_var, delivery_win):
    try:
        for row in tree.get_children():
            tree.delete(row)

        keyword = search_var.get().lower()
        sort_option = sort_var.get()
        today = datetime.now().strftime("%Y-%m-%d")
        rows = fetch_other_item_delivery_rows(cursor, keyword, sort_option, today)

        if not rows:
            message = "No matching records found." if keyword else "No other item deliveries for today"
            tree.insert("", "end", values=("", today, today, message, "", "", "", "", "", "", ""), tags=("oddrow",))
            return

        for row_index, row in enumerate(rows):
            tag = "evenrow" if row_index % 2 == 0 else "oddrow"
            tree.insert("", "end", values=tuple(row), tags=(tag,))
    except Exception as e:
        show_delivery_error(delivery_win, "Error", f"Failed to load other item deliveries: {str(e)}")


def on_closing(conn, delivery_win):
    conn.close()
    close_window_and_focus_parent(delivery_win)
