import sys
import tkinter as tk
from tkinter import messagebox, ttk
from datetime import datetime

from .chb_database import (
    CHB_ITEM_NAME,
    CHB_STATE_ID,
    CEMENT_ITEM_NAME,
    FINE_SAND_ITEM_NAME,
    FINE_SAND_BAGS_PER_CUBIC_METER,
    ensure_chb_inventory,
    adjust_chb_inventory,
    adjust_material_inventory,
    fetch_material_stock,
)
from .summary import open_date_calendar, open_period_summary

# Define shared popup colors for success and error dialogs.
SUCCESS_GREEN = "#16a34a"
ERROR_RED = "#dc2626"


def fine_sand_bags_to_cubic_meters(bags):
    # Convert fine sand bag count into the cubic meter unit stored in inventory.
    return float(bags or 0) / FINE_SAND_BAGS_PER_CUBIC_METER


def format_stock_quantity(quantity):
    # Format material stock without unnecessary trailing decimal zeros.
    quantity = float(quantity or 0)
    return f"{quantity:,.3f}".rstrip("0").rstrip(".")


def center_popup(window, width, height, parent=None):
    # Center a popup over its parent window or the screen.
    window.update_idletasks()
    if parent and parent.winfo_exists():
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    else:
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def show_chb_popup(parent, title, message, accent_color):
    # Show a modal CHB message popup with a colored accent.
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)

    tk.Frame(popup, bg=accent_color, height=12).pack(fill="x")

    content = tk.Frame(popup, bg="#ffffff", padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text=title,
        bg="#ffffff",
        fg=accent_color,
        font=("Arial", 28, "bold")
    ).pack(pady=(0, 14))

    tk.Label(
        content,
        text=message,
        bg="#ffffff",
        fg="#111827",
        font=("Arial", 17),
        wraplength=440,
        justify="center"
    ).pack(pady=(0, 28))

    def close_popup():
        # Close the modal popup when the user confirms or cancels.
        popup.destroy()

    # Build the single OK action button for the message popup.
    ok_btn = tk.Button(
        content,
        text="OK",
        command=close_popup,
        bg=accent_color,
        fg="white",
        activebackground=accent_color,
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
    center_popup(popup, 560, 300, parent)
    parent.wait_window(popup)


def show_chb_error(parent, title, message):
    # Display an error popup using the CHB error color.
    show_chb_popup(parent, title, message, ERROR_RED)


def show_chb_success(parent, title, message):
    # Display a success popup using the CHB success color.
    show_chb_popup(parent, title, message, SUCCESS_GREEN)


def ask_chb_confirmation(parent, title, message, confirm_text="Yes", cancel_text="Cancel", accent_color="#2563eb"):
    # Show a modal confirmation dialog and return True only when confirmed.
    result = {"confirmed": False}

    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)

    tk.Frame(popup, bg=accent_color, height=12).pack(fill="x")

    content = tk.Frame(popup, bg="#ffffff", padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text=title,
        bg="#ffffff",
        fg=accent_color,
        font=("Arial", 26, "bold")
    ).pack(pady=(0, 14))

    tk.Label(
        content,
        text=message,
        bg="#ffffff",
        fg="#111827",
        font=("Arial", 16),
        wraplength=470,
        justify="center"
    ).pack(pady=(0, 28))

    button_row = tk.Frame(content, bg="#ffffff")
    button_row.pack()

    def confirm():
        # Mark the dialog as confirmed before closing it.
        result["confirmed"] = True
        popup.destroy()

    def cancel():
        # Close the dialog without changing the default cancelled result.
        popup.destroy()

    # Build the cancel and confirm action buttons.
    tk.Button(
        button_row,
        text=cancel_text,
        command=cancel,
        bg="#64748b",
        fg="white",
        activebackground="#475569",
        font=("Arial", 14, "bold"),
        relief="flat",
        width=13,
        pady=9
    ).pack(side="left", padx=8)

    tk.Button(
        button_row,
        text=confirm_text,
        command=confirm,
        bg=accent_color,
        fg="white",
        activebackground=accent_color,
        font=("Arial", 14, "bold"),
        relief="flat",
        width=13,
        pady=9
    ).pack(side="left", padx=8)

    popup.bind("<Return>", lambda _event: confirm())
    popup.bind("<Escape>", lambda _event: cancel())
    popup.protocol("WM_DELETE_WINDOW", cancel)
    center_popup(popup, 600, 330, parent)
    parent.wait_window(popup)
    return result["confirmed"]


