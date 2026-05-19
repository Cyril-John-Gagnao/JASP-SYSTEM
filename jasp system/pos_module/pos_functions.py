import os
import sys
import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont
from tkinter import ttk

from jasp_theme import (
    DASHBOARD_CONTENT_BG,
    DASHBOARD_HEADER_BG,
    DASHBOARD_HEADER_BORDER,
    DASHBOARD_HEADER_FG,
    DASHBOARD_HEADER_SUBTLE_FG,
    add_header_logo,
)
from main_dashboard import session
from pos_module.pos_database import CHB_ITEM_NAME, CHB_STATE_ID

SUCCESS_GREEN = "#00c853"
CANCEL_RED = "#dc2626"
PRIMARY_BLUE = "#2563eb"
WARNING_ORANGE = "#f59e0b"
PANEL_BG = "#ffffff"
CHB_SECTION_ITEMS = ("Cement", "Fine Sand", CHB_ITEM_NAME)
CHB_SECTION_ORDER = {name.lower(): index for index, name in enumerate(CHB_SECTION_ITEMS)}
FINE_SAND_ITEM_NAME = "Fine Sand"
FINE_SAND_BAGS_PER_CUBIC_METER = 40
FINE_SAND_BASE_UNIT = "cubic meters"
FINE_SAND_TRANSACTION_UNITS = (FINE_SAND_BASE_UNIT, "bag")


def is_fine_sand(item_name):
    return str(item_name or "").strip().lower() == FINE_SAND_ITEM_NAME.lower()


def is_bag_unit(unit):
    unit_text = str(unit or "").strip().lower()
    return unit_text in {"bag", "bags", "bag/sack", "sack", "sacks"}


def fine_sand_cubic_deduction(qty, unit):
    qty = float(qty or 0)
    return qty / FINE_SAND_BAGS_PER_CUBIC_METER if is_bag_unit(unit) else qty


def parse_sale_quantity(qty_text, item_name, unit):
    qty_text = str(qty_text or "").strip()
    if is_fine_sand(item_name) and not is_bag_unit(unit):
        return float(qty_text)
    return int(qty_text)


def format_pos_quantity(quantity):
    try:
        value = float(quantity or 0)
    except (TypeError, ValueError):
        return str(quantity)
    return f"{value:,.3f}".rstrip("0").rstrip(".")


def format_fine_sand_stock(quantity):
    cubic_stock = float(quantity or 0)
    equivalent_bags = cubic_stock * FINE_SAND_BAGS_PER_CUBIC_METER
    return f"{format_pos_quantity(cubic_stock)} cubic meters ({format_pos_quantity(equivalent_bags)} bags)"


def format_money_value(value):
    return f"{float(value or 0):.2f}"


def format_fine_sand_prices(cubic_price, bag_price):
    return f"Cubic: {format_money_value(cubic_price)} | Bag: {format_money_value(bag_price)}"


def fetch_fine_sand_prices(cursor, item_id):
    cursor.execute("SELECT COALESCE(price, 0), COALESCE(fine_sand_bag_price, 0) FROM items WHERE id=?", (item_id,))
    row = cursor.fetchone() or (0, 0)
    return float(row[0] or 0), float(row[1] or 0)


def fine_sand_price_for_unit(cursor, item_id, unit):
    cubic_price, bag_price = fetch_fine_sand_prices(cursor, item_id)
    return bag_price if is_bag_unit(unit) else cubic_price


def parse_stock_quantity(quantity):
    return float(str(quantity).split(" ", 1)[0].replace(",", ""))


def display_inventory_row(row):
    values = list(row)
    if len(values) > 3 and is_fine_sand(values[1]):
        values[2] = FINE_SAND_BASE_UNIT
        values[3] = format_fine_sand_stock(values[3])
        bag_price = values[5] if len(values) > 5 else 0
        values[4] = format_fine_sand_prices(values[4], bag_price)
        values = values[:5]
    return tuple(values)


