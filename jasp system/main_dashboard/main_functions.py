import calendar
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import font as tkfont
from tkinter import ttk


# Define shared colors for dashboard pages, cards, and charts.
BG_PAGE = "#edeff3"
BG_SIDEBAR = "#273142"
BG_CARD = "#ffffff"
PRIMARY = "#2563eb"
ACCENT = "#60a5fa"
TEXT_PRIMARY = "#1e293b"
TEXT_MUTED = "#6b7280"
LINE = "#e5e7eb"


def spacer(parent, h=12):
    # Insert vertical spacing that matches the parent background.
    tk.Frame(parent, height=h, bg=parent["bg"]).pack(fill="x")


def stat_card(parent, title, value, subtitle="", bg=BG_CARD, header_bg=None):
    # Build a dashboard stat card with a colored header and large value.
    header_bg = header_bg or bg
    card = tk.Frame(parent, bg=bg, bd=0, relief="flat",
                    highlightthickness=1, highlightbackground="black")
    card.pack(side="left", expand=True, fill="both", padx=8)

    header = tk.Frame(card, bg=header_bg)
    header.pack(fill="x")
    tk.Label(header, text=title.upper(), bg=header_bg, fg="white",
             font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=(10, 8))
    tk.Label(card, text=value, bg=bg, fg="#020617",
             font=("Arial", 28, "bold")).pack(anchor="w", padx=16, pady=(10, 0))
    if subtitle:
        tk.Label(card, text=subtitle, bg=bg, fg=TEXT_MUTED,
                 font=("Arial", 11, "bold")).pack(anchor="w", padx=16, pady=(0, 14))
    return card


def build_table(parent, columns, rows):
    # Build a styled dashboard Treeview table with a vertical scrollbar.
    style = ttk.Style()
    style.configure("Dash.Treeview", font=("Arial", 12), rowheight=32,
                    background=BG_CARD, fieldbackground=BG_CARD)
    style.configure("Dash.Treeview.Heading", font=("Arial", 12, "bold"), foreground=TEXT_PRIMARY)
    style.map("Dash.Treeview", background=[("selected", ACCENT)])

    col_ids = [col for col, _, _ in columns]
    tree = ttk.Treeview(parent, columns=col_ids, show="headings", style="Dash.Treeview", height=6)
    for col, heading, width in columns:
        tree.heading(col, text=heading)
        tree.column(col, anchor="w", width=width, stretch=True)
    for row in rows:
        tree.insert("", "end", values=row)

    vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=vsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    parent.grid_rowconfigure(0, weight=1)
    parent.grid_columnconfigure(0, weight=1)
    return tree