def notify_inventory_views():
    """Refresh open inventory/POS windows if they registered callbacks."""
    # Call registered refresh callbacks in related modules when inventory changes.
    for module_name, callback_name in (("inventory_module", "inventory_refresh_callback"), ("inventory", "inventory_refresh_callback"), ("pos", "pos_refresh_callback")):
        module = sys.modules.get(module_name)
        callback = getattr(module, callback_name, None) if module else None
        if callable(callback):
            try:
                callback()
            except Exception:
                pass


def get_responsible_user():
    # Read the active dashboard user and fall back to Admin when unavailable.
    try:
        from main_dashboard import session
        return session.get_current_username("Admin")
    except Exception:
        return "Admin"


def is_blank(value):
    # Treat None and whitespace-only strings as empty form values.
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
        show_chb_error(parent, "Error", f"{field_name} must be an integer number.")
        return None
    if parsed <= 0:
        show_chb_error(parent, "Error", f"{field_name} must be greater than zero.")
        return None
    return parsed


def parse_positive_number(value, field_name, parent):
    # Validate that a form value is a positive numeric value.
    try:
        parsed = float(str(value).strip())
    except (TypeError, ValueError):
        show_chb_error(parent, "Error", f"{field_name} must be a numeric number.")
        return None
    if parsed <= 0:
        show_chb_error(parent, "Error", f"{field_name} must be greater than zero.")
        return None
    return parsed


def go_back(win):
    # Close the current window and restore focus to its parent.
    from window_utils import close_window_and_focus_parent
    close_window_and_focus_parent(win)


def refresh_data(load_data, update_total_blocks):
    # Refresh the production table and the CHB stock display together.
    load_data()
    update_total_blocks()


def create_chb_adjustments_table(cursor):
    # Create the adjustment history table used for manual CHB stock changes.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chb_adjustments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            adjustment_date TEXT NOT NULL,
            adjustment_type TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            reason TEXT NOT NULL,
            responsible_user TEXT DEFAULT '',
            ts TEXT NOT NULL
        )
    """)


def apply_chb_stock_adjustment(conn, cursor, adjustment_date, adjustment_type, quantity, reason):
    # Prepare CHB inventory and adjustment storage before applying a manual change.
    ensure_chb_inventory(conn, cursor)
    create_chb_adjustments_table(cursor)

    # Read the current available CHB stock to validate the requested adjustment.
    cursor.execute(
        "SELECT COALESCE(available, 0) FROM chb_inventory_state WHERE id=?",
        (CHB_STATE_ID,)
    )
    row = cursor.fetchone()
    available = int(row[0] or 0) if row else 0
    signed_quantity = quantity if adjustment_type == "Add" else -quantity
    new_available = available + signed_quantity

    if new_available < 0:
        return False, "Adjustment cannot make available stock negative."

    # Update the CHB state, inventory item, and adjustment history in one operation.
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        """
        UPDATE chb_inventory_state
        SET available = available + ?,
            updated_ts = ?
        WHERE id = ?
        """,
        (signed_quantity, ts, CHB_STATE_ID)
    )
    cursor.execute(
        "UPDATE items SET quantity = ? WHERE name=?",
        (new_available, CHB_ITEM_NAME)
    )
    cursor.execute(
        """
        INSERT INTO chb_adjustments
            (adjustment_date, adjustment_type, quantity, reason, responsible_user, ts)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (adjustment_date, adjustment_type, quantity, reason, get_responsible_user(), ts)
    )
    conn.commit()
    notify_inventory_views()
    return True, ""


