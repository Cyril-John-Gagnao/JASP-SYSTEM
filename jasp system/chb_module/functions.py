import sys
import tkinter as tk
from tkinter import messagebox
from datetime import datetime

from .chb_database import (
    CHB_STATE_ID,
    CEMENT_ITEM_NAME,
    FINE_SAND_ITEM_NAME,
    ensure_chb_inventory,
    adjust_chb_inventory,
    adjust_material_inventory,
    fetch_material_stock,
)
from .summary import open_date_calendar, open_period_summary


def notify_inventory_views():
    """Refresh open inventory/POS windows if they registered callbacks."""
    for module_name, callback_name in (("inventory_module", "inventory_refresh_callback"), ("inventory", "inventory_refresh_callback"), ("pos", "pos_refresh_callback")):
        module = sys.modules.get(module_name)
        callback = getattr(module, callback_name, None) if module else None
        if callable(callback):
            try:
                callback()
            except Exception:
                pass


def go_back(win):
    win.destroy()
    import main_dashboard
    main_dashboard.open_main()


def refresh_data(load_data, update_total_blocks):
    load_data()
    update_total_blocks()


def update_pay(event, cement_entry, pay_rate_var, result_label):
    try:
        cement = int(cement_entry.get() or 0)
        pay = cement * float(pay_rate_var.get() or 0)
        result_label.config(text=f"| Pay: ₱{pay:,.2f}")
    except:
        result_label.config(text="| Pay: ₱0")


def format_material_stock(cursor, item_name):
    return f"Available: {fetch_material_stock(cursor, item_name):,}"


def refresh_material_dropdowns(cursor, cement_stock_var=None, sand_stock_var=None, cement_stock_combo=None, sand_stock_combo=None):
    cement_text = format_material_stock(cursor, CEMENT_ITEM_NAME)
    sand_text = format_material_stock(cursor, FINE_SAND_ITEM_NAME)

    if cement_stock_var is not None:
        cement_stock_var.set(cement_text)
    if sand_stock_var is not None:
        sand_stock_var.set(sand_text)

    if cement_stock_combo is not None:
        cement_stock_combo.config(values=[cement_text])
    if sand_stock_combo is not None:
        sand_stock_combo.config(values=[sand_text])


def validate_material_stock(cursor, cement_needed, sand_needed, selected_id=None, return_existing_materials=True):
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
            old_sand = int(old_row[1] or 0)

    cement_delta = int(cement_needed) - old_cement
    sand_delta = int(sand_needed) - old_sand
    cement_available = fetch_material_stock(cursor, CEMENT_ITEM_NAME)
    sand_available = fetch_material_stock(cursor, FINE_SAND_ITEM_NAME)

    if cement_delta > cement_available:
        return False, f"Not enough cement. Available: {cement_available:,}, needed: {cement_delta:,}."
    if sand_delta > sand_available:
        return False, f"Not enough fine sand. Available: {sand_available:,}, needed: {sand_delta:,}."
    return True, ""


def get_production_inventory_values(cursor, production_id):
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
    return int(row[0] or 0), int(row[1] or 0), int(row[2] or 0), int(row[3] or 0)


def ask_return_materials(win, action, cement, sand):
    if cement <= 0 and sand <= 0:
        return False

    return messagebox.askyesno(
        "Return Materials",
        (
            f"Do you want to return the materials from this production record to inventory before {action}?\n\n"
            f"Cement: {cement:,} bag/s\n"
            f"Fine Sand: {sand:,} bag/s"
        ),
        parent=win
    )


def auto_sand(event, cement_entry, sand_entry, pay_rate_var, blocks_entry, result_label):
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
    worker_entry.delete(0, tk.END)
    cement_entry.delete(0, tk.END)
    sand_entry.delete(0, tk.END)
    blocks_entry.delete(0, tk.END)
    blocks_entry.insert(0, "0")
    result_label.config(text="| Pay: ₱0")
    selected_id.set("")


def save(conn, cursor, win, worker_entry, date_var, cement_entry, blocks_entry, pay_rate_var, load_data, update_total_blocks, clear_form, refresh_materials=None):
    try:
        cement = int(cement_entry.get())
        sand = cement * 15
        blocks = int(blocks_entry.get())
        pay_rate = float(pay_rate_var.get())
        pay = cement * pay_rate
    except:
        messagebox.showerror("Error", "Invalid input", parent=win)
        return

    worker = worker_entry.get()
    date = date_var.get()

    if not worker:
        messagebox.showerror("Error", "Fill all fields", parent=win)
        return

    ok, error = validate_material_stock(cursor, cement, sand)
    if not ok:
        messagebox.showerror("Insufficient Inventory", error, parent=win)
        return

    # Confirmation dialog
    if not messagebox.askyesno("Confirm Save", f"Save production record for {worker}?", parent=win):
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO chb_production
        (production_date, worker_name, cement_bags, fine_sand, total_blocks, pay, pay_rate, material_inventory_applied, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (date, worker, cement, sand, blocks, pay, pay_rate, 1, ts))

    adjust_material_inventory(cursor, CEMENT_ITEM_NAME, -cement)
    adjust_material_inventory(cursor, FINE_SAND_ITEM_NAME, -sand)
    conn.commit()
    adjust_chb_inventory(conn, cursor, produced_delta=blocks)
    notify_inventory_views()
    load_data()
    update_total_blocks()
    if callable(refresh_materials):
        refresh_materials()
    clear_form()
    messagebox.showinfo("Success", "Record saved successfully!", parent=win)