def center_window(window, width=None, height=None, parent=None):
    """Center a window on the screen."""
    window.update_idletasks()
    width = width or window.winfo_width()
    height = height or window.winfo_height()
    if parent and parent.winfo_exists():
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    else:
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def show_pos_popup(parent, title, message, accent_color):
    popup = tk.Toplevel(parent)
    popup.title(title)
    if parent is not None:
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

    tk.Button(content, text="OK", command=close_popup, bg=accent_color, fg="white", activebackground=accent_color, font=("Arial", 15, "bold"), relief="solid", bd=2, highlightthickness=1, highlightbackground="black", highlightcolor="black", width=14, pady=9).pack()
    popup.bind("<Return>", lambda _event: close_popup())
    popup.bind("<Escape>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    center_window(popup, 540, 290, parent)
    popup.wait_window(popup)


def show_pos_error(parent, title, message):
    show_pos_popup(parent, title, message, CANCEL_RED)


def show_pos_success(parent, title, message):
    show_pos_popup(parent, title, message, SUCCESS_GREEN)


def show_pos_warning(parent, title, message):
    show_pos_popup(parent, title, message, WARNING_ORANGE)


def ask_pos_confirmation(parent, title, message, confirm_text="Yes", accent_color=PRIMARY_BLUE):
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

    tk.Label(content, text=title, bg="#ffffff", fg=accent_color, font=("Arial", 26, "bold")).pack(pady=(0, 14))
    tk.Label(content, text=message, bg="#ffffff", fg="#111827", font=("Arial", 16), wraplength=470, justify="center").pack(pady=(0, 28))

    button_row = tk.Frame(content, bg="#ffffff")
    button_row.pack()

    def confirm():
        result["confirmed"] = True
        popup.destroy()

    def cancel():
        popup.destroy()

    border = {"relief": "solid", "bd": 2, "highlightthickness": 1, "highlightbackground": "black", "highlightcolor": "black"}
    tk.Button(button_row, text="Cancel", command=cancel, bg="#64748b", fg="white", activebackground="#475569", font=("Arial", 14, "bold"), width=13, pady=9, **border).pack(side="left", padx=8)
    tk.Button(button_row, text=confirm_text, command=confirm, bg=accent_color, fg="white", activebackground=accent_color, font=("Arial", 14, "bold"), width=13, pady=9, **border).pack(side="left", padx=8)
    popup.bind("<Return>", lambda _event: confirm())
    popup.bind("<Escape>", lambda _event: cancel())
    popup.protocol("WM_DELETE_WINDOW", cancel)
    center_window(popup, 600, 330, parent)
    parent.wait_window(popup)
    return result["confirmed"]


def notify_inventory_views():
    """Refresh open inventory windows when stock changes."""
    module = sys.modules.get("inventory_module") or sys.modules.get("inventory")
    callback = getattr(module, "inventory_refresh_callback", None) if module else None
    if callable(callback):
        try:
            callback()
        except Exception:
            pass


def notify_dashboard_views():
    """Refresh the main dashboard after a completed POS sale."""
    for module_name in ("main_dashboard.main_gui", "Main_dashboard.main_gui"):
        module = sys.modules.get(module_name)
        callback = getattr(module, "dashboard_refresh_callback", None) if module else None
        if callable(callback):
            try:
                callback()
            except Exception:
                pass


def compact_receipt_txn_id(txn_id):
    digits = "".join(ch for ch in str(txn_id or "") if ch.isdigit())
    return digits[-5:] if digits else str(txn_id or "")[-5:]


def center_receipt_window(window, parent):
    if not window.winfo_exists():
        return
    width = 760
    height = 760
    window.update_idletasks()
    if parent and parent.winfo_exists():
        parent.update_idletasks()
        x_pos = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y_pos = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    else:
        x_pos = (window.winfo_screenwidth() // 2) - (width // 2)
        y_pos = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{max(x_pos, 0)}+{max(y_pos, 0)}")


def fit_tree_columns_to_width(tree, column_weights, padding=26):
    tree.update_idletasks()
    available_width = max(tree.winfo_width() - padding, 1)
    total_weight = sum(weight for _width, _minwidth, weight in column_weights.values()) or 1
    for column, (base_width, min_width, weight) in column_weights.items():
        width = max(min_width, int(available_width * (weight / total_weight)))
        tree.column(column, width=width, minwidth=min_width, stretch=False)


def auto_fit_tree_columns(tree, column_specs, padding=26, sample_limit=80):
    tree.update_idletasks()
    body_font = tkfont.Font(font=("Arial", 15))
    heading_font = tkfont.Font(font=("Arial", 15, "bold"))
    max_widths = {
        "ID": 90,
        "Name": 220,
        "Unit": 150,
        "Quantity": 330,
        "Price": 340,
        "Add": 120,
        "Qty": 120,
        "Selling Price": 190,
        "Total": 170,
        "Edit": 120,
        "Item": 320,
    }

    for column, (base_width, min_width, _weight) in column_specs.items():
        heading_text = tree.heading(column, "text") or column
        measured = max(min_width, heading_font.measure(str(heading_text)) + 30)
        for row_id in tree.get_children()[:sample_limit]:
            values = tree.item(row_id, "values")
            try:
                value = values[list(tree["columns"]).index(column)]
            except (ValueError, IndexError):
                value = ""
            measured = max(measured, body_font.measure(str(value)) + 34)
        width = min(max(measured, base_width, min_width), max_widths.get(column, max(base_width * 3, min_width)))
        tree.column(column, width=width, minwidth=min_width, stretch=False)


def refresh_inventory_names(ctx):
    cursor = ctx["cursor"]
    cursor.execute("SELECT name FROM items WHERE COALESCE(status, 'Active') = 'Active'")
    ctx["inventory_names"][:] = [row[0] for row in cursor.fetchall()]


def update_search_suggestions(ctx):
    search_entry = ctx["search_entry"]
    text = search_entry.get()
    search_entry["values"] = [name for name in ctx["inventory_names"] if text.lower() in name.lower()]


def load_inventory(ctx, search_query=""):
    inv_tree = ctx["inv_tree"]
    chb_inv_tree = ctx.get("chb_inv_tree")
    inventory_trees = [tree for tree in (chb_inv_tree, inv_tree) if tree and tree.winfo_exists()]
    cursor = ctx["cursor"]
    sort_var = ctx["sort_var"]
    clear_inventory_buttons(ctx)
    for tree in inventory_trees:
        for row in tree.get_children():
            tree.delete(row)

    chb_query = """
        SELECT id, name, unit, quantity, price, COALESCE(fine_sand_bag_price, 0)
        FROM items
        WHERE COALESCE(status, 'Active') = 'Active'
          AND LOWER(name) IN ('cement', 'fine sand', 'chb blocks')
        ORDER BY
            CASE LOWER(name)
                WHEN 'cement' THEN 0
                WHEN 'fine sand' THEN 1
                WHEN 'chb blocks' THEN 2
                ELSE 3
            END
    """
    cursor.execute(chb_query)
    chb_rows = cursor.fetchall()

    query = """
        SELECT id, name, unit, quantity, price, COALESCE(fine_sand_bag_price, 0)
        FROM items
        WHERE COALESCE(status, 'Active') = 'Active'
          AND LOWER(name) NOT IN ('cement', 'fine sand', 'chb blocks')
    """
    params = []
    if search_query:
        query += " AND name LIKE ?"
        params.append("%" + search_query + "%")

    if sort_var.get() == "Name":
        query += """
            ORDER BY
                CASE WHEN LOWER(name) IN ('cement', 'fine sand', 'chb blocks') THEN 0 ELSE 1 END,
                CASE LOWER(name)
                    WHEN 'cement' THEN 0
                    WHEN 'fine sand' THEN 1
                    WHEN 'chb blocks' THEN 2
                    ELSE 3
                END,
                LOWER(name) ASC
        """
    else:
        query += """
            ORDER BY
                id DESC
        """

    cursor.execute(query, params)
    other_rows = cursor.fetchall()
    if not chb_rows and not other_rows:
        empty_message = "No items found"
        if search_query:
            cursor.execute(
                """
                SELECT COUNT(*)
                FROM items
                WHERE COALESCE(status, 'Active') <> 'Active'
                  AND name LIKE ?
                """,
                ("%" + search_query + "%",)
            )
            inactive_count = int(cursor.fetchone()[0] or 0)
            if inactive_count == 1:
                empty_message = "Matching item is currently unavailable"
            elif inactive_count > 1:
                empty_message = "Matching items are currently unavailable"
        if chb_inv_tree and chb_inv_tree.winfo_exists():
            chb_inv_tree.insert("", tk.END, values=("", "No CHB items found", "", "", "", ""), tags=("emptyrow",))
        inv_tree.insert("", tk.END, values=("", empty_message, "", "", "", ""), tags=("emptyrow",))
        refresh_inventory_names(ctx)
        if ctx.get("inventory_column_specs"):
            for tree in inventory_trees:
                auto_fit_tree_columns(tree, ctx["inventory_column_specs"])
        schedule_inventory_buttons(ctx)
        return

    if chb_inv_tree and chb_inv_tree.winfo_exists():
        if chb_rows:
            for index, row in enumerate(chb_rows):
                tag = "evenrow" if index % 2 else "oddrow"
                display_row = display_inventory_row(row)
                chb_inv_tree.insert("", tk.END, values=display_row + ("",), tags=(tag,))
        else:
            chb_inv_tree.insert("", tk.END, values=("", "No CHB items found", "", "", "", ""), tags=("emptyrow",))

    if other_rows:
        for index, row in enumerate(other_rows):
            tag = "evenrow" if index % 2 else "oddrow"
            display_row = display_inventory_row(row)
            inv_tree.insert("", tk.END, values=display_row + ("",), tags=(tag,))
    else:
        inv_tree.insert("", tk.END, values=("", "No other items found", "", "", "", ""), tags=("emptyrow",))

    refresh_inventory_names(ctx)
    if ctx.get("inventory_column_specs"):
        for tree in inventory_trees:
            auto_fit_tree_columns(tree, ctx["inventory_column_specs"])
    schedule_inventory_buttons(ctx)


def clear_inventory_buttons(ctx):
    buttons = ctx.get("inventory_buttons", {})
    if isinstance(buttons, list):
        iterable = buttons
    else:
        iterable = buttons.values()
    for button in iterable:
        if button.winfo_exists():
            button.destroy()
    ctx["inventory_buttons"] = {}


def schedule_inventory_buttons(ctx):
    root = ctx.get("root")
    if not root or not root.winfo_exists():
        return
    if ctx.get("inventory_button_job") is not None:
        return
    ctx["inventory_button_job"] = root.after_idle(lambda: render_inventory_buttons(ctx))


def render_inventory_buttons(ctx):
    ctx["inventory_button_job"] = None
    buttons = ctx.setdefault("inventory_buttons", {})
    if isinstance(buttons, list):
        clear_inventory_buttons(ctx)
        buttons = ctx["inventory_buttons"]
    visible_items = set()

    for inv_tree in [tree for tree in (ctx.get("chb_inv_tree"), ctx.get("inv_tree")) if tree and tree.winfo_exists()]:
        inv_tree.update_idletasks()
        for item_id in inv_tree.get_children():
            button_key = (str(inv_tree), item_id)
            bbox = inv_tree.bbox(item_id, "Add")
            values = inv_tree.item(item_id, "values")
            if not values or values[0] == "":
                continue
            if not bbox:
                button = buttons.get(button_key)
                if button and button.winfo_exists():
                    button.place_forget()
                continue
            visible_items.add(button_key)
            button = buttons.get(button_key)
            if button is None or not button.winfo_exists():
                button = tk.Button(
                    inv_tree,
                    text="Add",
                    bg="#16a34a",
                    fg="white",
                    activebackground="#15803d",
                    activeforeground="white",
                    font=("Arial", 10, "bold"),
                    cursor="hand2",
                    command=lambda row_id=item_id, tree_widget=inv_tree: (
                        tree_widget.selection_set(row_id),
                        tree_widget.focus(row_id),
                        open_add_to_cart_modal(ctx, tree_widget=tree_widget),
                    ),
                    **ctx["button_border"],
                )
                buttons[button_key] = button
            x, y, width, height = bbox
            button.place(x=x + 4, y=y + 4, width=max(width - 8, 64), height=max(height - 8, 24))

    for item_id, button in list(buttons.items()):
        if item_id not in visible_items:
            if button.winfo_exists():
                button.place_forget()


def add_item_to_cart(ctx, product_id, name, unit, quantity, price, qty):
    cursor = ctx["cursor"]
    cart = ctx["cart"]
    root = ctx["root"]
    cursor.execute("SELECT raw_price, COALESCE(status, 'Active') FROM items WHERE id=?", (product_id,))
    rp = cursor.fetchone()
    if not rp or rp[1] != "Active":
        show_pos_error(root, "Error", "This item is inactive and cannot be sold.")
        load_inventory(ctx, ctx["search_entry"].get())
        return False

    raw_price = float(rp[0]) if rp[0] is not None else price
    existing_item = next((item for item in cart if item["id"] == product_id), None)
    if existing_item and is_fine_sand(name) and existing_item.get("unit") != unit:
        show_pos_error(root, "Error", "Fine sand is already in the cart with a different unit.")
        return False
    existing_qty = existing_item["qty"] if existing_item else 0

    if qty <= 0:
        show_pos_error(root, "Error", "Enter a valid quantity.")
        return False
    requested_stock = fine_sand_cubic_deduction(existing_qty + qty, unit) if is_fine_sand(name) else existing_qty + qty
    if requested_stock > quantity:
        show_pos_error(root, "Error", "Not enough fine sand stock available." if is_fine_sand(name) else "Stocks aren't enough.")
        return False

    if existing_item:
        existing_item["qty"] += qty
        existing_item["total"] = existing_item["qty"] * existing_item["price"]
    else:
        cart.append({
            "id": product_id,
            "name": name,
            "unit": unit,
            "qty": qty,
            "price": price,
            "raw_price": raw_price,
            "total": qty * price,
        })

    update_cart(ctx)
    return True


def update_cart(ctx):
    cart_tree = ctx["cart_tree"]
    total_label = ctx["total_label"]
    clear_cart_buttons(ctx)
    cart_tree.delete(*cart_tree.get_children())
    total = 0
    for index, item in enumerate(ctx["cart"]):
        tag = "evenrow" if index % 2 else "oddrow"
        cart_tree.insert(
            "",
            tk.END,
            values=(
                item["id"],
                item["name"],
                item.get("unit", "pcs"),
                item["qty"],
                f"{item['price']:.2f}",
                f"{item['total']:.2f}",
                "",
            ),
            tags=(tag,),
        )
        total += item["total"]
    total_label.config(text=f"Amount Due: P{total:.2f}")
    if ctx.get("cart_column_specs"):
        auto_fit_tree_columns(cart_tree, ctx["cart_column_specs"])
    schedule_cart_buttons(ctx)


def clear_cart_buttons(ctx):
    for button in ctx.get("cart_buttons", {}).values():
        if button.winfo_exists():
            button.destroy()
    ctx["cart_buttons"] = {}


def schedule_cart_buttons(ctx):
    cart_tree = ctx.get("cart_tree")
    if not cart_tree or not cart_tree.winfo_exists():
        return
    if ctx.get("cart_button_job") is not None:
        return
    ctx["cart_button_job"] = cart_tree.after_idle(lambda: render_cart_buttons(ctx))


def render_cart_buttons(ctx):
    ctx["cart_button_job"] = None
    cart_tree = ctx["cart_tree"]
    cart_tree.update_idletasks()
    buttons = ctx.setdefault("cart_buttons", {})
    visible_items = set()

    for row_id in cart_tree.get_children():
        bbox = cart_tree.bbox(row_id, "Edit")
        values = cart_tree.item(row_id, "values")
        if not values:
            continue
        if not bbox:
            button = buttons.get(row_id)
            if button and button.winfo_exists():
                button.place_forget()
            continue
        visible_items.add(row_id)
        button = buttons.get(row_id)
        if button is None or not button.winfo_exists():
            button = tk.Button(
                cart_tree,
                text="Edit",
                bg="#2563eb",
                fg="white",
                activebackground="#1d4ed8",
                activeforeground="white",
                font=("Arial", 10, "bold"),
                cursor="hand2",
                command=lambda selected=row_id: (
                    cart_tree.selection_set(selected),
                    cart_tree.focus(selected),
                    open_cart_item_modal(ctx),
                ),
                **ctx["button_border"],
            )
            buttons[row_id] = button
        x, y, width, height = bbox
        button.place(x=x + 4, y=y + 4, width=max(width - 8, 64), height=max(height - 8, 24))

    for row_id, button in list(buttons.items()):
        if row_id not in visible_items and button.winfo_exists():
            button.place_forget()


def clear_cart(ctx):
    cart = ctx["cart"]
    root = ctx["root"]
    if not cart:
        show_pos_success(root, "Cart", "Cart is already empty.")
        return
    if not ask_pos_confirmation(root, "Clear Cart", "Clear all items from the cart?", confirm_text="Clear", accent_color=WARNING_ORANGE):
        return
    cart.clear()
    update_cart(ctx)


def nudge_quantity(qty_entry, delta, default_value=1, minimum=1):
    current_text = qty_entry.get().strip()
    try:
        current_value = int(current_text) if current_text else default_value
    except ValueError:
        current_value = default_value
    new_value = max(minimum, current_value + delta)
    qty_entry.delete(0, tk.END)
    qty_entry.insert(0, str(new_value))
    qty_entry.icursor(tk.END)
    qty_entry.focus_set()


def nudge_add_quantity(parent, qty_entry, delta):
    current_text = qty_entry.get().strip()
    if not current_text and delta < 0:
        show_pos_error(parent, "Invalid Quantity", "Enter a quantity before subtracting.")
        qty_entry.focus_set()
        return
    nudge_quantity(qty_entry, delta, 0, minimum=0)


def open_add_to_cart_modal(ctx, _event=None, tree_widget=None):
    inv_tree = tree_widget or (getattr(_event, "widget", None) if _event is not None else None) or ctx["inv_tree"]
    selected = inv_tree.focus()
    if not selected:
        return

    values = inv_tree.item(selected, "values")
    if not values or not values[0]:
        return
    product_id = int(values[0])
    name = values[1]
    unit = values[2] or "pcs"
    quantity = parse_stock_quantity(values[3])
    price = fine_sand_price_for_unit(ctx["cursor"], product_id, FINE_SAND_BASE_UNIT) if is_fine_sand(name) else float(values[4])
    button_border = ctx["button_border"]
    root = ctx["root"]

    modal = tk.Toplevel(root)
    modal.title("Add to Cart")
    modal.configure(bg=DASHBOARD_CONTENT_BG)
    modal.resizable(False, False)
    modal.transient(root)
    modal.grab_set()

    header = tk.Frame(modal, bg=DASHBOARD_HEADER_BG, highlightthickness=1, highlightbackground=DASHBOARD_HEADER_BORDER)
    header.pack(fill="x")
    title_frame = tk.Frame(header, bg=DASHBOARD_HEADER_BG)
    title_frame.pack(padx=24, pady=14)
    add_header_logo(title_frame, DASHBOARD_HEADER_BG, size=44)
    tk.Label(title_frame, text="Add to Cart", font=("Arial", 24, "bold"), bg=DASHBOARD_HEADER_BG, fg=DASHBOARD_HEADER_FG).pack(side="left")

    body = tk.Frame(modal, bg=PANEL_BG, padx=28, pady=22, highlightthickness=1, highlightbackground="black")
    body.pack(fill="both", expand=True, padx=26, pady=22)
    tk.Label(body, text=name, font=("Arial", 20, "bold"), bg=PANEL_BG, wraplength=520, justify="center").pack(pady=(0, 8))
    available_text = format_fine_sand_stock(quantity) if is_fine_sand(name) else f"{format_pos_quantity(quantity)} {unit}"
    tk.Label(body, text=f"Available stock: {available_text}", font=("Arial", 16, "bold"), bg=PANEL_BG, fg="#1e40af").pack(pady=(0, 18))

    form = tk.Frame(body, bg=PANEL_BG)
    form.pack(pady=8, fill="x")
    tk.Label(form, text="Quantity", bg=PANEL_BG, font=("Arial", 17, "bold")).grid(row=0, column=0, padx=(0, 12), pady=8)
    qty_entry = tk.Entry(form, width=14, font=("Arial", 18), justify="center", bd=2, relief="solid")
    qty_entry.grid(row=0, column=1, pady=8, ipady=4)
    tk.Button(
        form,
        text="-",
        command=lambda: nudge_add_quantity(modal, qty_entry, -1),
        bg="#dc2626",
        fg="white",
        activebackground="#b91c1c",
        activeforeground="white",
        font=("Arial", 18, "bold"),
        width=4,
        padx=4,
        pady=3,
        **button_border,
    ).grid(row=0, column=2, padx=(8, 0), pady=8)
    tk.Button(
        form,
        text="+",
        command=lambda: nudge_add_quantity(modal, qty_entry, 1),
        bg="#16a34a",
        fg="white",
        activebackground="#15803d",
        activeforeground="white",
        font=("Arial", 18, "bold"),
        width=4,
        padx=4,
        pady=3,
        **button_border,
    ).grid(row=0, column=3, padx=(8, 0), pady=8)
    qty_entry.focus_set()

    sale_unit_var = tk.StringVar(value=FINE_SAND_BASE_UNIT if is_fine_sand(name) else unit)
    price_var = tk.StringVar(value=f"Price: {format_money_value(price)}")
    if is_fine_sand(name):
        price_label = tk.Label(form, textvariable=price_var, bg=PANEL_BG, font=("Arial", 14, "bold"), fg="#991b1b")
        price_label.grid(row=2, column=1, columnspan=3, sticky="w", pady=(2, 0))

        def update_price_for_unit(*_args):
            current_price = fine_sand_price_for_unit(ctx["cursor"], product_id, sale_unit_var.get())
            price_var.set(f"Price: {format_money_value(current_price)}")

        sale_unit_var.trace_add("write", update_price_for_unit)
        tk.Label(form, text="Unit", bg=PANEL_BG, font=("Arial", 17, "bold")).grid(row=1, column=0, padx=(0, 12), pady=8)
        ttk.Combobox(
            form,
            textvariable=sale_unit_var,
            values=FINE_SAND_TRANSACTION_UNITS,
            state="readonly",
            width=13,
            font=("Arial", 16),
        ).grid(row=1, column=1, columnspan=3, sticky="ew", pady=8)

    quick_row = tk.Frame(body, bg=PANEL_BG)
    quick_row.pack(pady=(8, 10), fill="x")
    for idx, step in enumerate((-20, -10, -5, 5, 10, 20)):
        tk.Button(
            quick_row,
            text=f"{step:+}",
            command=lambda delta=step: nudge_add_quantity(modal, qty_entry, delta),
            bg="#e5e7eb",
            fg="#111827",
            activebackground="#d1d5db",
            activeforeground="#111827",
            font=("Arial", 14, "bold"),
            padx=8,
            pady=6,
            width=6,
            **button_border,
        ).grid(row=0, column=idx, padx=2, sticky="ew")
        quick_row.grid_columnconfigure(idx, weight=1)

    def submit():
        qty_text = qty_entry.get().strip()
        try:
            sale_unit = sale_unit_var.get()
            qty = parse_sale_quantity(qty_text, name, sale_unit)
            sale_price = fine_sand_price_for_unit(ctx["cursor"], product_id, sale_unit) if is_fine_sand(name) else price
        except ValueError:
            show_pos_error(modal, "Error", "Enter a valid quantity.")
            return
        if add_item_to_cart(ctx, product_id, name, sale_unit, quantity, sale_price, qty):
            modal.destroy()

    btns = tk.Frame(body, bg=PANEL_BG)
    btns.pack(pady=(14, 24))
    tk.Button(btns, text="Add to Cart", bg="#16a34a", fg="white", font=("Arial", 16, "bold"),
              command=submit, padx=18, pady=10, **button_border).pack(side="left", padx=8)
    tk.Button(btns, text="Cancel", bg="#6b7280", fg="white", font=("Arial", 16, "bold"),
              command=modal.destroy, padx=18, pady=10, **button_border).pack(side="left", padx=8)

    qty_entry.bind("<Return>", lambda _e: submit())
    center_window(modal, 720, 560, root)


def open_cart_item_modal(ctx, _event=None):
    cart_tree = ctx["cart_tree"]
    cursor = ctx["cursor"]
    cart = ctx["cart"]
    selected = cart_tree.focus()
    if not selected:
        return

    values = cart_tree.item(selected, "values")
    item_id = int(values[0])
    cart_item = next((item for item in cart if item["id"] == item_id), None)
    if not cart_item:
        return

    cursor.execute("SELECT quantity FROM items WHERE id=?", (item_id,))
    row = cursor.fetchone()
    available_stock = float(row[0]) if row else 0
    cursor.execute("SELECT unit FROM items WHERE id=?", (item_id,))
    unit_row = cursor.fetchone()
    unit = cart_item.get("unit") or (unit_row[0] if unit_row and unit_row[0] else "pcs")
    button_border = ctx["button_border"]
    root = ctx["root"]

    modal = tk.Toplevel(root)
    modal.title("Edit Cart Item")
    modal.configure(bg=DASHBOARD_CONTENT_BG)
    modal.resizable(False, False)
    modal.transient(root)
    modal.grab_set()

    header = tk.Frame(modal, bg=DASHBOARD_HEADER_BG, highlightthickness=1, highlightbackground=DASHBOARD_HEADER_BORDER)
    header.pack(fill="x")
    title_frame = tk.Frame(header, bg=DASHBOARD_HEADER_BG)
    title_frame.pack(padx=24, pady=14)
    add_header_logo(title_frame, DASHBOARD_HEADER_BG, size=44)
    tk.Label(title_frame, text="Edit Cart Item", font=("Arial", 24, "bold"), bg=DASHBOARD_HEADER_BG, fg=DASHBOARD_HEADER_FG).pack(side="left")

    body = tk.Frame(modal, bg=PANEL_BG, padx=28, pady=22, highlightthickness=1, highlightbackground="black")
    body.pack(fill="both", expand=True, padx=26, pady=22)
    tk.Label(body, text=cart_item["name"], font=("Arial", 20, "bold"), bg=PANEL_BG, wraplength=520, justify="center").pack(pady=(0, 8))
    available_text = format_fine_sand_stock(available_stock) if is_fine_sand(cart_item["name"]) else f"{format_pos_quantity(available_stock)} {unit}"
    tk.Label(body, text=f"Available stock: {available_text}", font=("Arial", 16, "bold"), bg=PANEL_BG, fg="#1e40af").pack(pady=(0, 18))

    form = tk.Frame(body, bg=PANEL_BG)
    form.pack(pady=8, fill="x")
    tk.Label(form, text="Quantity", bg=PANEL_BG, font=("Arial", 17, "bold")).grid(row=0, column=0, padx=(0, 12), pady=8)
    qty_entry = tk.Entry(form, width=14, font=("Arial", 18), justify="center", bd=2, relief="solid")
    qty_entry.grid(row=0, column=1, pady=8, ipady=4)
    qty_entry.insert(0, str(cart_item["qty"]))
    qty_entry.focus_set()
    qty_entry.select_range(0, tk.END)
    tk.Button(
        form,
        text="-",
        command=lambda: nudge_quantity(qty_entry, -1, 0, minimum=0),
        bg="#dc2626",
        fg="white",
        activebackground="#b91c1c",
        activeforeground="white",
        font=("Arial", 18, "bold"),
        width=4,
        padx=4,
        pady=3,
        **button_border,
    ).grid(row=0, column=2, padx=(8, 0), pady=8)
    tk.Button(
        form,
        text="+",
        command=lambda: nudge_quantity(qty_entry, 1, 0, minimum=0),
        bg="#16a34a",
        fg="white",
        activebackground="#15803d",
        activeforeground="white",
        font=("Arial", 18, "bold"),
        width=4,
        padx=4,
        pady=3,
        **button_border,
    ).grid(row=0, column=3, padx=(8, 0), pady=8)

    sale_unit_var = tk.StringVar(value=unit if is_fine_sand(cart_item["name"]) else unit)
    price_var = tk.StringVar(value=f"Price: {format_money_value(cart_item['price'])}")
    if is_fine_sand(cart_item["name"]):
        tk.Label(form, textvariable=price_var, bg=PANEL_BG, font=("Arial", 14, "bold"), fg="#991b1b").grid(row=2, column=1, columnspan=3, sticky="w", pady=(2, 0))

        def update_price_for_unit(*_args):
            current_price = fine_sand_price_for_unit(cursor, item_id, sale_unit_var.get())
            price_var.set(f"Price: {format_money_value(current_price)}")

        sale_unit_var.trace_add("write", update_price_for_unit)
        tk.Label(form, text="Unit", bg=PANEL_BG, font=("Arial", 17, "bold")).grid(row=1, column=0, padx=(0, 12), pady=8)
        ttk.Combobox(
            form,
            textvariable=sale_unit_var,
            values=FINE_SAND_TRANSACTION_UNITS,
            state="readonly",
            width=13,
            font=("Arial", 16),
        ).grid(row=1, column=1, columnspan=3, sticky="ew", pady=8)

    quick_row = tk.Frame(body, bg=PANEL_BG)
    quick_row.pack(pady=(8, 10), fill="x")
    for idx, step in enumerate((-20, -10, -5, 5, 10, 20)):
        tk.Button(
            quick_row,
            text=f"{step:+}",
            command=lambda delta=step: nudge_quantity(qty_entry, delta, 0, minimum=0),
            bg="#e5e7eb",
            fg="#111827",
            activebackground="#d1d5db",
            activeforeground="#111827",
            font=("Arial", 14, "bold"),
            padx=8,
            pady=6,
            width=6,
            **button_border,
        ).grid(row=0, column=idx, padx=2, sticky="ew")
        quick_row.grid_columnconfigure(idx, weight=1)

    def save_changes():
        qty_text = qty_entry.get().strip()
        try:
            sale_unit = sale_unit_var.get()
            new_qty = parse_sale_quantity(qty_text, cart_item["name"], sale_unit)
        except ValueError:
            show_pos_error(modal, "Error", "Enter a valid quantity.")
            return
        if new_qty <= 0:
            show_pos_error(modal, "Error", "Enter a valid quantity.")
            return
        requested_stock = fine_sand_cubic_deduction(new_qty, sale_unit) if is_fine_sand(cart_item["name"]) else new_qty
        if requested_stock > available_stock:
            show_pos_error(modal, "Error", "Not enough fine sand stock available." if is_fine_sand(cart_item["name"]) else "Stocks aren't enough.")
            return
        cart_item["qty"] = new_qty
        cart_item["unit"] = sale_unit
        if is_fine_sand(cart_item["name"]):
            cart_item["price"] = fine_sand_price_for_unit(cursor, item_id, sale_unit)
        cart_item["total"] = new_qty * cart_item["price"]
        update_cart(ctx)
        modal.destroy()

    def remove_item():
        if not ask_pos_confirmation(modal, "Remove Item", f"Remove {cart_item['name']} from the cart?", confirm_text="Remove", accent_color=CANCEL_RED):
            return
        cart.remove(cart_item)
        update_cart(ctx)
        modal.destroy()

    btns = tk.Frame(body, bg=PANEL_BG)
    btns.pack(pady=(14, 24))
    tk.Button(btns, text="Save", bg="#16a34a", fg="white", font=("Arial", 16, "bold"),
              command=save_changes, padx=18, pady=10, **button_border).pack(side="left", padx=8)
    tk.Button(btns, text="Remove", bg="#dc3545", fg="white", font=("Arial", 16, "bold"),
              command=remove_item, padx=18, pady=10, **button_border).pack(side="left", padx=8)
    tk.Button(btns, text="Cancel", bg="#6b7280", fg="white", font=("Arial", 16, "bold"),
              command=modal.destroy, padx=18, pady=10, **button_border).pack(side="left", padx=8)

    qty_entry.bind("<Return>", lambda _e: save_changes())
    center_window(modal, 720, 560, root)


def generate_invoice_pdf(cart_items, total_amount, money_received, change, mode, platform, txn_id):
    try:
        from fpdf import FPDF
    except ImportError:
        show_pos_warning(
            None,
            "PDF Library Missing",
            "Receipt PDF was skipped because 'fpdf' is not installed.\nInstall it with: pip install fpdf.",
        )
        return None

    documents_path = os.path.expanduser("~/Documents")
    display_txn_id = compact_receipt_txn_id(txn_id)
    pdf_path = os.path.join(documents_path, f"receipt_{display_txn_id}.pdf")
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", "B", 14)
    pdf.cell(0, 8, "JASP Hardware", ln=True)
    pdf.set_font("Arial", "", 11)
    pdf.cell(0, 6, "123 Business St, City", ln=True)
    pdf.cell(0, 6, "email@example.com | +63-900-000-0000", ln=True)
    pdf.ln(4)
    pdf.cell(0, 6, f"Date/Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.cell(0, 6, f"Transaction ID: {display_txn_id}", ln=True)
    pdf.ln(6)
    pdf.set_font("Arial", "B", 11)
    pdf.cell(60, 8, "Item", 1)
    pdf.cell(30, 8, "Qty", 1, align="C")
    pdf.cell(40, 8, "Price", 1, align="R")
    pdf.cell(40, 8, "Total", 1, ln=True, align="R")
    pdf.set_font("Arial", "", 11)
    for item in cart_items:
        pdf.cell(60, 8, item["name"], 1)
        pdf.cell(30, 8, f"x{item['qty']}", 1, align="C")
        pdf.cell(40, 8, f"{item['price']:.2f}", 1, align="R")
        pdf.cell(40, 8, f"{item['total']:.2f}", 1, ln=True, align="R")
    pdf.ln(4)
    pdf.cell(0, 8, f"Total Amount: {total_amount:.2f}", ln=True)
    payment_label = "Money Received" if mode == "Cash" else "Amount Paid"
    pdf.cell(0, 8, f"{payment_label}: {money_received:.2f}", ln=True)
    pdf.cell(0, 8, f"Mode of Payment: {mode}" + (f" ({platform})" if platform else ""), ln=True)
    if mode == "Cash":
        pdf.cell(0, 8, f"Change: {change:.2f}", ln=True)
    pdf.output(pdf_path)
    return pdf_path


def open_invoice_window(ctx, cart_items, total_amount, money_received, change, mode, platform, txn_id):
    pos_root = ctx["root"]
    if pos_root.winfo_exists():
        pos_root.deiconify()
        pos_root.lift()
        pos_root.focus_force()

    inv_window = tk.Toplevel(ctx["root"])
    inv_window.title("Receipt")
    inv_window.configure(bg=DASHBOARD_CONTENT_BG)
    inv_window.resizable(True, True)
    inv_window.minsize(720, 720)
    inv_window.transient(pos_root)
    button_border = ctx["button_border"]
    display_txn_id = compact_receipt_txn_id(txn_id)
    receipt_style = ttk.Style(inv_window)
    receipt_style.configure("Receipt.Treeview", font=("Arial", 14), rowheight=34)
    receipt_style.configure("Receipt.Treeview.Heading", font=("Arial", 13, "bold"))

    header_frame = tk.Frame(inv_window, bg=DASHBOARD_HEADER_BG, highlightthickness=1, highlightbackground=DASHBOARD_HEADER_BORDER)
    header_frame.pack(fill="x")
    header_inner = tk.Frame(header_frame, bg=DASHBOARD_HEADER_BG)
    header_inner.pack(fill="x", padx=24, pady=16)
    add_header_logo(header_inner, DASHBOARD_HEADER_BG, size=54)
    title_block = tk.Frame(header_inner, bg=DASHBOARD_HEADER_BG)
    title_block.pack(side="left")
    tk.Label(title_block, text="JASP Hardware", font=("Arial", 22, "bold"), bg=DASHBOARD_HEADER_BG, fg=DASHBOARD_HEADER_FG).pack(anchor="w")
    tk.Label(title_block, text="Official POS Receipt", font=("Arial", 13, "bold"), bg=DASHBOARD_HEADER_BG, fg=DASHBOARD_HEADER_SUBTLE_FG).pack(anchor="w")

    content_frame = tk.Frame(inv_window, bg=PANEL_BG, padx=22, pady=18, highlightthickness=1, highlightbackground="black")
    content_frame.pack(fill="both", expand=True, padx=28, pady=(22, 12))

    meta_frame = tk.Frame(content_frame, bg=PANEL_BG)
    meta_frame.pack(fill="x", pady=(0, 14))
    tk.Label(meta_frame, text=f"Transaction ID: {display_txn_id}", font=("Arial", 16, "bold"), bg=PANEL_BG, fg="#991b1b").pack(side="left")
    tk.Label(meta_frame, text=datetime.now().strftime("%Y-%m-%d %H:%M:%S"), font=("Arial", 13, "bold"), bg=PANEL_BG, fg="#475569").pack(side="right")

    table_frame = tk.Frame(content_frame, bg=PANEL_BG)
    table_frame.pack(fill="both", expand=True, pady=(0, 14))
    receipt_columns = ("Item", "Qty", "Selling Price", "Total")
    receipt_tree = ttk.Treeview(table_frame, columns=receipt_columns, show="headings", height=7, style="Receipt.Treeview")
    receipt_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=receipt_tree.yview)
    receipt_tree.configure(yscrollcommand=receipt_scroll.set)
    receipt_tree.grid(row=0, column=0, sticky="nsew")
    receipt_scroll.grid(row=0, column=1, sticky="ns")
    table_frame.grid_columnconfigure(0, weight=1)
    table_frame.grid_rowconfigure(0, weight=1)
    receipt_column_specs = {
        "Item": (300, 180, 2.7),
        "Qty": (80, 70, 0.7),
        "Selling Price": (150, 130, 1.3),
        "Total": (130, 110, 1.2),
    }
    for col, (width, minwidth, _weight), anchor in (
        ("Item", receipt_column_specs["Item"], "w"),
        ("Qty", receipt_column_specs["Qty"], "center"),
        ("Selling Price", receipt_column_specs["Selling Price"], "e"),
        ("Total", receipt_column_specs["Total"], "e"),
    ):
        receipt_tree.heading(col, text=col)
        receipt_tree.column(col, width=width, minwidth=minwidth, anchor=anchor, stretch=False)
    receipt_tree.tag_configure("oddrow", background="#ffffff", foreground="#000000")
    receipt_tree.tag_configure("evenrow", background="#e0f2fe", foreground="#000000")
    for index, item in enumerate(cart_items):
        receipt_tree.insert(
            "",
            "end",
            values=(item["name"], item["qty"], f"{item['price']:.2f}", f"{item['total']:.2f}"),
            tags=("evenrow" if index % 2 else "oddrow",),
        )
    auto_fit_tree_columns(receipt_tree, receipt_column_specs, padding=34)

    total_panel = tk.Frame(content_frame, bg=DASHBOARD_CONTENT_BG, padx=16, pady=12, highlightthickness=1, highlightbackground="black")
    total_panel.pack(fill="x")
    tk.Label(total_panel, text=f"Total Amount: {total_amount:.2f}", font=("Arial", 18, "bold"), bg=DASHBOARD_CONTENT_BG, fg="#991b1b").pack(anchor="w", pady=2)
    payment_label = "Money Received" if mode == "Cash" else "Amount Paid"
    tk.Label(total_panel, text=f"{payment_label}: {money_received:.2f}", font=("Arial", 14, "bold"), bg=DASHBOARD_CONTENT_BG).pack(anchor="w", pady=2)
    tk.Label(total_panel, text=f"Mode of Payment: {mode}" + (f" ({platform})" if platform else ""), font=("Arial", 14, "bold"), bg=DASHBOARD_CONTENT_BG).pack(anchor="w", pady=2)
    status_var = tk.StringVar(value="Status: Paid")
    status_label = tk.Label(total_panel, textvariable=status_var, font=("Arial", 14, "bold"), bg=DASHBOARD_CONTENT_BG, fg="#15803d")
    status_label.pack(anchor="w", pady=2)
    if mode == "Cash":
        tk.Label(total_panel, text=f"Change: {change:.2f}", font=("Arial", 14, "bold"), bg=DASHBOARD_CONTENT_BG, fg="#15803d").pack(anchor="w", pady=2)

    def print_receipt():
        pdf_path = generate_invoice_pdf(cart_items, total_amount, money_received, change, mode, platform, txn_id)
        if pdf_path:
            ctx["cursor"].execute(
                "UPDATE sales SET receipt_path=? WHERE transaction_id=?",
                (pdf_path, txn_id),
            )
            ctx["conn"].commit()
            show_pos_success(inv_window, "Receipt Downloaded", f"Receipt saved to:\n{pdf_path}")

    def void_transaction():
        if not ask_pos_confirmation(
            inv_window,
            "Void Transaction",
            "Void this transaction and return the sold items to inventory?",
            confirm_text="Void",
            accent_color=CANCEL_RED,
        ):
            return

        cursor = ctx["cursor"]
        conn = ctx["conn"]
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM sales
            WHERE transaction_id = ?
              AND COALESCE(payment_status, 'Paid') <> 'Void'
            """,
            (txn_id,),
        )
        active_rows = int(cursor.fetchone()[0] or 0)
        if active_rows == 0:
            status_var.set("Status: Void")
            status_label.config(fg=CANCEL_RED)
            void_button.config(state="disabled", bg="#9ca3af", cursor="arrow")
            show_pos_warning(inv_window, "Already Void", "This transaction has already been voided.")
            return

        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for item in cart_items:
            stock_qty = fine_sand_cubic_deduction(item["qty"], item.get("unit", "")) if is_fine_sand(item["name"]) else item["qty"]
            cursor.execute(
                "UPDATE items SET quantity = quantity + ? WHERE id = ?",
                (stock_qty, item["id"]),
            )
            if item["name"] == CHB_ITEM_NAME:
                cursor.execute(
                    """
                    UPDATE chb_inventory_state
                    SET total_sold = MAX(total_sold - ?, 0),
                        available = available + ?,
                        updated_ts = ?
                    WHERE id = ?
                    """,
                    (item["qty"], item["qty"], now, CHB_STATE_ID),
                )

        cursor.execute(
            """
            UPDATE sales
            SET payment_status = 'Void'
            WHERE transaction_id = ?
            """,
            (txn_id,),
        )
        conn.commit()
        notify_inventory_views()
        load_inventory(ctx, ctx["search_entry"].get())
        if ctx["root"].winfo_exists():
            ctx["root"].deiconify()
            ctx["root"].lift()
            ctx["root"].focus_force()
        status_var.set("Status: Void")
        status_label.config(fg=CANCEL_RED)
        print_button.config(state="disabled", bg="#9ca3af", cursor="arrow")
        void_button.config(state="disabled", bg="#9ca3af", cursor="arrow")
        show_pos_success(inv_window, "Transaction Voided", "Items were returned to inventory and the sale was marked as void.")

    btn_frame = tk.Frame(inv_window, bg=DASHBOARD_CONTENT_BG)
    btn_frame.pack(pady=(0, 8))
    for col_index in range(3):
        btn_frame.grid_columnconfigure(col_index, weight=1, uniform="receipt_actions")
    action_button_options = {
        "font": ("Arial", 13, "bold"),
        "width": 22,
        "padx": 10,
        "pady": 10,
        **button_border,
    }
    print_button = tk.Button(
        btn_frame,
        text="Print / Download",
        bg="#16a34a",
        fg="white",
        command=print_receipt,
        **action_button_options,
    )
    print_button.grid(row=0, column=0, sticky="ew", padx=6)
    void_button = tk.Button(
        btn_frame,
        text="Void Transaction",
        bg="#f97316",
        fg="white",
        command=void_transaction,
        **action_button_options,
    )
    void_button.grid(row=0, column=1, sticky="ew", padx=6)
    tk.Button(
        btn_frame,
        text="Close",
        bg="#ef4444",
        fg="white",
        command=inv_window.destroy,
        **action_button_options,
    ).grid(row=0, column=2, sticky="ew", padx=6)
    center_receipt_window(inv_window, pos_root)
    inv_window.grab_set()
    inv_window.lift()
    inv_window.attributes("-topmost", True)
    inv_window.after(350, lambda: inv_window.attributes("-topmost", False) if inv_window.winfo_exists() else None)
    inv_window.after(80, lambda: (
        auto_fit_tree_columns(receipt_tree, receipt_column_specs, padding=34),
        center_receipt_window(inv_window, pos_root),
        inv_window.lift(),
        inv_window.focus_force(),
    ) if inv_window.winfo_exists() else None)
    inv_window.focus_force()


def finalize_transaction(ctx, mode, money_received, platform):
    cart = ctx["cart"]
    if not cart:
        show_pos_error(ctx["root"], "Error", "Cart is empty.")
        return False

    cursor = ctx["cursor"]
    conn = ctx["conn"]
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    txn_id = datetime.now().strftime("TXN-%Y%m%d%H%M%S")
    cashier = session.get_current_username("Admin")
    total_amount = sum(item["total"] for item in cart)
    change = money_received - total_amount if mode == "Cash" else 0

    for item in cart:
        stock_qty = fine_sand_cubic_deduction(item["qty"], item.get("unit", "")) if is_fine_sand(item["name"]) else item["qty"]
        cursor.execute("SELECT COALESCE(quantity, 0) FROM items WHERE id=?", (item["id"],))
        row = cursor.fetchone()
        available = float(row[0] or 0) if row else 0
        if stock_qty > available:
            show_pos_error(ctx["root"], "Error", "Not enough fine sand stock available." if is_fine_sand(item["name"]) else "Stocks aren't enough.")
            return False

    for item in cart:
        stock_qty = fine_sand_cubic_deduction(item["qty"], item.get("unit", "")) if is_fine_sand(item["name"]) else item["qty"]
        cursor.execute("UPDATE items SET quantity = quantity - ? WHERE id=?", (stock_qty, item["id"]))
        cursor.execute(
            """
            INSERT INTO sales (
                item_name, qty, price, raw_price, total, ts,
                transaction_id, cashier, payment_status, payment_method,
                payment_received, change_amount
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                item["name"],
                item["qty"],
                item["price"],
                item.get("raw_price", 0),
                item["total"],
                now,
                txn_id,
                cashier,
                "Paid",
                mode,
                money_received,
                change,
            ),
        )
        if item["name"] == CHB_ITEM_NAME:
            cursor.execute(
                """
                UPDATE chb_inventory_state
                SET total_sold = total_sold + ?,
                    available = MAX(available - ?, 0),
                    updated_ts = ?
                WHERE id = ?
                """,
                (item["qty"], item["qty"], now, CHB_STATE_ID),
            )
    conn.commit()
    notify_inventory_views()

    cart_items_copy = [item.copy() for item in cart]
    cart.clear()
    update_cart(ctx)
    load_inventory(ctx)
    ctx["pending_receipt"] = (cart_items_copy, total_amount, money_received, change, mode, platform, txn_id)
    return True


def open_payment_modal(ctx):
    cart = ctx["cart"]
    root = ctx["root"]
    if not cart:
        show_pos_error(root, "Error", "Cart is empty.")
        return
    total_amount = sum(item["total"] for item in cart)
    button_border = ctx["button_border"]

    pay_modal = tk.Toplevel(root)
    pay_modal.title("Complete Payment")
    pay_modal.grab_set()
    pay_modal.configure(bg="white")
    pay_modal.resizable(False, False)

    payment_style = ttk.Style(pay_modal)
    payment_style.configure("Payment.Treeview", font=("Arial", 17), rowheight=38)
    payment_style.configure("Payment.Treeview.Heading", font=("Arial", 16, "bold"))

    tk.Label(pay_modal, text="Checkout Summary", font=("Arial", 28, "bold"), bg="white", fg="#2563eb").pack(pady=(18, 8))
    tk.Label(pay_modal, text=f"Amount Due: P{total_amount:.2f}", font=("Arial", 22, "bold"), bg="white", fg="#991b1b").pack(pady=(0, 10))

    payment_method = tk.StringVar(value="Cash")
    method_frame = tk.Frame(pay_modal, bg="white")
    method_frame.pack(fill="x", padx=24, pady=(0, 10))
    tk.Label(method_frame, text="Payment Method:", bg="white", font=("Arial", 17, "bold")).pack(side="left", padx=(0, 14))
    tk.Radiobutton(method_frame, text="Cash", variable=payment_method, value="Cash", bg="white", font=("Arial", 16, "bold"),
                   selectcolor="white", activebackground="white").pack(side="left", padx=(0, 16))
    tk.Radiobutton(method_frame, text="GCash", variable=payment_method, value="GCash", bg="white", font=("Arial", 16, "bold"),
                   selectcolor="white", activebackground="white").pack(side="left")

    summary_frame = tk.Frame(pay_modal, bg="white")
    summary_frame.pack(fill="x", padx=22, pady=(0, 10))
    columns = ("Item", "Unit", "Qty", "Selling Price", "Total")
    summary_tree = ttk.Treeview(summary_frame, columns=columns, show="headings", height=4, style="Payment.Treeview")
    summary_scroll = ttk.Scrollbar(summary_frame, orient="vertical", command=summary_tree.yview)
    summary_tree.configure(yscrollcommand=summary_scroll.set)
    summary_tree.grid(row=0, column=0, sticky="nsew")
    summary_scroll.grid(row=0, column=1, sticky="ns")
    summary_frame.grid_columnconfigure(0, weight=1)
    summary_frame.grid_rowconfigure(0, weight=1)

    for col, width, anchor in (("Item", 240, "w"), ("Unit", 130, "center"), ("Qty", 80, "center"), ("Selling Price", 160, "e"), ("Total", 120, "e")):
        summary_tree.heading(col, text=col)
        summary_tree.column(col, width=width, anchor=anchor, stretch=True)
    summary_tree.tag_configure("oddrow", background="#ffffff", foreground="#000000")
    summary_tree.tag_configure("evenrow", background="#bfdbfe", foreground="#000000")
    for index, item in enumerate(cart):
        tag = "evenrow" if index % 2 else "oddrow"
        summary_tree.insert(
            "",
            tk.END,
            values=(item["name"], item.get("unit", "pcs"), item["qty"], f"{item['price']:.2f}", f"{item['total']:.2f}"),
            tags=(tag,),
        )

    money_frame = tk.Frame(pay_modal, bg="white")
    money_frame.pack(fill="x", padx=24, pady=(4, 8))
    money_label = tk.Label(money_frame, text="Money Received:", bg="white", font=("Arial", 17, "bold"))
    money_label.pack(anchor="w")
    money_entry = tk.Entry(money_frame, font=("Arial", 19), bd=2, relief="solid")
    money_entry.pack(fill="x", pady=5, ipady=4)
    money_entry.focus_set()

    change_var = tk.StringVar(value="Change: 0.00")
    change_label = tk.Label(pay_modal, textvariable=change_var, bg="white", font=("Arial", 18, "bold"), fg="#15803d")
    change_label.pack(anchor="w", padx=24, pady=(0, 8))

    def update_change(*_):
        value = money_entry.get().strip()
        if not value:
            change_var.set("Change: 0.00")
            return
        try:
            received = float(value)
        except ValueError:
            change_var.set("Change: --")
            return
        change_var.set(f"Change: {received - total_amount:.2f}")

    def update_payment_method(*_):
        if payment_method.get() == "GCash":
            money_label.config(text="Amount Paid:")
            money_entry.config(state="normal")
            money_entry.delete(0, tk.END)
            change_var.set("Change: 0.00")
            money_entry.focus_set()
        else:
            money_label.config(text="Money Received:")
            money_entry.config(state="normal")
            money_entry.delete(0, tk.END)
            change_var.set("Change: 0.00")
            money_entry.focus_set()

    def on_pay():
        method = payment_method.get()
        if method == "GCash":
            try:
                received = float(money_entry.get())
            except ValueError:
                show_pos_error(pay_modal, "Error", "Enter a valid amount paid.")
                return
            if received < total_amount:
                show_pos_error(pay_modal, "Error", "Amount paid is less than total.")
                return
        else:
            try:
                received = float(money_entry.get())
            except ValueError:
                show_pos_error(pay_modal, "Error", "Enter a valid amount for money received.")
                return
            if received < total_amount:
                show_pos_error(pay_modal, "Error", "Money received is less than total.")
                return
        if finalize_transaction(ctx, method, received, ""):
            receipt_data = ctx.pop("pending_receipt", None)
            try:
                pay_modal.grab_release()
            except tk.TclError:
                pass
            pay_modal.destroy()
            if receipt_data:
                root.deiconify()
                root.lift()
                root.focus_force()
                root.update_idletasks()
                open_invoice_window(ctx, *receipt_data)

    money_entry.bind("<KeyRelease>", update_change)
    money_entry.bind("<Return>", lambda _event: on_pay())
    payment_method.trace_add("write", update_payment_method)

    btns = tk.Frame(pay_modal, bg="white")
    btns.pack(pady=(6, 20))
    tk.Button(btns, text="Checkout", bg="#16a34a", fg="white", font=("Arial", 15, "bold"),
              command=on_pay, padx=15, pady=10, **button_border).pack(side="left", padx=6)
    tk.Button(btns, text="Cancel", bg="#ef4444", fg="white", font=("Arial", 15, "bold"),
              command=pay_modal.destroy, padx=15, pady=10, **button_border).pack(side="left", padx=6)

    center_window(pay_modal, 820, 610, root)