def open_chb_adjustment_form(conn, cursor, win, update_total_blocks):
    # Open a modal form for adding or subtracting available CHB stock.
    form = tk.Toplevel(win)
    form.title("Adjust CHB Stock")
    form.transient(win)
    form.grab_set()
    form.configure(bg="#fef3c7")
    form.resizable(False, False)

    card = tk.Frame(form, bg="#fef3c7", padx=28, pady=24)
    card.pack(fill="both", expand=True)

    # Show the adjustment form title and current available stock.
    tk.Label(card, text="Adjust CHB Stock", bg="#fef3c7", fg="#1e40af", font=("Arial", 22, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))

    cursor.execute("SELECT COALESCE(available, 0) FROM chb_inventory_state WHERE id=?", (CHB_STATE_ID,))
    available_row = cursor.fetchone()
    available = int(available_row[0] or 0) if available_row else 0
    tk.Label(card, text=f"Current Available: {available:,}", bg="#fef3c7", fg="#111827", font=("Arial", 15, "bold")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 14))

    adjustment_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    adjustment_type_var = tk.StringVar(value="Add")
    quantity_var = tk.StringVar()
    reason_text = tk.Text(card, width=32, height=4, font=("Arial", 13), bd=1, relief="solid")

    # Build the adjustment date field with a calendar picker.
    tk.Label(card, text="Adjustment Date", bg="#fef3c7", font=("Arial", 13, "bold")).grid(row=2, column=0, sticky="w", pady=8)
    date_frame = tk.Frame(card, bg="#fef3c7")
    date_frame.grid(row=2, column=1, sticky="ew", padx=(12, 0), pady=8)
    date_frame.columnconfigure(0, weight=1)
    tk.Entry(date_frame, textvariable=adjustment_date_var, width=18, font=("Arial", 13), bd=1, relief="solid").grid(row=0, column=0, sticky="ew")
    tk.Button(
        date_frame,
        text="Calendar",
        command=lambda: open_date_calendar(form, adjustment_date_var),
        bg="#3b82f6",
        fg="white",
        font=("Arial", 10, "bold"),
        padx=8,
        pady=2,
        bd=1,
        relief="solid"
    ).grid(row=0, column=1, padx=(6, 0))

    # Build the adjustment type, quantity, and reason fields.
    tk.Label(card, text="Type", bg="#fef3c7", font=("Arial", 13, "bold")).grid(row=3, column=0, sticky="w", pady=8)
    ttk.Combobox(card, textvariable=adjustment_type_var, values=("Add", "Subtract"), state="readonly", width=21, font=("Arial", 13)).grid(row=3, column=1, sticky="ew", padx=(12, 0), pady=8)

    tk.Label(card, text="Quantity", bg="#fef3c7", font=("Arial", 13, "bold")).grid(row=4, column=0, sticky="w", pady=8)
    tk.Entry(card, textvariable=quantity_var, width=24, font=("Arial", 13), bd=1, relief="solid").grid(row=4, column=1, sticky="ew", padx=(12, 0), pady=8)

    tk.Label(card, text="Reason", bg="#fef3c7", font=("Arial", 13, "bold")).grid(row=5, column=0, sticky="nw", pady=8)
    reason_text.grid(row=5, column=1, sticky="ew", padx=(12, 0), pady=8)

    def submit_adjustment():
        # Validate and apply the manual CHB stock adjustment.
        adjustment_date = adjustment_date_var.get().strip()
        adjustment_type = adjustment_type_var.get().strip()
        reason = reason_text.get("1.0", tk.END).strip()
        try:
            quantity = int(quantity_var.get().strip())
        except ValueError:
            show_chb_error(form, "Error", "Quantity must be a positive whole number.")
            return

        if not adjustment_date or not reason:
            show_chb_error(form, "Error", "Adjustment date and reason are required.")
            return
        if adjustment_type not in ("Add", "Subtract"):
            show_chb_error(form, "Error", "Adjustment type must be Add or Subtract.")
            return
        if quantity <= 0:
            show_chb_error(form, "Error", "Quantity must be greater than zero.")
            return

        signed_text = f"+{quantity:,}" if adjustment_type == "Add" else f"-{quantity:,}"
        if not ask_chb_confirmation(
            form,
            "Confirm Adjustment",
            f"Apply CHB stock adjustment of {signed_text}?",
            confirm_text="Apply",
            cancel_text="Cancel",
            accent_color="#2563eb"
        ):
            return

        ok, error = apply_chb_stock_adjustment(conn, cursor, adjustment_date, adjustment_type, quantity, reason)
        if not ok:
            show_chb_error(form, "Error", error)
            return

        update_total_blocks()
        form.destroy()
        show_chb_success(win, "Success", "CHB stock adjusted successfully!")

    # Build the form action buttons.
    button_row = tk.Frame(card, bg="#fef3c7")
    button_row.grid(row=6, column=0, columnspan=2, pady=(20, 0))
    tk.Button(button_row, text="Apply", command=submit_adjustment, bg=SUCCESS_GREEN, fg="white", font=("Arial", 13, "bold"), width=13, pady=8, bd=2, relief="solid").pack(side="left", padx=8)
    tk.Button(button_row, text="Cancel", command=form.destroy, bg=ERROR_RED, fg="white", font=("Arial", 13, "bold"), width=13, pady=8, bd=2, relief="solid").pack(side="left", padx=8)

    form.bind("<Escape>", lambda _event: form.destroy())
    center_popup(form, 560, 500, win)


