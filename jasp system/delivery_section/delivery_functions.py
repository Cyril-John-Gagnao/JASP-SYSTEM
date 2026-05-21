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

# Define shared popup colors for delivery actions.
SUCCESS_GREEN = "#00c853"
CANCEL_RED = "#dc2626"


def get_delivery_unit_options():
    # Load inventory unit options for other-item delivery forms.
    conn = None
    try:
        conn, cursor = open_inventory_connection()
        return fetch_inventory_unit_options(conn, cursor)
    except Exception:
        return ["pieces", "kilograms", "bag/sack", "meters", "liters", "boxes", "sets", "rolls"]
    finally:
        if conn:
            conn.close()


def get_delivery_item_options():
    # Load active POS other-item names and units for the editable delivery dropdown.
    conn = None
    try:
        conn, cursor = open_inventory_connection()
        cursor.execute("""
            SELECT name, COALESCE(unit, '')
            FROM items
            WHERE COALESCE(status, 'Active') = 'Active'
              AND COALESCE(TRIM(name), '') <> ''
              AND LOWER(name) NOT IN ('cement', 'fine sand', 'chb blocks')
            GROUP BY LOWER(name)
            ORDER BY LOWER(name) ASC
        """)
        return [(row[0], row[1]) for row in cursor.fetchall()]
    except Exception:
        return []
    finally:
        if conn:
            conn.close()