def update(conn, cursor, win, selected_id, worker_entry, date_var, cement_entry, blocks_entry, pay_rate_var, load_data, update_total_blocks, clear_form, refresh_materials=None):
    if not selected_id.get():
        messagebox.showerror("Error", "Select a record", parent=win)
        return

    try:
        cement = int(cement_entry.get())
        sand = cement * 15
        blocks = int(blocks_entry.get())
        pay_rate = float(pay_rate_var.get())
        pay = cement * pay_rate
    except:
        messagebox.showerror("Error", "Invalid input", parent=win)
        return

    old_blocks, old_cement_value, old_sand_value, old_applied = get_production_inventory_values(cursor, selected_id.get())
    old_cement = old_cement_value if old_applied else 0
    old_sand = old_sand_value if old_applied else 0

    ok, error = validate_material_stock(cursor, cement, sand, selected_id.get())
    if not ok:
        messagebox.showerror("Insufficient Inventory", error, parent=win)
        return

    # Confirmation dialog
    if not messagebox.askyesno("Confirm Update", f"Update record for {worker_entry.get()}?", parent=win):
        return

    cursor.execute("""
        UPDATE chb_production
        SET production_date=?, worker_name=?, cement_bags=?, fine_sand=?, total_blocks=?, pay=?, pay_rate=?, material_inventory_applied=?
        WHERE id=?
    """, (
        date_var.get(),
        worker_entry.get(),
        cement, sand, blocks, pay, pay_rate, 1,
        selected_id.get()
    ))

    adjust_material_inventory(cursor, CEMENT_ITEM_NAME, old_cement - cement)
    adjust_material_inventory(cursor, FINE_SAND_ITEM_NAME, old_sand - sand)
    conn.commit()
    adjust_chb_inventory(conn, cursor, produced_delta=(blocks - old_blocks))
    notify_inventory_views()
    load_data()
    update_total_blocks()
    if callable(refresh_materials):
        refresh_materials()
    clear_form()
    messagebox.showinfo("Success", "Record updated successfully!", parent=win)


def delete(conn, cursor, win, selected_id, worker_entry, load_data, update_total_blocks, clear_form, refresh_materials=None):
    if not selected_id.get():
        return

    # Confirmation dialog
    if not messagebox.askyesno("Confirm Delete", f"Delete record for {worker_entry.get()}?\n\nThis action cannot be undone.", parent=win):
        return

    old_blocks, old_cement_value, old_sand_value, old_applied = get_production_inventory_values(cursor, selected_id.get())
    old_cement = old_cement_value if old_applied else 0
    old_sand = old_sand_value if old_applied else 0
    return_materials = ask_return_materials(win, "deleting", old_cement, old_sand) if old_applied else False

    cursor.execute("DELETE FROM chb_production WHERE id=?", (selected_id.get(),))
    if return_materials:
        adjust_material_inventory(cursor, CEMENT_ITEM_NAME, old_cement)
        adjust_material_inventory(cursor, FINE_SAND_ITEM_NAME, old_sand)
    conn.commit()
    adjust_chb_inventory(conn, cursor, produced_delta=-old_blocks)
    notify_inventory_views()
    load_data()
    update_total_blocks()
    if callable(refresh_materials):
        refresh_materials()
    clear_form()
    messagebox.showinfo("Success", "Record deleted successfully!", parent=win)


def update_total_blocks(conn, cursor, total_blocks_var):
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
    tree.update_idletasks()


def on_select(event, tree, selected_id, date_var, worker_entry, cement_entry, sand_entry, blocks_entry, cursor, pay_rate_var, update_pay):
    selected = tree.focus()
    values = tree.item(selected, "values")

    if values:
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
        update_pay()


def load_data(event, tree, search_var, sort_var, cursor):
    for row in tree.get_children():
        tree.delete(row)

    keyword = search_var.get().lower()
    sort_option = sort_var.get()

    query = """
        SELECT id, production_date, worker_name, cement_bags, fine_sand, total_blocks, pay
        FROM chb_production
    """

    params = []

    if keyword:
        query += " WHERE LOWER(worker_name) LIKE ? OR production_date LIKE ?"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if sort_option == "Worker Name":
        query += " ORDER BY worker_name ASC"
    else:
        query += " ORDER BY ts DESC"

    cursor.execute(query, params)

    row_index = 0
    for row in cursor.fetchall():
        tag = 'evenrow' if row_index % 2 == 0 else 'oddrow'
        tree.insert("", "end", values=row, tags=(tag,))
        row_index += 1