def update_pay(event, cement_entry, pay_rate_var, result_label):
    # Recalculate displayed worker pay from cement count and pay rate.
    try:
        cement = int(cement_entry.get() or 0)
        pay = cement * float(pay_rate_var.get() or 0)
        result_label.config(text=f"| Pay: ₱{pay:,.2f}")
    except:
        result_label.config(text="| Pay: ₱0")


def format_material_stock(cursor, item_name):
    # Build the displayed stock text for cement or fine sand.
    stock = fetch_material_stock(cursor, item_name)
    if item_name == FINE_SAND_ITEM_NAME:
        bags = stock * FINE_SAND_BAGS_PER_CUBIC_METER
        return f"Available: {format_stock_quantity(stock)} cubic meters\nEquivalent Bags: {format_stock_quantity(bags)} bags"
    return f"Available: {format_stock_quantity(stock)}"


def refresh_material_dropdowns(cursor, cement_stock_var=None, sand_stock_var=None, cement_stock_combo=None, sand_stock_combo=None):
    # Refresh the material stock labels/dropdowns shown beside production inputs.
    cement_text = format_material_stock(cursor, CEMENT_ITEM_NAME)
    sand_text = format_material_stock(cursor, FINE_SAND_ITEM_NAME)

    if cement_stock_var is not None:
        cement_stock_var.set(cement_text)
    if sand_stock_var is not None:
        sand_stock_var.set(sand_text)

    if cement_stock_combo is not None:
        try:
            cement_stock_combo.config(values=[cement_text])
        except tk.TclError:
            pass
    if sand_stock_combo is not None:
        try:
            sand_stock_combo.config(values=[sand_text])
        except tk.TclError:
            pass


def validate_material_stock(cursor, cement_needed, sand_needed, selected_id=None, return_existing_materials=True):
    # Compare requested material usage with available stock, accounting for edits.
    old_cement = 0
    old_sand = 0
    if selected_id:
        cursor.execute(
            """
            SELECT COALESCE(cement_bags, 0), COALESCE(fine_sand, 0), COALESCE(material_inventory_applied, 0)
            FROM chb_production
            WHERE id=?
            """,
            (selected_id,)
        )
        old_row = cursor.fetchone()
        if old_row and int(old_row[2] or 0):
            old_cement = int(old_row[0] or 0)
            old_sand = float(old_row[1] or 0)

    cement_delta = int(cement_needed) - old_cement
    sand_delta = fine_sand_bags_to_cubic_meters(float(sand_needed or 0) - old_sand)
    cement_available = fetch_material_stock(cursor, CEMENT_ITEM_NAME)
    sand_available = fetch_material_stock(cursor, FINE_SAND_ITEM_NAME)

    if cement_delta > cement_available:
        return False, f"Not enough cement. Available: {cement_available:,}, needed: {cement_delta:,}."
    if sand_delta > sand_available:
        return False, "Not enough fine sand stock available."
    return True, ""


def get_production_inventory_values(cursor, production_id):
    # Fetch the stock-impact values from one production record.
    cursor.execute(
        """
        SELECT COALESCE(total_blocks, 0), COALESCE(cement_bags, 0), COALESCE(fine_sand, 0), COALESCE(material_inventory_applied, 0)
        FROM chb_production
        WHERE id=?
        """,
        (production_id,)
    )
    row = cursor.fetchone()
    if not row:
        return 0, 0, 0, 0
    return int(row[0] or 0), int(row[1] or 0), float(row[2] or 0), int(row[3] or 0)