def center_window(window, width=560, height=430, parent=None):
    # Center a delivery popup over its parent window or the screen.
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
    # Show a modal delivery message popup with a colored accent.
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
        # Close the delivery popup.
        popup.destroy()

    # Build the single OK action button for the popup.
    tk.Button(content, text="OK", command=close_popup, bg=accent_color, fg="white", activebackground=accent_color, font=("Arial", 15, "bold"), relief="flat", width=14, pady=9).pack()
    popup.bind("<Return>", lambda _event: close_popup())
    popup.bind("<Escape>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    center_window(popup, 540, 290, parent)
    parent.wait_window(popup)


def show_delivery_error(parent, title, message):
    # Display an error popup using the delivery error color.
    show_delivery_popup(parent, title, message, CANCEL_RED)


def show_delivery_success(parent, title, message):
    # Display a success popup using the delivery success color.
    show_delivery_popup(parent, title, message, SUCCESS_GREEN)


def ask_delivery_confirmation(parent, title, message, confirm_text="Yes"):
    # Show a modal confirmation dialog and return True only when confirmed.
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
        # Mark the dialog as confirmed before closing it.
        result["confirmed"] = True
        popup.destroy()

    def cancel():
        # Close the dialog without confirming the action.
        popup.destroy()

    # Build the cancel and confirm buttons.
    tk.Button(button_row, text="Cancel", command=cancel, bg="#64748b", fg="white", activebackground="#475569", font=("Arial", 14, "bold"), relief="flat", width=13, pady=9).pack(side="left", padx=8)
    tk.Button(button_row, text=confirm_text, command=confirm, bg="#2563eb", fg="white", activebackground="#1d4ed8", font=("Arial", 14, "bold"), relief="flat", width=13, pady=9).pack(side="left", padx=8)
    popup.bind("<Return>", lambda _event: confirm())
    popup.bind("<Escape>", lambda _event: cancel())
    popup.protocol("WM_DELETE_WINDOW", cancel)
    center_window(popup, 600, 330, parent)
    parent.wait_window(popup)
    return result["confirmed"]


def go_back(delivery_win):
    # Close the delivery window and return focus to its parent.
    close_window_and_focus_parent(delivery_win)


def refresh_data(load_data):
    # Refresh the active delivery table.
    load_data()


# Format a numeric value as Philippine peso currency text.
def money(value):
    return f"₱{value:,.2f}"


def parse_money(value):
    # Convert displayed currency text back into a float.
    cleaned = "".join(ch for ch in str(value) if ch.isdigit() or ch in ".-")
    return float(cleaned or 0)


def is_blank(value):
    # Treat None and whitespace-only strings as empty values.
    return str(value or "").strip() == ""


def get_tk_var_text(var):
    # Safely read text from normal or Tcl-backed Tkinter variables.
    try:
        return str(var.get()).strip()
    except tk.TclError:
        return str(var._tk.globalgetvar(var._name)).strip()


def parse_positive_int(value, field_name, parent):
    # Validate that a form value is a positive integer.
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
    # Validate that a form value is numeric and optionally allow zero.
    normalized_value = str(value or "").strip().lower()
    if allow_zero and normalized_value in ("free", "none", "no fee", "n/a", "na"):
        return 0
    try:
        normalized_value = normalized_value.replace("₱", "").replace(",", "")
        parsed = float(normalized_value)
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


def format_delivery_money(value):
    # Format delivery monetary values with a peso sign for table display.
    try:
        return f"₱{float(value or 0):,.2f}"
    except (TypeError, ValueError):
        return "₱0.00"


def open_date_calendar(parent, date_var, on_select=None):
    # Open a small calendar popup for selecting a YYYY-MM-DD date.
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
        # Apply the selected day and run the optional callback.
        date_var.set(f"{year_var.get():04d}-{month_var.get():02d}-{day:02d}")
        if callable(on_select):
            on_select()
        cal_win.destroy()

    def change_month(delta):
        # Move the calendar view backward or forward by one month.
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
        # Redraw the calendar grid for the selected month and year.
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

    tk.Button(header, text="Close", command=cal_win.destroy, bg="#dc2626", fg="white", activebackground="#b91c1c", activeforeground="white", relief="solid", bd=1, font=("Arial", 12, "bold"), padx=10, pady=4).pack(side="right", padx=(8, 0))
    tk.Button(header, text=">", command=lambda: change_month(1), bg="#e0f2fe", relief="solid", bd=1, width=5, font=("Arial", 13, "bold")).pack(side="right")
    tk.Button(header, text="<", command=lambda: change_month(-1), bg="#e0f2fe", relief="solid", bd=1, width=5, font=("Arial", 13, "bold")).pack(side="left")
    tk.Label(header, textvariable=title_var, bg="#ffffff", fg="#1e293b", font=("Arial", 15, "bold"), width=20).pack(side="left", padx=10)

    render_calendar()

    # Position the calendar near the center of the parent window.
    cal_win.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (cal_win.winfo_width() // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (cal_win.winfo_height() // 2)
    cal_win.geometry(f"470x390+{x}+{y}")


from .delivery_summary import open_delivery_summary


def open_other_items_form(parent_win, conn, cursor, load_data, display_option_var, record_values=None):
    # Open the add/edit form for non-CHB delivery records.
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

    # Define local button borders for the other-items form.
    button_border = {
        "bd": 2,
        "relief": "solid",
        "highlightthickness": 1,
        "highlightbackground": "black",
        "highlightcolor": "black",
    }

    content = tk.Frame(form_win, bg="#ffffff", padx=24, pady=20)
    content.pack(fill="both", expand=True)

    # Build the form title for add or edit mode.
    tk.Label(
        content,
        text="Edit Other Item Delivery" if is_edit_mode else "Other Items to Deliver",
        bg="#ffffff",
        fg="#2563eb",
        font=("Arial", 22, "bold")
    ).pack(anchor="w", pady=(0, 12))

    form_bg = tk.Frame(content, bg="#fef3c7", bd=1, relief="flat")
    form_bg.pack(fill="x")

    # Build the input grid for other-item delivery fields.
    form = tk.Frame(form_bg, bg="#fef3c7")
    form.pack(fill="x", padx=16, pady=12)
    form.columnconfigure(0, weight=0)
    form.columnconfigure(1, weight=1)

    # Build the transaction date field with a calendar picker.
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

    # Build the delivery date field with a calendar picker.
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

    # Build a searchable item field that filters active POS item names while allowing manual input.
    item_name_options = get_delivery_item_options()
    item_unit_by_name = {name: unit for name, unit in item_name_options}
    item_name_list = [name for name, _unit in item_name_options]
    item_name_var = tk.StringVar()
    unit_of_measurement_var = tk.StringVar()
    delivery_fee_var = tk.StringVar()
    item_name_frame = tk.Frame(form, bg="#fef3c7")
    item_name_entry = tk.Entry(
        item_name_frame,
        textvariable=item_name_var,
        width=26,
        font=("Arial", 13),
        bd=1,
        relief="solid",
        bg="white"
    )
    item_name_entry.pack(side="left", fill="x", expand=True)
    item_suggestion_box = tk.Listbox(
        form,
        height=5,
        font=("Arial", 13),
        bd=1,
        relief="solid",
        activestyle="none"
    )

    def matching_item_names():
        # Return matching inventory names for the typed item search text.
        typed_text = item_name_var.get().strip().lower()
        if typed_text:
            return [name for name in item_name_list if typed_text in name.lower()]
        return item_name_list

    def hide_item_suggestions():
        # Hide the item search dropdown.
        item_suggestion_box.place_forget()

    def show_item_suggestions(options=None):
        # Show matching item names under the Item Name field.
        options = matching_item_names() if options is None else options
        item_suggestion_box.delete(0, tk.END)
        for option in options:
            item_suggestion_box.insert(tk.END, option)
        if not options:
            hide_item_suggestions()
            return
        form.update_idletasks()
        x_pos = item_name_frame.winfo_x()
        y_pos = item_name_frame.winfo_y() + item_name_frame.winfo_height()
        item_suggestion_box.place(x=x_pos, y=y_pos, width=item_name_frame.winfo_width(), height=min(150, 30 * len(options)))
        item_suggestion_box.lift()

    def select_item_suggestion(event=None):
        # Copy the selected suggested item into the field and fill its unit.
        selection = item_suggestion_box.curselection()
        if selection:
            selected_name = item_suggestion_box.get(selection[0])
            item_name_var.set(selected_name)
            unit_of_measurement_var.set(item_unit_by_name.get(selected_name, ""))
        hide_item_suggestions()
        item_name_entry.focus_set()
        item_name_entry.icursor(tk.END)

    def autofill_unit_for_typed_item():
        # Fill unit when the typed item exactly matches an inventory item.
        typed_name = item_name_var.get().strip().lower()
        for item_name, unit in item_unit_by_name.items():
            if item_name.lower() == typed_name:
                unit_of_measurement_var.set(unit)
                return

    def filter_item_name_options(event=None):
        # Update suggestions as the user types in the item name field.
        ignored_keys = {"Left", "Right", "Return", "Escape", "Tab"}
        if event and event.keysym in ignored_keys:
            if event.keysym == "Escape":
                hide_item_suggestions()
            return
        if event and event.keysym == "Down" and item_suggestion_box.winfo_ismapped():
            item_suggestion_box.focus_set()
            item_suggestion_box.selection_set(0)
            return
        show_item_suggestions()

    def toggle_item_suggestions():
        # Open or close the full searchable item list.
        if item_suggestion_box.winfo_ismapped():
            hide_item_suggestions()
        else:
            show_item_suggestions(item_name_list)
            item_name_entry.focus_set()

    tk.Button(
        item_name_frame,
        text="▼",
        command=toggle_item_suggestions,
        bg="#e2e8f0",
        fg="#1e293b",
        font=("Arial", 10, "bold"),
        width=2,
        bd=1,
        relief="solid"
    ).pack(side="left", padx=(4, 0))
    item_name_entry.bind("<KeyRelease>", filter_item_name_options)
    item_name_entry.bind("<FocusIn>", lambda event: show_item_suggestions(matching_item_names()) if item_name_var.get().strip() else None)
    item_name_entry.bind("<FocusOut>", lambda event: (autofill_unit_for_typed_item(), form_win.after(150, hide_item_suggestions)))
    item_name_entry.bind("<Return>", lambda event: (autofill_unit_for_typed_item(), hide_item_suggestions()))
    item_suggestion_box.bind("<ButtonRelease-1>", select_item_suggestion)
    item_suggestion_box.bind("<Return>", select_item_suggestion)
    item_suggestion_box.bind("<Escape>", lambda event: hide_item_suggestions())

    # Define the remaining other-item delivery input fields.
    fields = [
        ("Item Name", item_name_frame),
        ("Quantity", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
        ("Unit of Measurement", ttk.Combobox(form, textvariable=unit_of_measurement_var, values=get_delivery_unit_options(), width=26, font=("Arial", 13))),
        ("Delivery Address", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
        ("Delivery Driver", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
        ("Helper", tk.Entry(form, width=28, font=("Arial", 13), bd=1, relief="solid", bg="white")),
        ("Delivery Fee", ttk.Combobox(form, textvariable=delivery_fee_var, values=["Free", "0", "50", "100", "150", "200"], width=26, font=("Arial", 13))),
    ]

    # Render labels and inputs, then keep references by label name.
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

    # Build the action button row for save, update, delete, or cancel.
    button_row = tk.Frame(content, bg="#ffffff")
    button_row.pack(fill="x", pady=(18, 0))

    if is_edit_mode:
        # Fill form inputs with the selected record when editing.
        transaction_date_var.set(str(record_values[1])[:10])
        delivery_date_var.set(str(record_values[2])[:10])
        item_name_var.set(record_values[3])
        entry_by_label["Quantity"].insert(0, record_values[4])
        unit_of_measurement_var.set(record_values[5])
        entry_by_label["Delivery Address"].insert(0, record_values[6])
        entry_by_label["Delivery Driver"].insert(0, record_values[7])
        entry_by_label["Helper"].insert(0, record_values[8])
        delivery_fee_var.set(record_values[9])

    def get_other_item_form_values():
        # Read and validate all other-item delivery form values.
        transaction_date = transaction_date_var.get().strip()
        delivery_date = delivery_date_var.get().strip()
        item_name = item_name_var.get().strip()
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
        # Validate and save a new non-CHB delivery record.
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
        # Validate and update the selected non-CHB delivery record.
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
        # Confirm and delete the selected non-CHB delivery record.
        item_name = item_name_var.get().strip() or "this item"
        if not ask_delivery_confirmation(form_win, "Confirm Delete", f"Delete delivery record for {item_name}?\n\nThis action cannot be undone.", "Delete"):
            return

        delete_other_item_delivery_record(conn, cursor, selected_other_id)
        display_option_var.set("Option 2")
        load_data()
        form_win.destroy()
        show_delivery_success(parent_win, "Success", "Other item delivery deleted successfully!")

    # Place the correct form action buttons for add or edit mode.
    tk.Button(button_row, text="Cancel", command=form_win.destroy, bg="#64748b", fg="white", font=("Arial", 12, "bold"), width=12, pady=7, cursor="hand2", **button_border).pack(side="right", padx=6)
    if is_edit_mode:
        tk.Button(button_row, text="Delete", command=delete_other_item_delivery, bg="#dc2626", fg="white", font=("Arial", 12, "bold"), width=12, pady=7, cursor="hand2", **button_border).pack(side="right", padx=6)
        tk.Button(button_row, text="Update", command=update_other_item_delivery, bg="#1e40af", fg="white", font=("Arial", 12, "bold"), width=12, pady=7, cursor="hand2", **button_border).pack(side="right", padx=6)
    else:
        tk.Button(button_row, text="Save", command=save_other_item_delivery, bg="#15803d", fg="white", font=("Arial", 12, "bold"), width=12, pady=7, cursor="hand2", **button_border).pack(side="right", padx=6)

    center_window(form_win, 600, 500, parent_win)


def auto_calc(event, blocks_entry, payment_var, result_label):
    # Recalculate helper salary from delivered blocks and salary per block.
    try:
        blocks = int(blocks_entry.get() or 0)
        payment_per = float(payment_var.get() or 2.0)
        total = blocks * payment_per

        result_label.config(text=f"Total Payment for Helper: ₱{total:,.2f}")

    except:
        blocks_entry.delete(0, tk.END)
        result_label.config(text="Total Payment for Helper: ₱0")


def clear_form(transaction_date_var, date_var, worker_entry, driver_entry, address_entry, blocks_entry, delivery_fee_entry, payment_var, result_label, selected_id):
    # Reset the CHB delivery form fields and selected record.
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
    # Read and validate CHB delivery inputs before saving.
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

    # Validate numeric CHB delivery fields.
    blocks = parse_positive_int(blocks_text, "Blocks to be delivered", delivery_win)
    if blocks is None:
        return

    delivery_fee = parse_positive_number(delivery_fee_text, "Delivery fee", delivery_win, allow_zero=True)
    if delivery_fee is None:
        return

    payment_per = parse_positive_number(payment_text, "Helper salary", delivery_win)
    if payment_per is None:
        return

    total = blocks * payment_per

    # Confirm and insert the new CHB delivery record.
    if not ask_delivery_confirmation(delivery_win, "Confirm Save", f"Save delivery record for {worker}?", "Save"):
        return

    insert_delivery(conn, cursor, transaction_date, date, worker, driver_name, address, blocks, delivery_fee, payment_per, total)
    load_data()
    clear_form()
    show_delivery_success(delivery_win, "Success", "Delivery record saved successfully!")


def update_delivery(conn, cursor, delivery_win, selected_id, transaction_date_var, worker_entry, date_var, driver_entry, address_entry, blocks_entry, delivery_fee_entry, payment_var, load_data, clear_form):
    # Require a selected CHB delivery row before updating.
    if not selected_id.get():
        show_delivery_error(delivery_win, "Error", "Select a record")
        return

    # Read and validate edited CHB delivery inputs.
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

    # Validate numeric CHB delivery fields before updating.
    blocks = parse_positive_int(blocks_text, "Blocks to be delivered", delivery_win)
    if blocks is None:
        return

    delivery_fee = parse_positive_number(delivery_fee_text, "Delivery fee", delivery_win, allow_zero=True)
    if delivery_fee is None:
        return

    payment_per = parse_positive_number(payment_text, "Helper salary", delivery_win)
    if payment_per is None:
        return

    total = blocks * payment_per

    # Confirm and update the selected CHB delivery record.
    if not ask_delivery_confirmation(delivery_win, "Confirm Update", f"Update record for {worker}?", "Update"):
        return

    update_delivery_record(conn, cursor, selected_id.get(), transaction_date, date, worker, driver_name, address, blocks, delivery_fee, payment_per, total)
    load_data()
    clear_form()
    show_delivery_success(delivery_win, "Success", "Record updated successfully!")


def delete_delivery(conn, cursor, delivery_win, selected_id, worker_entry, load_data, clear_form):
    # Require a selected CHB delivery row before deleting.
    if not selected_id.get():
        show_delivery_error(delivery_win, "Error", "Select a record")
        return

    # Confirm and delete the selected CHB delivery record.
    if not ask_delivery_confirmation(delivery_win, "Confirm Delete", f"Delete record for {worker_entry.get()}?\n\nThis action cannot be undone.", "Delete"):
        return

    delete_delivery_record(conn, cursor, selected_id.get())
    load_data()
    clear_form()
    show_delivery_success(delivery_win, "Success", "Record deleted successfully!")


def on_tree_configure(event, tree):
    # Allow the delivery table to finish layout updates after resizing.
    tree.update_idletasks()


def on_select(event, tree, selected_id, transaction_date_var, date_var, worker_entry, driver_entry, address_entry, blocks_entry, delivery_fee_entry, auto_calc):
    # Load the selected CHB delivery table row into the form.
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
        delivery_fee_entry.insert(0, str(values[7]).replace("₱", "").replace(",", ""))
        auto_calc()


def load_data(event, cursor, tree, search_var, sort_var, delivery_win):
    # Load today's CHB delivery rows into the table.
    try:
        # Clear existing CHB delivery table rows before reloading.
        for row in tree.get_children():
            tree.delete(row)

        keyword = search_var.get().lower()
        sort_option = sort_var.get()
        today = datetime.now().strftime("%Y-%m-%d")
        rows = fetch_delivery_rows(cursor, keyword, sort_option, today)

        # Insert matching CHB rows or a friendly empty row.
        row_index = 0
        if not rows:
            message = "No matching records found." if keyword else "No deliveries for today"
            tree.insert("", "end", values=("", today, today, message, "", "", "", "", "", ""), tags=('oddrow',))
            return

        for row in rows:
            tag = 'evenrow' if row_index % 2 == 0 else 'oddrow'
            display_row = list(row)
            display_row[7] = format_delivery_money(display_row[7])
            display_row[8] = format_delivery_money(display_row[8])
            tree.insert("", "end", values=tuple(display_row), tags=(tag,))
            row_index += 1
    except Exception as e:
        show_delivery_error(delivery_win, "Error", f"Failed to load data: {str(e)}")


def load_other_items_data(event, cursor, tree, search_var, sort_var, delivery_win):
    # Load today's other-item delivery rows into the table.
    try:
        # Clear existing other-item table rows before reloading.
        for row in tree.get_children():
            tree.delete(row)

        keyword = search_var.get().lower()
        sort_option = sort_var.get()
        today = datetime.now().strftime("%Y-%m-%d")
        rows = fetch_other_item_delivery_rows(cursor, keyword, sort_option, today)

        # Insert matching other-item rows or a friendly empty row.
        if not rows:
            message = "No matching records found." if keyword else "No other item deliveries for today"
            tree.insert("", "end", values=("", today, today, message, "", "", "", "", "", "", ""), tags=("oddrow",))
            return

        for row_index, row in enumerate(rows):
            tag = "evenrow" if row_index % 2 == 0 else "oddrow"
            display_row = list(row)
            display_row[9] = format_delivery_money(display_row[9])
            tree.insert("", "end", values=tuple(display_row), tags=(tag,))
    except Exception as e:
        show_delivery_error(delivery_win, "Error", f"Failed to load other item deliveries: {str(e)}")


def on_closing(conn, delivery_win):
    # Close the delivery database connection before leaving the window.
    conn.close()
    close_window_and_focus_parent(delivery_win)