def render_table_or_empty(container, columns, rows, empty_text):
    # Render a table when rows exist or an empty-state label otherwise.
    if rows:
        build_table(container, columns, rows)
    else:
        tk.Label(container, text=empty_text, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Arial", 13, "italic")).pack(expand=True, fill="both", pady=12)


def money(val):
    # Format a numeric value as Philippine peso currency.
    return f"\u20b1{val:,.2f}"


def format_dashboard_datetime(ts):
    # Format stored sale timestamps for dashboard display.
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(ts, fmt).strftime("%b %d, %Y | %I:%M %p").replace(" 0", " ")
        except (TypeError, ValueError):
            continue
    return str(ts or "")


def compact_items(item_summary, item_count):
    # Shorten grouped item text for compact transaction tables.
    if not item_summary:
        return ""
    first_item = item_summary.split(", ")[0]
    if item_count > 1:
        return f"{first_item} + {item_count - 1} more"
    return first_item


def compact_txn_id(txn_id):
    # Show only the trailing part of long transaction ids.
    text = str(txn_id or "")
    return text[-5:] if len(text) > 5 else text


def render_recent_transactions(container, rows, empty_text):
    # Render the dashboard recent transactions preview table.
    if not rows:
        tk.Label(container, text=empty_text, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Arial", 13, "italic")).pack(expand=True, fill="both", pady=12)
        return

    # Configure the recent transactions table style and scrollbars.
    style = ttk.Style()
    style.configure(
        "RecentDash.Treeview",
        font=("Arial", 13),
        rowheight=38,
        background=BG_CARD,
        fieldbackground=BG_CARD,
    )
    style.configure(
        "RecentDash.Treeview.Heading",
        font=("Arial", 12, "bold"),
        foreground=TEXT_PRIMARY,
    )
    style.map("RecentDash.Treeview", background=[("selected", PRIMARY)], foreground=[("selected", "white")])

    columns = ("txn", "date", "items", "qty", "total", "cashier", "status")
    tree = ttk.Treeview(container, columns=columns, show="headings", style="RecentDash.Treeview", height=4)
    vsb = ttk.Scrollbar(container, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(container, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    container.grid_rowconfigure(0, weight=1)
    container.grid_columnconfigure(0, weight=1)

    headings = [
        ("txn", "TXN ID", 70, 110, "w"),
        ("date", "Date & Time", 150, 230, "w"),
        ("items", "Item(s) Sold", 160, 360, "w"),
        ("qty", "Qty", 60, 90, "e"),
        ("total", "Total", 90, 140, "e"),
        ("cashier", "Cashier", 90, 180, "w"),
        ("status", "Status", 80, 120, "center"),
    ]
    display_rows = []
    for row in rows:
        # Convert raw transaction rows into display-ready values.
        txn_id, ts, item_summary, item_count, qty, total, cashier, status = row
        display_rows.append((
            compact_txn_id(txn_id),
            format_dashboard_datetime(ts),
            compact_items(item_summary, item_count),
            f"{qty:,}",
            money(total),
            cashier or "Admin",
            status or "Paid",
        ))

    body_font = tkfont.Font(family="Arial", size=13)
    heading_font = tkfont.Font(family="Arial", size=12, weight="bold")
    column_widths = {}
    for index, (col, heading, min_width, max_width, _anchor) in enumerate(headings):
        # Measure heading and row text to choose readable column widths.
        widest = heading_font.measure(heading)
        for values in display_rows:
            widest = max(widest, body_font.measure(str(values[index])))
        column_widths[col] = min(max(widest + 28, min_width), max_width)

    for col, heading, _min_width, _max_width, anchor in headings:
        tree.heading(col, text=heading)
        tree.column(col, width=column_widths[col], minwidth=column_widths[col], anchor=anchor, stretch=True)

    tree.tag_configure("blue_row", background="#e0f2fe", foreground=TEXT_PRIMARY)
    tree.tag_configure("white_row", background="#ffffff", foreground=TEXT_PRIMARY)

    for row_index, values in enumerate(display_rows):
        tree.insert(
            "",
            "end",
            values=values,
            tags=("blue_row" if row_index % 2 == 0 else "white_row",),
        )


def center_window(window, width, height, parent=None):
    # Center a popup over its parent window or the screen.
    window.update_idletasks()
    if parent and parent.winfo_exists():
        x_pos = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y_pos = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    else:
        x_pos = (window.winfo_screenwidth() // 2) - (width // 2)
        y_pos = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{max(x_pos, 0)}+{max(y_pos, 0)}")


def parse_dashboard_date(date_text):
    # Parse a YYYY-MM-DD dashboard date and fall back to today.
    try:
        return datetime.strptime((date_text or "").strip(), "%Y-%m-%d")
    except ValueError:
        return datetime.now()


def open_date_calendar(parent, date_var, on_select=None):
    # Open a small or large dashboard calendar popup.
    selected_date = parse_dashboard_date(date_var.get())
    large_calendar = bool(getattr(parent, "_large_calendar", False))
    day_width = 7 if large_calendar else 5
    day_font = ("Arial", 13, "bold") if large_calendar else ("Arial", 9, "bold")
    title_font = ("Arial", 16, "bold") if large_calendar else ("Arial", 11, "bold")
    nav_font = ("Arial", 14, "bold") if large_calendar else ("Arial", 10, "bold")
    title_width = 20 if large_calendar else 18
    nav_width = 5 if large_calendar else 4

    cal_win = tk.Toplevel(parent)
    cal_win.title("Select Date")
    cal_win.configure(bg=BG_CARD)
    cal_win.resizable(False, False)
    cal_win.transient(parent)
    cal_win.grab_set()

    year_var = tk.IntVar(value=selected_date.year)
    month_var = tk.IntVar(value=selected_date.month)
    title_var = tk.StringVar()

    header = tk.Frame(cal_win, bg=BG_CARD)
    header.pack(fill="x", padx=10, pady=(10, 4))
    grid = tk.Frame(cal_win, bg=BG_CARD)
    grid.pack(padx=10, pady=(0, 10))

    def select_date(day):
        # Apply the selected date and run the optional callback.
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
        for child in grid.winfo_children():
            child.destroy()
        title_var.set(f"{calendar.month_name[month_var.get()]} {year_var.get()}")

        for col, day_name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            tk.Label(grid, text=day_name, bg=BG_CARD, fg=TEXT_MUTED,
                     font=day_font, width=day_width).grid(row=0, column=col, padx=3, pady=4)

        today = datetime.now()
        for row_index, week in enumerate(calendar.monthcalendar(year_var.get(), month_var.get()), start=1):
            for col_index, day in enumerate(week):
                if not day:
                    tk.Label(grid, text="", bg=BG_CARD, width=5).grid(row=row_index, column=col_index, padx=2, pady=2)
                    continue
                is_today = day == today.day and month_var.get() == today.month and year_var.get() == today.year
                tk.Button(
                    grid,
                    text=str(day),
                    width=day_width,
                    bg=PRIMARY if is_today else "#f8fafc",
                    fg="white" if is_today else TEXT_PRIMARY,
                    activebackground=ACCENT,
                    relief="solid",
                    bd=1,
                    font=day_font,
                    command=lambda d=day: select_date(d),
                ).grid(row=row_index, column=col_index, padx=3, pady=3)

    tk.Button(header, text="<", command=lambda: change_month(-1), bg=ACCENT,
              fg=TEXT_PRIMARY, relief="flat", width=nav_width, font=nav_font).pack(side="left")
    tk.Label(header, textvariable=title_var, bg=BG_CARD, fg=TEXT_PRIMARY,
             font=title_font, width=title_width).pack(side="left", padx=10)
    tk.Button(header, text=">", command=lambda: change_month(1), bg=ACCENT,
              fg=TEXT_PRIMARY, relief="flat", width=nav_width, font=nav_font).pack(side="left")

    # Position the calendar near the center of the parent window.
    render_calendar()
    cal_win.update_idletasks()
    cal_width = 540 if large_calendar else 380
    cal_height = 430 if large_calendar else 300
    x_pos = parent.winfo_rootx() + (parent.winfo_width() // 2) - (cal_width // 2)
    y_pos = parent.winfo_rooty() + (parent.winfo_height() // 2) - (cal_height // 2)
    cal_win.geometry(f"{cal_width}x{cal_height}+{max(x_pos, 0)}+{max(y_pos, 0)}")


def compute_summary_range(period, date_text):
    # Convert a selected period and date into start/end datetimes.
    selected = parse_dashboard_date(date_text)
    if period == "Week":
        start = selected - timedelta(days=selected.weekday())
        end = start + timedelta(days=6)
    elif period == "Month":
        start = datetime(selected.year, selected.month, 1)
        if selected.month == 12:
            end = datetime(selected.year, 12, 31)
        else:
            end = datetime(selected.year, selected.month + 1, 1) - timedelta(days=1)
    else:
        start = selected
        end = selected
    return start, end