def ask_return_materials(win, action, cement, sand):
    # Ask whether consumed materials should be returned before editing/deleting.
    if cement <= 0 and sand <= 0:
        return False

    return ask_chb_confirmation(
        win,
        "Return Materials",
        (
            f"Do you want to return the materials from this production record to inventory before {action}?\n\n"
            f"Cement: {cement:,} bag/s\n"
            f"Fine Sand: {sand:,} bag/s"
        ),
        confirm_text="Return",
        cancel_text="Do Not Return",
        accent_color="#2563eb"
    )


def auto_sand(event, cement_entry, sand_entry, pay_rate_var, blocks_entry, result_label):
    # Auto-fill fine sand, block count, and pay based on cement bags.
    try:
        cement = int(cement_entry.get() or 0)
        sand = cement * 15
        sand_entry.delete(0, tk.END)
        sand_entry.insert(0, str(sand))

        blocks = cement * 75
        blocks_entry.delete(0, tk.END)
        blocks_entry.insert(0, str(blocks))

        update_pay(event, cement_entry, pay_rate_var, result_label)

    except:
        sand_entry.delete(0, tk.END)
        blocks_entry.delete(0, tk.END)
        blocks_entry.insert(0, "0")
        result_label.config(text="| Pay: ₱0")


def clear_form(worker_entry, cement_entry, sand_entry, blocks_entry, result_label, selected_id):
    # Reset the CHB production form fields and selected record.
    worker_entry.delete(0, tk.END)
    cement_entry.delete(0, tk.END)
    sand_entry.delete(0, tk.END)
    blocks_entry.delete(0, tk.END)
    blocks_entry.insert(0, "0")
    result_label.config(text="| Pay: ₱0")
    selected_id.set("")


def confirm_clear_form(win, worker_entry, cement_entry, sand_entry, blocks_entry, result_label, selected_id):
    # Confirm before clearing all current production form values.
    if not ask_chb_confirmation(
        win,
        "Clear Form",
        "Clear all current form inputs?",
        confirm_text="Clear",
        cancel_text="Cancel",
        accent_color="#64748b"
    ):
        return
    clear_form(worker_entry, cement_entry, sand_entry, blocks_entry, result_label, selected_id)
    show_chb_success(win, "Success", "Form cleared successfully!")


def save(conn, cursor, win, worker_entry, date_var, cement_entry, blocks_entry, pay_rate_var, load_data, update_total_blocks, clear_form, refresh_materials=None):
    # Read and validate form inputs before saving a new CHB production record.
    worker = worker_entry.get().strip()
    date = date_var.get().strip()
    cement_text = cement_entry.get().strip()
    blocks_text = blocks_entry.get().strip()
    pay_rate_text = get_tk_var_text(pay_rate_var)

    if any(is_blank(value) for value in (worker, date, cement_text, blocks_text, pay_rate_text)):
        show_chb_error(win, "Error", "All fields must not be empty.")
        return

    cement = parse_positive_int(cement_text, "Bag/s of Cement", win)
    if cement is None:
        return

    blocks = parse_positive_int(blocks_text, "Blocks", win)
    if blocks is None:
        return

    pay_rate = parse_positive_number(pay_rate_text, "Salary / 75 Blocks", win)
    if pay_rate is None:
        return

    sand = cement * 15
    pay = cement * pay_rate

    # Check raw material inventory before allowing production to be saved.
    ok, error = validate_material_stock(cursor, cement, sand)
    if not ok:
        show_chb_error(win, "Insufficient Inventory", error)
        return

    # Ask the user to confirm the new production record.
    if not ask_chb_confirmation(win, "Confirm Save", f"Save production record for {worker}?", confirm_text="Save", cancel_text="Cancel", accent_color=SUCCESS_GREEN):
        return

    # Insert the production record and deduct consumed materials.
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    responsible_user = get_responsible_user()

    cursor.execute("""
        INSERT INTO chb_production
        (production_date, worker_name, cement_bags, fine_sand, total_blocks, pay, pay_rate, material_inventory_applied, responsible_user, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (date, worker, cement, sand, blocks, pay, pay_rate, 1, responsible_user, ts))

    adjust_material_inventory(cursor, CEMENT_ITEM_NAME, -cement)
    adjust_material_inventory(cursor, FINE_SAND_ITEM_NAME, -fine_sand_bags_to_cubic_meters(sand))
    conn.commit()

    # Increase CHB stock and refresh all visible production/inventory views.
    adjust_chb_inventory(conn, cursor, produced_delta=blocks)
    notify_inventory_views()
    load_data()
    update_total_blocks()
    if callable(refresh_materials):
        refresh_materials()
    clear_form()
    show_chb_success(win, "Success", "Record saved successfully!")


def update(conn, cursor, win, selected_id, worker_entry, date_var, cement_entry, blocks_entry, pay_rate_var, load_data, update_total_blocks, clear_form, refresh_materials=None):
    # Require an existing selected production row before updating.
    if not selected_id.get():
        show_chb_error(win, "Error", "Select a record.")
        return

    # Read and validate the edited production form values.
    worker = worker_entry.get().strip()
    date = date_var.get().strip()
    cement_text = cement_entry.get().strip()
    blocks_text = blocks_entry.get().strip()
    pay_rate_text = get_tk_var_text(pay_rate_var)

    if any(is_blank(value) for value in (worker, date, cement_text, blocks_text, pay_rate_text)):
        show_chb_error(win, "Error", "All fields must not be empty.")
        return

    cement = parse_positive_int(cement_text, "Bag/s of Cement", win)
    if cement is None:
        return

    blocks = parse_positive_int(blocks_text, "Blocks", win)
    if blocks is None:
        return

    pay_rate = parse_positive_number(pay_rate_text, "Salary / 75 Blocks", win)
    if pay_rate is None:
        return

    sand = cement * 15
    pay = cement * pay_rate

    # Load old inventory values so stock changes can be adjusted by the difference.
    old_blocks, old_cement_value, old_sand_value, old_applied = get_production_inventory_values(cursor, selected_id.get())
    old_cement = old_cement_value if old_applied else 0
    old_sand = old_sand_value if old_applied else 0

    # Confirm enough material exists for any extra material required by the edit.
    ok, error = validate_material_stock(cursor, cement, sand, selected_id.get())
    if not ok:
        show_chb_error(win, "Insufficient Inventory", error)
        return

    # Ask the user to confirm the production record update.
    if not ask_chb_confirmation(win, "Confirm Update", f"Update record for {worker}?", confirm_text="Update", cancel_text="Cancel", accent_color="#1e40af"):
        return

    # Update the saved production record with the edited values.
    cursor.execute("""
        UPDATE chb_production
        SET production_date=?, worker_name=?, cement_bags=?, fine_sand=?, total_blocks=?, pay=?, pay_rate=?, material_inventory_applied=?, responsible_user=?
        WHERE id=?
    """, (
        date,
        worker,
        cement, sand, blocks, pay, pay_rate, 1, get_responsible_user(),
        selected_id.get()
    ))

    # Adjust material and CHB stock by the difference between old and new values.
    adjust_material_inventory(cursor, CEMENT_ITEM_NAME, old_cement - cement)
    adjust_material_inventory(cursor, FINE_SAND_ITEM_NAME, fine_sand_bags_to_cubic_meters(old_sand - sand))
    conn.commit()
    adjust_chb_inventory(conn, cursor, produced_delta=(blocks - old_blocks))
    notify_inventory_views()
    load_data()
    update_total_blocks()
    if callable(refresh_materials):
        refresh_materials()
    clear_form()
    show_chb_success(win, "Success", "Record updated successfully!")


def delete(conn, cursor, win, selected_id, worker_entry, load_data, update_total_blocks, clear_form, refresh_materials=None):
    # Require an existing selected production row before deleting.
    if not selected_id.get():
        show_chb_error(win, "Error", "Select a record to delete.")
        return

    # Ask the user to confirm the irreversible delete action.
    if not ask_chb_confirmation(
        win,
        "Confirm Delete",
        f"Delete record for {worker_entry.get()}?\n\nThis action cannot be undone.",
        confirm_text="Delete",
        cancel_text="Cancel",
        accent_color=ERROR_RED
    ):
        return

    # Load old production values and optionally return consumed materials to inventory.
    old_blocks, old_cement_value, old_sand_value, old_applied = get_production_inventory_values(cursor, selected_id.get())
    old_cement = old_cement_value if old_applied else 0
    old_sand = old_sand_value if old_applied else 0
    return_materials = ask_return_materials(win, "deleting", old_cement, old_sand) if old_applied else False

    # Delete the production record and reverse its CHB stock contribution.
    cursor.execute("DELETE FROM chb_production WHERE id=?", (selected_id.get(),))
    if return_materials:
        adjust_material_inventory(cursor, CEMENT_ITEM_NAME, old_cement)
        adjust_material_inventory(cursor, FINE_SAND_ITEM_NAME, fine_sand_bags_to_cubic_meters(old_sand))
    conn.commit()
    adjust_chb_inventory(conn, cursor, produced_delta=-old_blocks)
    notify_inventory_views()
    load_data()
    update_total_blocks()
    if callable(refresh_materials):
        refresh_materials()
    clear_form()
    show_chb_success(win, "Success", "Record deleted successfully!")


def update_total_blocks(conn, cursor, total_blocks_var):
    # Read CHB state and update the total available blocks label.
    ensure_chb_inventory(conn, cursor)
    cursor.execute("""
        SELECT total_produced, total_sold, available
        FROM chb_inventory_state
        WHERE id=?
    """, (CHB_STATE_ID,))
    state = cursor.fetchone()
    if state:
        produced, sold, stock = state
    else:
        produced = sold = stock = 0
    total_blocks_var.set(f"Total Hollow Blocks Available: {stock:,}")


def on_tree_configure(event, tree):
    # Allow the production table to finish layout updates after resizing.
    tree.update_idletasks()


def on_select(event, tree, selected_id, date_var, worker_entry, cement_entry, sand_entry, blocks_entry, cursor, pay_rate_var, update_pay):
    # Load the selected production table row back into the edit form.
    selected = tree.focus()
    values = tree.item(selected, "values")

    if values and values[0]:
        selected_id.set(values[0])
        date_var.set(values[1])

        worker_entry.delete(0, tk.END)
        worker_entry.insert(0, values[2])

        cement_entry.delete(0, tk.END)
        cement_entry.insert(0, values[3])

        sand_entry.delete(0, tk.END)
        sand_entry.insert(0, values[4])

        blocks_entry.delete(0, tk.END)
        blocks_entry.insert(0, values[5])

        cursor.execute("SELECT pay_rate FROM chb_production WHERE id=?", (values[0],))
        pr = cursor.fetchone()
        pay_rate_var.set(pr[0] if pr and pr[0] is not None else 200)
        # Recalculate pay display after loading the selected record.
        update_pay()


def load_data(event, tree, search_var, sort_var, cursor):
    # Clear the production table before loading the current day's rows.
    for row in tree.get_children():
        tree.delete(row)

    keyword = search_var.get().lower()
    sort_option = sort_var.get()
    today = datetime.now().strftime("%Y-%m-%d")

    query = """
        SELECT id,
               production_date,
               worker_name,
               cement_bags,
               fine_sand,
               total_blocks,
               pay,
               COALESCE(NULLIF(responsible_user, ''), 'Admin')
        FROM chb_production
        WHERE DATE(COALESCE(NULLIF(production_date, ''), ts)) = ?
    """

    # Apply search and sort options to the current-day production query.
    params = [today]

    if keyword:
        query += " AND (LOWER(worker_name) LIKE ? OR production_date LIKE ?)"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if sort_option == "Worker Name":
        query += " ORDER BY worker_name ASC"
    else:
        query += " ORDER BY ts DESC"

    cursor.execute(query, params)

    # Insert matching rows or a friendly empty row when there is no production today.
    row_index = 0
    rows = cursor.fetchall()
    if not rows:
        if keyword:
            return 0
        tree.insert("", "end", values=("", today, "No production today", "", "", "", "", ""), tags=('oddrow',))
        return 0
    for row in rows:
        tag = 'evenrow' if row_index % 2 == 0 else 'oddrow'
        tree.insert("", "end", values=row, tags=(tag,))
        row_index += 1
    return row_index
