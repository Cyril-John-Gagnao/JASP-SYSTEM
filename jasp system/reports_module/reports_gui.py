import calendar
import os
import tkinter as tk
from datetime import datetime, timedelta
from tkinter import messagebox, ttk

from .reports_constants import (
    ACCENT,
    BG_CARD,
    BG_PAGE,
    BG_SIDEBAR,
    HEADER_BG,
    HEADER_FG,
    HIGHLIGHT_BG,
    HIGHLIGHT_FG,
    LINE,
    NO_DATA_PERIOD_MESSAGE,
    SUMMARY_BG,
    TABLE_HEADER_BG,
    TABLE_HEADER_FG,
    TEXT_MUTED,
    TEXT_PRIMARY,
)
from .reports_database import init_database
from .reports_functions import (
    export_to_pdf,
    generate_chb_production,
    generate_delivery_report,
    generate_financial_summary,
    generate_inventory_status,
    generate_sales_report,
    generate_weekly_sales,
    get_report_date_range,
)
from jasp_theme import (
    DASHBOARD_HEADER_BG,
    DASHBOARD_HEADER_BORDER,
    DASHBOARD_HEADER_FG,
    DASHBOARD_HEADER_SUBTLE_FG,
    add_header_logo,
)
from window_utils import close_window_and_focus_parent

_ACTIVE_DATE_PICKER = None

ACTION_BG = "#2563eb"
ACTION_ACTIVE = "#1d4ed8"
ACTION_SECONDARY = "#16a34a"
ACTION_PURPLE = "#8b5cf6"
PANEL_PAD = 8
SECTION_GAP = 10
REPORT_TITLE_FG = "#2563eb"
REPORTS_HEADER_BG = DASHBOARD_HEADER_BG
PESO = "\u20b1"
SUCCESS_GREEN = "#16a34a"
ERROR_RED = "#dc3545"
CUSTOM_PERIOD_PROMPT = "Select a custom date range, then click Generate Report."


def money(val):
    return f"{PESO}{float(val or 0):,.2f}"


def quantity(val):
    try:
        num = float(val or 0)
    except (TypeError, ValueError):
        return str(val or 0)
    return f"{num:,.3f}".rstrip("0").rstrip(".")


def _parse_picker_date(date_text):
    try:
        return datetime.strptime((date_text or "").strip(), "%Y-%m-%d")
    except ValueError:
        return datetime.now()


def _shift_picker_month(base_date, offset):
    month_index = (base_date.year * 12 + (base_date.month - 1)) + offset
    year = month_index // 12
    month = month_index % 12 + 1
    day = min(base_date.day, calendar.monthrange(year, month)[1])
    return base_date.replace(year=year, month=month, day=day)


def _open_date_picker(anchor_widget, date_var):
    global _ACTIVE_DATE_PICKER

    if _ACTIVE_DATE_PICKER and _ACTIVE_DATE_PICKER.winfo_exists():
        _ACTIVE_DATE_PICKER.destroy()

    popup = tk.Toplevel(anchor_widget.winfo_toplevel())
    _ACTIVE_DATE_PICKER = popup
    popup.title("Select Date")
    popup.transient(anchor_widget.winfo_toplevel())
    popup.resizable(False, False)
    popup.configure(bg=BG_CARD)

    state = {"view_date": _parse_picker_date(date_var.get())}
    today = datetime.now().date()

    def close_popup():
        global _ACTIVE_DATE_PICKER
        if popup.winfo_exists():
            popup.destroy()
        if _ACTIVE_DATE_PICKER is popup:
            _ACTIVE_DATE_PICKER = None

    def choose_date(day):
        selected = state["view_date"].replace(day=day)
        date_var.set(selected.strftime("%Y-%m-%d"))
        close_popup()

    def render_calendar():
        for widget in popup.winfo_children():
            widget.destroy()

        shell = tk.Frame(popup, bg=BG_CARD, padx=8, pady=8)
        shell.pack(fill="both", expand=True)

        header = tk.Frame(shell, bg=BG_CARD)
        header.pack(fill="x", pady=(0, 5))

        nav_options = {
            "font": ("Arial", 9, "bold"),
            "bg": ACCENT,
            "fg": TEXT_PRIMARY,
            "activebackground": SUMMARY_BG,
            "relief": "flat",
            "bd": 0,
            "width": 3,
        }
        tk.Button(
            header,
            text="<",
            command=lambda: (state.__setitem__("view_date", _shift_picker_month(state["view_date"], -1)), render_calendar()),
            **nav_options,
        ).pack(side="left")
        tk.Label(
            header,
            text=state["view_date"].strftime("%B %Y"),
            bg=BG_CARD,
            fg=TEXT_PRIMARY,
            font=("Arial", 10, "bold"),
        ).pack(side="left", expand=True)
        tk.Button(
            header,
            text=">",
            command=lambda: (state.__setitem__("view_date", _shift_picker_month(state["view_date"], 1)), render_calendar()),
            **nav_options,
        ).pack(side="right")

        grid = tk.Frame(shell, bg=BG_CARD)
        grid.pack()

        for col, day_name in enumerate(("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")):
            tk.Label(
                grid,
                text=day_name,
                bg=BG_CARD,
                fg=TEXT_MUTED,
                font=("Arial", 8, "bold"),
                width=4,
            ).grid(row=0, column=col, padx=1, pady=(0, 3))

        selected_date = _parse_picker_date(date_var.get()).date()
        month_days = calendar.monthcalendar(state["view_date"].year, state["view_date"].month)

        for row_index, week in enumerate(month_days, start=1):
            for col_index, day in enumerate(week):
                if not day:
                    tk.Label(grid, text="", bg=BG_CARD, width=4).grid(row=row_index, column=col_index, padx=1, pady=1)
                    continue

                button_bg = BG_CARD
                button_fg = TEXT_PRIMARY
                if (state["view_date"].year, state["view_date"].month, day) == (selected_date.year, selected_date.month, selected_date.day):
                    button_bg = ACTION_BG
                    button_fg = "#ffffff"
                elif (state["view_date"].year, state["view_date"].month, day) == (today.year, today.month, today.day):
                    button_bg = ACCENT

                tk.Button(
                    grid,
                    text=str(day),
                    command=lambda selected_day=day: choose_date(selected_day),
                    bg=button_bg,
                    fg=button_fg,
                    activebackground=ACTION_ACTIVE if button_bg == ACTION_BG else ACCENT,
                    activeforeground="#ffffff" if button_bg == ACTION_BG else TEXT_PRIMARY,
                    relief="flat",
                    bd=0,
                    width=4,
                    font=("Arial", 8),
                    cursor="hand2",
                ).grid(row=row_index, column=col_index, padx=1, pady=1)

        footer = tk.Frame(shell, bg=BG_CARD)
        footer.pack(fill="x", pady=(6, 0))
        tk.Button(
            footer,
            text="Today",
            command=lambda: (date_var.set(datetime.now().strftime("%Y-%m-%d")), close_popup()),
            font=("Arial", 8, "bold"),
            bg=ACCENT,
            fg=TEXT_PRIMARY,
            relief="flat",
            bd=0,
            padx=8,
            pady=3,
        ).pack(side="left")
        tk.Button(
            footer,
            text="Close",
            command=close_popup,
            font=("Arial", 8),
            bg=BG_CARD,
            fg=TEXT_MUTED,
            relief="flat",
            bd=0,
            padx=6,
            pady=3,
        ).pack(side="right")

    popup.protocol("WM_DELETE_WINDOW", close_popup)
    popup.bind("<Escape>", lambda _event: close_popup())
    render_calendar()
    popup.update_idletasks()
    x_pos = anchor_widget.winfo_rootx()
    y_pos = anchor_widget.winfo_rooty() + anchor_widget.winfo_height() + 4
    popup.geometry(f"+{x_pos}+{y_pos}")
    popup.lift()
    popup.focus_force()


def create_date_picker_entry(parent, initial_date, width=12):
    date_var = tk.StringVar(value=initial_date)
    entry = tk.Entry(
        parent,
        textvariable=date_var,
        width=width,
        font=("Arial", 16),
        relief="solid",
        bd=2,
        justify="center",
        state="readonly",
        readonlybackground="#ffffff",
        highlightthickness=1,
        highlightbackground="#000000",
        highlightcolor=ACTION_BG,
        cursor="hand2",
    )
    entry.bind("<Button-1>", lambda _event: _open_date_picker(entry, date_var))
    return entry, date_var


def create_tab_root(parent):
    root = tk.Frame(parent, bg=BG_PAGE)
    root.pack(fill="both", expand=True, padx=20, pady=10)
    root.grid_columnconfigure(0, weight=1)
    root.grid_rowconfigure(1, weight=1)
    return root


def create_filter_bar(parent, title):
    bar = tk.Frame(
        parent,
        bg=BG_PAGE,
        padx=0,
        pady=0,
    )
    bar.grid(row=0, column=0, sticky="ew")
    bar.grid_columnconfigure(99, weight=1)
    tk.Label(
        bar,
        text=title,
        bg=BG_PAGE,
        fg=TEXT_PRIMARY,
        font=("Arial", 16, "bold"),
    ).grid(row=0, column=0, sticky="w", padx=(0, 18))
    return bar


def add_date_range_controls(bar, start_default, end_default, command, include_period=False):
    next_col = 1
    period_var = None
    if include_period:
        tk.Label(bar, text="Period:", bg=BG_PAGE, fg=TEXT_PRIMARY, font=("Arial", 16, "bold")).grid(row=0, column=next_col, sticky="e", padx=(0, 10))
        period_var = tk.StringVar(value="Custom")
        period_combo = ttk.Combobox(
            bar,
            textvariable=period_var,
            values=("Custom", "Day", "Week", "Month"),
            state="readonly",
            width=10,
            font=("Arial", 15),
        )
        period_combo.grid(row=0, column=next_col + 1, sticky="w", padx=(0, 20))
        next_col += 2

    start_label = tk.Label(bar, text="Start Date:", bg=BG_PAGE, fg=TEXT_PRIMARY, font=("Arial", 16, "bold"))
    start_label.grid(row=0, column=next_col, sticky="e", padx=(0, 10))
    start_entry, start_var = create_date_picker_entry(bar, start_default, width=13)
    start_entry.grid(row=0, column=next_col + 1, sticky="w", padx=(0, 20))

    end_label = tk.Label(bar, text="End Date:", bg=BG_PAGE, fg=TEXT_PRIMARY, font=("Arial", 16, "bold"))
    end_label.grid(row=0, column=next_col + 2, sticky="e", padx=(0, 10))
    end_entry, end_var = create_date_picker_entry(bar, end_default, width=13)
    end_entry.grid(row=0, column=next_col + 3, sticky="w", padx=(0, 20))

    generate_button = make_button(bar, "Generate Report", command)
    generate_button.grid(row=0, column=100, sticky="e")
    if include_period:
        custom_widgets = (start_label, start_entry, end_label, end_entry, generate_button)

        def sync_period_widgets(*_args):
            if period_var.get() == "Custom":
                for widget in custom_widgets:
                    widget.grid()
            else:
                for widget in custom_widgets:
                    widget.grid_remove()

        period_var.trace_add("write", sync_period_widgets)
        sync_period_widgets()
        return start_var, end_var, period_var
    return start_var, end_var


def make_button(parent, text, command, secondary=False, purple=False):
    bg = ACTION_PURPLE if purple else ACTION_SECONDARY if secondary else ACTION_BG
    active = "#7c3aed" if purple else "#15803d" if secondary else ACTION_ACTIVE
    return tk.Button(
        parent,
        text=text,
        command=command,
        bg=bg,
        fg="white",
        activebackground=active,
        activeforeground="white",
        font=("Arial", 14, "bold"),
        bd=2,
        relief="solid",
        highlightbackground="#000000",
        highlightcolor="#000000",
        highlightthickness=1,
        padx=16,
        pady=7,
        cursor="hand2",
    )


def create_report_area(parent, scrollable=False):
    area = tk.Frame(parent, bg=BG_PAGE)
    area.grid(row=1, column=0, sticky="nsew", pady=(SECTION_GAP, 0))
    area.grid_columnconfigure(0, weight=1)
    area.grid_rowconfigure(0, weight=1)
    if not scrollable:
        return area

    canvas = tk.Canvas(area, bg=BG_PAGE, highlightthickness=0)
    scroll = ttk.Scrollbar(area, orient="vertical", command=canvas.yview)
    content = tk.Frame(canvas, bg=BG_PAGE)
    content_window = canvas.create_window((0, 0), window=content, anchor="nw")

    canvas.configure(yscrollcommand=scroll.set)
    canvas.grid(row=0, column=0, sticky="nsew")
    scroll.grid(row=0, column=1, sticky="ns")

    def sync_scroll_region(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    def sync_content_width(event):
        canvas.itemconfigure(content_window, width=event.width)

    def on_mousewheel(event):
        canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    content.bind("<Configure>", sync_scroll_region)
    canvas.bind("<Configure>", sync_content_width)
    canvas.bind("<Enter>", lambda _event: canvas.bind_all("<MouseWheel>", on_mousewheel))
    canvas.bind("<Leave>", lambda _event: canvas.unbind_all("<MouseWheel>"))
    content.grid_columnconfigure(0, weight=1)
    return content


def clear_frame(frame):
    for widget in frame.winfo_children():
        widget.destroy()


def panel(parent, title=None, pad=True, bg=BG_CARD, border=LINE):
    outer = tk.Frame(
        parent,
        bg=bg,
        padx=PANEL_PAD if pad else 0,
        pady=PANEL_PAD if pad else 0,
        highlightthickness=2,
        highlightbackground=border,
        highlightcolor=border,
    )
    if title:
        tk.Label(
            outer,
            text=title,
            bg=bg,
            fg=REPORT_TITLE_FG,
            font=("Arial", 18, "bold"),
        ).pack(anchor="w", pady=(0, 8))
    return outer


def configure_tree_style(style_name, font=("Arial", 14), heading_font=("Arial", 15, "bold"), rowheight=40):
    style = ttk.Style()
    style.configure(
        style_name,
        font=font,
        rowheight=rowheight,
        background=BG_CARD,
        fieldbackground=BG_CARD,
        borderwidth=0,
    )
    style.configure(
        f"{style_name}.Heading",
        font=heading_font,
        background=TABLE_HEADER_BG,
        foreground=TABLE_HEADER_FG,
        relief="flat",
        padding=(6, 5),
    )
    style.map(style_name, background=[("selected", ACTION_BG)], foreground=[("selected", "#ffffff")])


def create_tree(parent, columns, headings, style_name, height=8, font=("Arial", 14), heading_font=("Arial", 15, "bold"), rowheight=40):
    configure_tree_style(style_name, font=font, heading_font=heading_font, rowheight=rowheight)
    tree = ttk.Treeview(parent, columns=columns, show="headings", style=style_name, height=height)
    vsb = ttk.Scrollbar(parent, orient="vertical", command=tree.yview)
    hsb = ttk.Scrollbar(parent, orient="horizontal", command=tree.xview)
    tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    tree.grid(row=0, column=0, sticky="nsew")
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    tk.Frame(parent, bg=BG_CARD, width=15, height=15).grid(row=1, column=1, sticky="nsew")
    parent.grid_columnconfigure(0, weight=1)
    parent.grid_rowconfigure(0, weight=1)

    for col, title, width, anchor in headings:
        tree.heading(col, text=title)
        tree.column(col, width=width, minwidth=max(55, int(width * 0.65)), anchor=anchor, stretch=True)

    tree.tag_configure("even", background=ACCENT)
    tree.tag_configure("odd", background="#ffffff")
    return tree


def insert_row(tree, values, index):
    tree.insert("", "end", values=values, tags=("even" if index % 2 == 0 else "odd",))


def render_empty(parent, text=NO_DATA_PERIOD_MESSAGE):
    empty = panel(parent, pad=True)
    empty.grid(row=0, column=0, sticky="ew")
    tk.Label(
        empty,
        text=text,
        bg=BG_CARD,
        fg=TEXT_MUTED,
        font=("Arial", 14, "italic"),
    ).pack(anchor="w")


def attach_auto_generate(root, command, *variables, period_var=None):
    state = {"after_id": None}

    def run():
        state["after_id"] = None
        try:
            if root.winfo_exists():
                if period_var is not None and period_var.get() == "Custom":
                    command(False)
                    return
                command()
        except tk.TclError:
            pass

    def schedule(*_args):
        if state["after_id"] is not None:
            try:
                root.after_cancel(state["after_id"])
            except tk.TclError:
                pass
        state["after_id"] = root.after(250, run)

    for variable in variables:
        if variable is not None:
            variable.trace_add("write", schedule)
    if period_var is not None:
        period_var.trace_add("write", schedule)
    return schedule


def summary_row(parent, label, value, highlight=False):
    bg = HIGHLIGHT_BG if highlight else BG_CARD
    fg = HIGHLIGHT_FG if highlight else TEXT_PRIMARY
    row = tk.Frame(parent, bg=bg, padx=8, pady=6)
    row.pack(fill="x", pady=2)
    tk.Label(row, text=label, bg=bg, fg=fg, font=("Arial", 13, "bold" if highlight else "normal")).pack(side="left", anchor="w")
    tk.Label(row, text=value, bg=bg, fg=fg, font=("Arial", 13, "bold"), anchor="e").pack(side="right")
    return row


def render_metric_strip(parent, metrics):
    strip = panel(parent, "Key Metrics", pad=True)
    metrics_grid = tk.Frame(strip, bg=BG_CARD)
    metrics_grid.pack(fill="x")
    if not metrics:
        return strip
    columns_per_row = 3 if len(metrics) > 3 else len(metrics)
    for col in range(columns_per_row):
        metrics_grid.grid_columnconfigure(col, weight=1, uniform="metric")
    for index, (label, value) in enumerate(metrics):
        row, col = divmod(index, columns_per_row)
        cell = tk.Frame(metrics_grid, bg=SUMMARY_BG, padx=10, pady=8)
        cell.grid(row=row, column=col, sticky="ew", padx=(0 if col == 0 else 6, 0), pady=(0 if row == 0 else 6, 0))
        tk.Label(cell, text=label.upper(), bg=SUMMARY_BG, fg=TEXT_MUTED, font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(cell, text=value, bg=SUMMARY_BG, fg=TEXT_PRIMARY, font=("Arial", 18, "bold")).pack(anchor="w")
    return strip


def center_popup(window, width=560, height=320, parent=None):
    window.update_idletasks()
    if parent and parent.winfo_exists():
        parent.update_idletasks()
        x_pos = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y_pos = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    else:
        x_pos = (window.winfo_screenwidth() // 2) - (width // 2)
        y_pos = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x_pos}+{y_pos}")


def show_report_popup(parent, title, message, accent_color):
    if parent is None or not parent.winfo_exists():
        if accent_color == SUCCESS_GREEN:
            messagebox.showinfo(title, message)
        else:
            messagebox.showerror(title, message)
        return

    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg=BG_CARD)
    popup.resizable(False, False)

    tk.Frame(popup, bg=accent_color, height=12).pack(fill="x")

    content = tk.Frame(popup, bg=BG_CARD, padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text=title,
        bg=BG_CARD,
        fg=accent_color,
        font=("Arial", 26, "bold"),
    ).pack(pady=(0, 14))
    tk.Label(
        content,
        text=message,
        bg=BG_CARD,
        fg="#111827",
        font=("Arial", 15),
        wraplength=470,
        justify="center",
    ).pack(pady=(0, 28))

    def close_popup():
        popup.destroy()

    ok_btn = tk.Button(
        content,
        text="OK",
        command=close_popup,
        bg=accent_color,
        fg="white",
        activebackground=accent_color,
        activeforeground="white",
        font=("Arial", 14, "bold"),
        relief="flat",
        width=14,
        pady=8,
    )
    ok_btn.pack()
    ok_btn.focus_set()

    popup.bind("<Return>", lambda _event: close_popup())
    popup.bind("<Escape>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    center_popup(popup, 590, 330, parent)
    parent.wait_window(popup)


def show_pdf_success_message(parent, report_name, file_path):
    message = (
        f"The {report_name} PDF has been exported successfully.\n\n"
        f"Saved to:\n{file_path}"
    )
    show_report_popup(parent, "PDF Export Successful", message, SUCCESS_GREEN)


def show_pdf_error_message(parent, message):
    show_report_popup(parent, "PDF Export Failed", message, ERROR_RED)


def fmt_short_date(ts_value):
    text = str(ts_value or "")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(text[:19], fmt)
            return dt.strftime("%m-%d-%y")
        except ValueError:
            continue
    return text[:10]


def _insert_financial_sales_rows(tree, sales_transactions):
    for idx, (ts, item_name, qty, jasp_unit_price, purchased_unit_price, jasp_total) in enumerate(sales_transactions):
        qty_val = float(qty or 0)
        purchased_unit = float(purchased_unit_price or 0)
        jasp_unit = float(jasp_unit_price or 0)
        jasp_total_val = float(jasp_total or 0)
        purchased_total = purchased_unit * qty_val
        marked_up = jasp_total_val - purchased_total
        insert_row(
            tree,
            (
                fmt_short_date(ts),
                str(item_name or "-"),
                "pc",
                money(purchased_unit),
                money(jasp_unit),
                f"{qty_val:,.2f}",
                money(purchased_total),
                money(jasp_total_val),
                money(marked_up),
            ),
            idx,
        )


def _insert_financial_expense_rows(tree, expense_summary_rows):
    for idx, (expense_date, expense_name, total_amount, remarks) in enumerate(expense_summary_rows):
        insert_row(
            tree,
            (
                fmt_short_date(expense_date),
                str(expense_name or "-"),
                money(total_amount),
                str(remarks or ""),
            ),
            idx,
        )


def open_financial_tables_fullscreen(parent, data):
    expanded = tk.Toplevel(parent)
    expanded.title("Financial Summary Tables")
    expanded.configure(bg=BG_PAGE)
    expanded.transient(parent)
    try:
        expanded.state("zoomed")
    except tk.TclError:
        expanded.geometry("1280x720")

    header = tk.Frame(expanded, bg=REPORTS_HEADER_BG, padx=14, pady=10, highlightthickness=1, highlightbackground=DASHBOARD_HEADER_BORDER)
    header.pack(fill="x", padx=18, pady=(14, 8))
    tk.Label(
        header,
        text="FINANCIAL SUMMARY TABLES",
        bg=REPORTS_HEADER_BG,
        fg=DASHBOARD_HEADER_FG,
        font=("Arial", 22, "bold"),
    ).pack(side="left", padx=(4, 16))
    tk.Label(
        header,
        text=f"{data['start_date']} to {data['end_date']}",
        bg=REPORTS_HEADER_BG,
        fg=DASHBOARD_HEADER_SUBTLE_FG,
        font=("Arial", 13, "bold"),
    ).pack(side="left")
    tk.Button(
        header,
        text="Close",
        command=expanded.destroy,
        bg=ACTION_BG,
        fg="white",
        activebackground=ACTION_ACTIVE,
        activeforeground="white",
        font=("Arial", 13, "bold"),
        bd=2,
        relief="solid",
        padx=18,
        pady=7,
        cursor="hand2",
    ).pack(side="right")

    body = tk.Frame(expanded, bg=BG_PAGE)
    body.pack(fill="both", expand=True, padx=18, pady=(0, 18))
    body.grid_columnconfigure(0, weight=1)
    body.grid_rowconfigure(0, weight=3)
    body.grid_rowconfigure(1, weight=2)

    sales_panel = panel(body, "Items Sold")
    sales_panel.grid(row=0, column=0, sticky="nsew", pady=(0, SECTION_GAP))
    sales_wrap = tk.Frame(sales_panel, bg=BG_CARD)
    sales_wrap.pack(fill="both", expand=True)
    sales_columns = ("date", "product", "unit", "purchased", "jasp", "qty", "total_purchased", "total_jasp", "markup")
    sales_headings = [
        ("date", "DATE", 110, "center"),
        ("product", "PRODUCT", 260, "w"),
        ("unit", "UNIT", 70, "center"),
        ("purchased", "PURCHASED", 130, "e"),
        ("jasp", "JASP", 120, "e"),
        ("qty", "QTY", 95, "e"),
        ("total_purchased", "TOTAL PURCHASED", 170, "e"),
        ("total_jasp", "TOTAL JASP", 150, "e"),
        ("markup", "MARKUP", 140, "e"),
    ]
    sales_tree = create_tree(
        sales_wrap,
        sales_columns,
        sales_headings,
        "FinancialDataFullscreen.Treeview",
        height=14,
        font=("Arial", 13),
        heading_font=("Arial", 14, "bold"),
        rowheight=34,
    )
    _insert_financial_sales_rows(sales_tree, data.get("sales_transactions", []))

    expense_panel = panel(body, "Material / Operating Expenses")
    expense_panel.grid(row=1, column=0, sticky="nsew")
    expense_wrap = tk.Frame(expense_panel, bg=BG_CARD)
    expense_wrap.pack(fill="both", expand=True)
    exp_columns = ("date", "expense_name", "total_expense", "remarks")
    exp_headings = [
        ("date", "DATE", 130, "center"),
        ("expense_name", "EXPENSE NAME", 300, "w"),
        ("total_expense", "TOTAL", 160, "e"),
        ("remarks", "REMARKS", 720, "w"),
    ]
    exp_tree = create_tree(
        expense_wrap,
        exp_columns,
        exp_headings,
        "FinancialExpenseFullscreen.Treeview",
        height=9,
        font=("Arial", 13),
        heading_font=("Arial", 14, "bold"),
        rowheight=34,
    )
    _insert_financial_expense_rows(exp_tree, data.get("expense_summary_rows", []))

    footer = tk.Frame(expanded, bg=BG_PAGE)
    footer.pack(fill="x", padx=18, pady=(0, 14))
    tk.Label(
        footer,
        text="CHB material expenses are based on production records in the selected period.",
        bg=BG_PAGE,
        fg=TEXT_MUTED,
        font=("Arial", 12, "italic"),
    ).pack(side="left")
    tk.Label(
        footer,
        text=f"Expense Sub-Total: {money(data['material_expenses'])}",
        bg=SUMMARY_BG,
        fg=TEXT_PRIMARY,
        font=("Arial", 14, "bold"),
        padx=12,
        pady=6,
    ).pack(side="right")


def open_reports(parent=None):
    reports_window = tk.Toplevel(parent) if parent is not None else tk.Toplevel()
    reports_window.title("Reports & Analytics")
    reports_window.state("zoomed")
    reports_window.configure(bg=BG_PAGE)
    reports_window.option_add("*TCombobox*Listbox.font", ("Arial", 18))
    if parent is not None:
        reports_window.transient(parent)
    reports_window.protocol("WM_DELETE_WINDOW", lambda: close_window_and_focus_parent(reports_window, parent))

    init_database()
    refresh_callbacks = {}
    notebook = None

    def refresh_current_tab():
        if notebook is None:
            return
        callback = refresh_callbacks.get(notebook.tab(notebook.select(), "text"))
        if callback:
            callback()

    header = tk.Frame(
        reports_window,
        bg=REPORTS_HEADER_BG,
        padx=14,
        pady=10,
        highlightthickness=1,
        highlightbackground=DASHBOARD_HEADER_BORDER,
    )
    header.pack(fill="x", padx=30, pady=(15, 8))

    title_frame = tk.Frame(header, bg=REPORTS_HEADER_BG)
    title_frame.pack(side="left")
    add_header_logo(title_frame, REPORTS_HEADER_BG, size=52)

    tk.Label(
        title_frame,
        text="REPORTS & ANALYTICS",
        bg=REPORTS_HEADER_BG,
        fg=DASHBOARD_HEADER_FG,
        font=("Arial", 22, "bold"),
        padx=12,
        pady=4,
    ).pack(side="left")
    tk.Label(
        title_frame,
        text="Financials | Sales | Production | Inventory | Delivery",
        bg=REPORTS_HEADER_BG,
        fg=DASHBOARD_HEADER_SUBTLE_FG,
        font=("Arial", 12, "bold"),
    ).pack(side="left", padx=(18, 0))

    header_button_options = {
        "width": 12,
        "font": ("Arial", 13, "bold"),
        "bd": 2,
        "relief": "solid",
        "padx": 10,
        "pady": 7,
    }

    tk.Button(
        header,
        text="← Back",
        bg=ACTION_BG,
        fg="white",
        command=lambda: close_window_and_focus_parent(reports_window, parent),
        **header_button_options,
    ).pack(side="right", padx=(6, 0))
    tk.Button(
        header,
        text="🔄 Refresh",
        bg=ACTION_SECONDARY,
        fg="white",
        command=refresh_current_tab,
        **header_button_options,
    ).pack(side="right", padx=(6, 0))

    content = tk.Frame(reports_window, bg=BG_PAGE)
    content.pack(fill="both", expand=True, padx=20, pady=10)

    notebook_style = ttk.Style()
    notebook_style.configure("Reports.TNotebook", background=BG_PAGE, borderwidth=0)
    notebook_style.configure("Reports.TNotebook.Tab", font=("Arial", 12, "bold"), padding=(14, 8))
    notebook_style.map(
        "Reports.TNotebook.Tab",
        background=[("selected", BG_CARD)],
        foreground=[("selected", HEADER_BG)],
    )

    notebook = ttk.Notebook(content, style="Reports.TNotebook")
    notebook.pack(fill="both", expand=True)

    fin_frame = tk.Frame(notebook, bg=BG_PAGE)
    notebook.add(fin_frame, text="Financial Summary")
    refresh_callbacks["Financial Summary"] = _build_financial_summary_tab(fin_frame)

    sales_frame = tk.Frame(notebook, bg=BG_PAGE)
    notebook.add(sales_frame, text="Sales Report")
    refresh_callbacks["Sales Report"] = _build_sales_report_tab(sales_frame)

    chb_frame = tk.Frame(notebook, bg=BG_PAGE)
    notebook.add(chb_frame, text="CHB Production")
    refresh_callbacks["CHB Production"] = _build_chb_production_tab(chb_frame)

    inventory_frame = tk.Frame(notebook, bg=BG_PAGE)
    notebook.add(inventory_frame, text="Inventory Status")
    refresh_callbacks["Inventory Status"] = _build_inventory_status_tab(inventory_frame)

    delivery_frame = tk.Frame(notebook, bg=BG_PAGE)
    notebook.add(delivery_frame, text="Delivery Report")
    refresh_callbacks["Delivery Report"] = _build_delivery_report_tab(delivery_frame)

    notebook.bind("<<NotebookTabChanged>>", lambda _event: refresh_current_tab())
    reports_window.after(150, refresh_current_tab)


def _build_financial_summary_tab(parent):
    root = create_tab_root(parent)
    report_container = create_report_area(root, scrollable=True)

    def clear_report_area():
        clear_frame(report_container)

    def generate_report(force=False):
        if period_var.get() == "Custom" and not force:
            clear_frame(report_container)
            render_empty(report_container, CUSTOM_PERIOD_PROMPT)
            return
        start, end, range_error = get_report_date_range(
            period_var.get(),
            reference_date=end_var.get().strip(),
            custom_start=start_var.get().strip(),
            custom_end=end_var.get().strip(),
        )
        if range_error:
            messagebox.showerror("Error", range_error)
            return
        data, error = generate_financial_summary(start, end)

        if error:
            messagebox.showerror("Error", error)
            return

        clear_report_area()
        if not data.get("has_period_data"):
            render_empty(report_container)
            return

        report_container.grid_columnconfigure(0, weight=4)
        report_container.grid_columnconfigure(1, weight=1, minsize=300)
        report_container.grid_rowconfigure(2, weight=3, minsize=245)
        report_container.grid_rowconfigure(3, weight=2, minsize=210)

        title_bar = panel(report_container, pad=True)
        title_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SECTION_GAP))
        tk.Label(title_bar, text="Financial Summary Report", bg=BG_CARD, fg=HEADER_BG, font=("Arial", 18, "bold")).pack(side="left")
        tk.Label(title_bar, text=f"{start} to {end}", bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 12, "bold")).pack(side="right")
        make_button(
            title_bar,
            "Full Screen Display",
            lambda: open_financial_tables_fullscreen(report_container.winfo_toplevel(), data),
            secondary=True,
        ).pack(side="right", padx=(0, 12))

        metrics = render_metric_strip(
            report_container,
            [
                ("Total Sales / Gross Revenue", money(data["total_sales"])),
                ("Cash On Hand", money(data["cash_on_hand"])),
                ("Material / Operating Expenses", money(data["material_expenses"])),
                ("Worker Payouts", money(data["worker_payouts"])),
                ("Total Expenses", money(data["total_expenses"])),
                ("Net Profit", money(data["total_revenue"])),
            ],
        )
        metrics.grid(row=1, column=0, sticky="ew", pady=(0, SECTION_GAP), padx=(0, SECTION_GAP))

        sales_panel = panel(report_container, "Items Sold")
        sales_panel.grid(row=2, column=0, sticky="nsew", pady=(0, SECTION_GAP), padx=(0, SECTION_GAP))
        sales_wrap = tk.Frame(sales_panel, bg=BG_CARD)
        sales_wrap.pack(fill="both", expand=True)
        sales_columns = ("date", "product", "unit", "purchased", "jasp", "qty", "total_purchased", "total_jasp", "markup")
        sales_headings = [
            ("date", "DATE", 78, "center"),
            ("product", "PRODUCT", 160, "w"),
            ("unit", "UNIT", 48, "center"),
            ("purchased", "PURCHASED", 92, "e"),
            ("jasp", "JASP", 82, "e"),
            ("qty", "QTY", 68, "e"),
            ("total_purchased", "TOTAL PURCHASED", 116, "e"),
            ("total_jasp", "TOTAL JASP", 98, "e"),
            ("markup", "MARKUP", 90, "e"),
        ]
        sales_tree = create_tree(
            sales_wrap,
            sales_columns,
            sales_headings,
            "FinancialData.Treeview",
            height=8,
            font=("Arial", 12),
            heading_font=("Arial", 13, "bold"),
            rowheight=30,
        )
        _insert_financial_sales_rows(sales_tree, data.get("sales_transactions", []))

        expense_panel = panel(report_container, "Material / Operating Expenses")
        expense_panel.grid(row=3, column=0, sticky="nsew", padx=(0, SECTION_GAP))
        exp_wrap = tk.Frame(expense_panel, bg=BG_CARD)
        exp_wrap.pack(fill="both", expand=True)
        exp_columns = ("date", "expense_name", "total_expense", "remarks")
        exp_headings = [
            ("date", "DATE", 80, "center"),
            ("expense_name", "EXPENSE NAME", 250, "w"),
            ("total_expense", "TOTAL", 110, "e"),
            ("remarks", "REMARKS", 165, "w"),
        ]
        exp_tree = create_tree(
            exp_wrap,
            exp_columns,
            exp_headings,
            "FinancialExpense.Treeview",
            height=4,
            font=("Arial", 12),
            heading_font=("Arial", 13, "bold"),
            rowheight=30,
        )
        _insert_financial_expense_rows(exp_tree, data.get("expense_summary_rows", []))

        subtotal = tk.Frame(expense_panel, bg=BG_CARD)
        subtotal.pack(fill="x", pady=(4, 0))
        tk.Label(subtotal, text="Expense Sub-Total", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 14, "bold")).pack(side="left")
        tk.Label(subtotal, text=money(data["material_expenses"]), bg=SUMMARY_BG, fg=TEXT_PRIMARY, font=("Arial", 14, "bold"), padx=8, pady=4).pack(side="right")
        tk.Label(
            expense_panel,
            text="CHB material expenses are based on production records in the selected period.",
            bg=BG_CARD,
            fg=TEXT_MUTED,
            font=("Arial", 11, "italic"),
        ).pack(anchor="w", pady=(4, 0))

        sidebar = panel(report_container, "Financial Summary")
        sidebar.grid(row=1, column=1, rowspan=3, sticky="nsew")
        for label, value, highlight in [
            ("Total Sales / Gross Revenue", money(data["total_sales"]), False),
            ("Cash On Hand", money(data["cash_on_hand"]), False),
            ("Material / Operating Expenses", f"-{money(data['material_expenses'])}", False),
            ("Worker Payouts", f"-{money(data['worker_payouts'])}", False),
            ("Total Expenses", f"-{money(data['total_expenses'])}", False),
            ("Net Profit", money(data["total_revenue"]), True),
        ]:
            summary_row(sidebar, label, value, highlight)

        total = tk.Frame(sidebar, bg=HIGHLIGHT_BG, padx=8, pady=7)
        total.pack(fill="x", pady=(8, 6))
        tk.Label(total, text="NET PROFIT", bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG, font=("Arial", 12, "bold")).pack(anchor="w")
        tk.Label(total, text=money(data["total_revenue"]), bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG, font=("Arial", 18, "bold")).pack(anchor="w")
        make_button(sidebar, "Export to PDF", lambda: _handle_export("Financial Summary", data, report_container.winfo_toplevel())).pack(fill="x")

    bar = create_filter_bar(root, "Financial Summary")
    start_var, end_var, period_var = add_date_range_controls(
        bar,
        (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        datetime.now().strftime("%Y-%m-%d"),
        lambda: generate_report(True),
        include_period=True,
    )
    attach_auto_generate(root, generate_report, period_var=period_var)
    return generate_report


def _build_sales_report_tab(parent):
    root = create_tab_root(parent)
    report_container = create_report_area(root)

    def generate_report(force=False):
        if period_var.get() == "Custom" and not force:
            clear_frame(report_container)
            render_empty(report_container, CUSTOM_PERIOD_PROMPT)
            return
        start, end, range_error = get_report_date_range(
            period_var.get(),
            reference_date=end_var.get().strip(),
            custom_start=start_var.get().strip(),
            custom_end=end_var.get().strip(),
        )
        if range_error:
            messagebox.showerror("Error", range_error)
            return

        data, error = generate_sales_report(start, end)
        if error:
            messagebox.showerror("Error", error)
            return

        clear_frame(report_container)
        if not data.get("has_period_data"):
            render_empty(report_container)
            return

        report_container.grid_columnconfigure(0, weight=4)
        report_container.grid_columnconfigure(1, weight=1, minsize=285)
        report_container.grid_rowconfigure(1, weight=1)

        title_bar = panel(report_container, pad=True)
        title_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SECTION_GAP))
        tk.Label(title_bar, text="Sales Report", bg=BG_CARD, fg=HEADER_BG, font=("Arial", 18, "bold")).pack(side="left")
        tk.Label(title_bar, text=f"{data['start_date']} to {data['end_date']}", bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 12, "bold")).pack(side="right")

        table_panel = panel(report_container, "Completed Transactions")
        table_panel.grid(row=1, column=0, sticky="nsew", padx=(0, SECTION_GAP))
        wrap = tk.Frame(table_panel, bg=BG_CARD)
        wrap.pack(fill="both", expand=True)
        columns = ("date", "txn", "items", "qty", "total", "payment", "change")
        headings = [
            ("date", "DATE", 150, "w"),
            ("txn", "TRANSACTION ID", 145, "w"),
            ("items", "ITEMS SOLD", 240, "w"),
            ("qty", "QUANTITIES", 120, "w"),
            ("total", "TOTAL AMOUNT", 125, "e"),
            ("payment", "PAYMENT RECEIVED", 145, "e"),
            ("change", "CHANGE", 105, "e"),
        ]
        tree = create_tree(
            wrap,
            columns,
            headings,
            "SalesReport.Treeview",
            height=13,
            font=("Arial", 12),
            heading_font=("Arial", 12, "bold"),
            rowheight=34,
        )
        for idx, row in enumerate(data.get("transactions", [])):
            insert_row(
                tree,
                (
                    str(row["transaction_date"])[:19],
                    row["transaction_id"],
                    row["items_sold"],
                    row["quantities"],
                    money(row["total_amount"]),
                    money(row["payment_received"]),
                    money(row["change_amount"]),
                ),
                idx,
            )

        sidebar = panel(report_container, "Summary")
        sidebar.grid(row=1, column=1, sticky="nsew")
        summary_row(sidebar, "Transactions", f"{data['transaction_count']:,}")
        summary_row(sidebar, "Start Date", data["start_date"])
        summary_row(sidebar, "End Date", data["end_date"])
        total = tk.Frame(sidebar, bg=HIGHLIGHT_BG, padx=8, pady=7)
        total.pack(fill="x", pady=(8, 6))
        tk.Label(total, text="TOTAL SALES", bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG, font=("Arial", 12, "bold")).pack(anchor="w")
        tk.Label(total, text=money(data["total_sales"]), bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG, font=("Arial", 18, "bold")).pack(anchor="w")
        make_button(sidebar, "Export to PDF", lambda: _handle_export("Sales Report", data, report_container.winfo_toplevel())).pack(fill="x")

    bar = create_filter_bar(root, "Sales Report")
    start_var, end_var, period_var = add_date_range_controls(
        bar,
        (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        datetime.now().strftime("%Y-%m-%d"),
        lambda: generate_report(True),
        include_period=True,
    )
    attach_auto_generate(root, generate_report, period_var=period_var)
    return generate_report


def _build_weekly_sales_tab(parent):
    root = create_tab_root(parent)
    report_container = create_report_area(root)

    def clear_report_area():
        clear_frame(report_container)

    def generate_report():
        end = end_var.get().strip()
        data, error = generate_weekly_sales(end)

        if error:
            messagebox.showerror("Error", error)
            return

        clear_report_area()
        if not data.get("has_period_data"):
            render_empty(report_container)
            return

        report_container.grid_columnconfigure(0, weight=4)
        report_container.grid_columnconfigure(1, weight=1, minsize=285)
        report_container.grid_rowconfigure(1, weight=1)
        total_revenue = sum(row[2] for row in data["daily_data"])

        title_bar = panel(report_container, pad=True)
        title_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SECTION_GAP))
        tk.Label(title_bar, text="Weekly Sales Statistics", bg=BG_CARD, fg=HEADER_BG, font=("Arial", 18, "bold")).pack(side="left")
        tk.Label(title_bar, text=f"{data['start_date']} to {data['end_date']}", bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 12, "bold")).pack(side="right")

        table_panel = panel(report_container, "Daily Revenue Breakdown")
        table_panel.grid(row=1, column=0, sticky="nsew", padx=(0, SECTION_GAP))
        wrap = tk.Frame(table_panel, bg=BG_CARD)
        wrap.pack(fill="both", expand=True)
        columns = ("day", "date", "revenue")
        headings = [
            ("day", "DAY", 180, "w"),
            ("date", "DATE", 140, "center"),
            ("revenue", "REVENUE", 160, "e"),
        ]
        tree = create_tree(wrap, columns, headings, "WeeklyData.Treeview", height=12)
        for idx, (day, date, revenue) in enumerate(data["daily_data"]):
            insert_row(tree, (day, date, money(revenue)), idx)

        sidebar = panel(report_container, "Summary")
        sidebar.grid(row=1, column=1, sticky="nsew")
        summary_row(sidebar, "Days Counted", str(len(data["daily_data"])))
        summary_row(sidebar, "Start Date", data["start_date"])
        summary_row(sidebar, "End Date", data["end_date"])
        total = tk.Frame(sidebar, bg=HIGHLIGHT_BG, padx=8, pady=7)
        total.pack(fill="x", pady=(8, 6))
        tk.Label(total, text="TOTAL WEEKLY REVENUE", bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG, font=("Arial", 12, "bold")).pack(anchor="w")
        tk.Label(total, text=money(total_revenue), bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG, font=("Arial", 18, "bold")).pack(anchor="w")
        make_button(sidebar, "Export to PDF", lambda: _handle_export("Weekly Sales Statistics", data, report_container.winfo_toplevel())).pack(fill="x")

    bar = create_filter_bar(root, "Weekly Sales")
    tk.Label(bar, text="Week Ending:", bg=BG_PAGE, fg=TEXT_PRIMARY, font=("Arial", 16, "bold")).grid(row=0, column=1, sticky="e", padx=(0, 10))
    end_entry, end_var = create_date_picker_entry(bar, datetime.now().strftime("%Y-%m-%d"), width=13)
    end_entry.grid(row=0, column=2, sticky="w", padx=(0, 20))
    make_button(bar, "Generate Report", generate_report).grid(row=0, column=100, sticky="e")
    attach_auto_generate(root, generate_report, end_var)
    return generate_report


def _build_chb_production_tab(parent):
    root = create_tab_root(parent)
    report_container = create_report_area(root)

    def clear_report_area():
        clear_frame(report_container)

    def generate_report(force=False):
        if period_var.get() == "Custom" and not force:
            clear_report_area()
            render_empty(report_container, CUSTOM_PERIOD_PROMPT)
            return
        start, end, range_error = get_report_date_range(
            period_var.get(),
            reference_date=end_var.get().strip(),
            custom_start=start_var.get().strip(),
            custom_end=end_var.get().strip(),
        )
        if range_error:
            messagebox.showerror("Error", range_error)
            return
        data, error = generate_chb_production(start, end)

        if error:
            messagebox.showerror("Error", error)
            return

        clear_report_area()
        if not data.get("has_period_data"):
            render_empty(report_container)
            return

        report_container.grid_columnconfigure(0, weight=4)
        report_container.grid_columnconfigure(1, weight=1, minsize=285)
        report_container.grid_rowconfigure(1, weight=1)

        title_bar = panel(report_container, pad=True)
        title_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SECTION_GAP))
        tk.Label(title_bar, text="CHB Production Report", bg=BG_CARD, fg=HEADER_BG, font=("Arial", 18, "bold")).pack(side="left")
        tk.Label(title_bar, text=f"{start} to {end}", bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 12, "bold")).pack(side="right")

        details_panel = panel(report_container, "Production Details")
        details_panel.grid(row=1, column=0, sticky="nsew", padx=(0, SECTION_GAP))
        wrap = tk.Frame(details_panel, bg=BG_CARD)
        wrap.pack(fill="both", expand=True)
        columns = ("production_date", "worker", "cement", "fine_sand", "blocks", "pay")
        headings = [
            ("production_date", "PRODUCTION DATE", 135, "center"),
            ("worker", "WORKER NAME", 180, "w"),
            ("cement", "CEMENT BAGS", 115, "e"),
            ("fine_sand", "FINE SAND", 115, "e"),
            ("blocks", "TOTAL BLOCKS", 130, "e"),
            ("pay", "WORKER PAY", 125, "e"),
        ]
        tree = create_tree(
            wrap,
            columns,
            headings,
            "CHBData.Treeview",
            height=13,
            font=("Arial", 12),
            heading_font=("Arial", 12, "bold"),
            rowheight=34,
        )
        for idx, row in enumerate(data.get("entries", [])):
            insert_row(
                tree,
                (
                    str(row.get("production_date") or "")[:10],
                    str(row.get("worker_name") or "N/A"),
                    quantity(row.get("cement_bags")),
                    quantity(row.get("fine_sand")),
                    f"{int(float(row.get('total_blocks') or 0)):,}",
                    money(row.get("worker_pay")),
                ),
                idx,
            )

        sidebar = panel(report_container, "Production Summary")
        sidebar.grid(row=1, column=1, sticky="nsew")
        summary_row(sidebar, "Total Cement Bags", quantity(data["total_cement"]))
        summary_row(sidebar, "Total Fine Sand", quantity(data["total_fine_sand"]))
        summary_row(sidebar, "Total Blocks", f"{data['total_blocks']:,} pcs")
        summary_row(sidebar, "Worker Pay", money(data["total_worker_pay"]), True)
        make_button(sidebar, "Export to PDF", lambda: _handle_export("CHB Production", data, report_container.winfo_toplevel())).pack(fill="x", pady=(8, 0))

    bar = create_filter_bar(root, "CHB Production")
    start_var, end_var, period_var = add_date_range_controls(
        bar,
        (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        datetime.now().strftime("%Y-%m-%d"),
        lambda: generate_report(True),
        include_period=True,
    )
    attach_auto_generate(root, generate_report, period_var=period_var)
    return generate_report


def _build_inventory_status_tab(parent):
    root = create_tab_root(parent)
    report_container = create_report_area(root)

    def clear_report_area():
        clear_frame(report_container)

    def generate_report():
        data, error = generate_inventory_status()

        if error:
            messagebox.showerror("Error", error)
            return

        clear_report_area()
        if not data.get("has_inventory_data"):
            render_empty(report_container)
            return

        report_container.grid_columnconfigure(0, weight=4)
        report_container.grid_columnconfigure(1, weight=1, minsize=300)
        report_container.grid_rowconfigure(1, weight=1)

        title_bar = panel(report_container, pad=True)
        title_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SECTION_GAP))
        tk.Label(title_bar, text="Inventory Status Report", bg=BG_CARD, fg=HEADER_BG, font=("Arial", 18, "bold")).pack(side="left")
        tk.Label(title_bar, text=f"As of {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 12, "bold")).pack(side="right")

        all_items_panel = panel(report_container, "All Inventory Items")
        all_items_panel.grid(row=1, column=0, sticky="nsew", padx=(0, SECTION_GAP))
        wrap = tk.Frame(all_items_panel, bg=BG_CARD)
        wrap.pack(fill="both", expand=True)
        columns = ("name", "unit", "qty", "status")
        headings = [
            ("name", "PRODUCT NAME", 310, "w"),
            ("unit", "UNIT", 110, "center"),
            ("qty", "CURRENT STOCK", 145, "e"),
            ("status", "STOCK STATUS", 160, "center"),
        ]
        tree = create_tree(wrap, columns, headings, "InventoryReport.Treeview", height=14)
        for idx, row in enumerate(data.get("all_items", [])):
            insert_row(
                tree,
                (
                    str(row.get("product_name") or "N/A"),
                    str(row.get("unit") or "-"),
                    quantity(row.get("current_stock")),
                    row.get("stock_status") or "Normal Stock",
                ),
                idx,
            )

        sidebar = panel(report_container, "Snapshot")
        sidebar.grid(row=1, column=1, sticky="nsew")
        summary_row(sidebar, "Total Items", f"{data.get('total_items', 0):,}")
        summary_row(sidebar, "Low Stock", f"{len(data.get('low_stock', [])):,}", bool(data.get("low_stock")))

        low_panel = tk.Frame(sidebar, bg="#fff8e1", padx=5, pady=5, highlightthickness=1, highlightbackground="#e7c76a")
        low_panel.pack(fill="both", expand=True, pady=(8, 6))
        tk.Label(low_panel, text="Low Stock Alerts", bg="#fff8e1", fg="#7c4a03", font=("Arial", 9, "bold")).pack(anchor="w", pady=(0, 4))
        if data.get("low_stock"):
            low_wrap = tk.Frame(low_panel, bg="#fff8e1")
            low_wrap.pack(fill="both", expand=True)
            columns = ("name", "qty")
            headings = [
                ("name", "ITEM", 185, "w"),
                ("qty", "QTY", 70, "e"),
            ]
            low_tree = create_tree(low_wrap, columns, headings, "LowStock.Treeview", height=7)
            for idx, row in enumerate(data.get("low_stock", [])):
                insert_row(
                    low_tree,
                    (
                        str(row.get("product_name") or "N/A"),
                        quantity(row.get("current_stock")),
                    ),
                    idx,
                )
        else:
            tk.Label(low_panel, text="No low stock alerts.", bg="#fff8e1", fg="#7c4a03", font=("Arial", 9, "italic")).pack(anchor="w")

        make_button(sidebar, "Export to PDF", lambda: _handle_export("Inventory Status", data, report_container.winfo_toplevel())).pack(fill="x")

    bar = create_filter_bar(root, "Inventory Status")
    make_button(bar, "Generate Report", generate_report).grid(row=0, column=100, sticky="e")
    return generate_report


def _build_delivery_report_tab(parent):
    root = create_tab_root(parent)
    report_container = create_report_area(root)

    def clear_report_area():
        clear_frame(report_container)

    def generate_report(force=False):
        if period_var.get() == "Custom" and not force:
            clear_report_area()
            render_empty(report_container, CUSTOM_PERIOD_PROMPT)
            return
        start, end, range_error = get_report_date_range(
            period_var.get(),
            reference_date=end_var.get().strip(),
            custom_start=start_var.get().strip(),
            custom_end=end_var.get().strip(),
        )
        if range_error:
            messagebox.showerror("Error", range_error)
            return

        data, error = generate_delivery_report(start, end)
        if error:
            messagebox.showerror("Error", error)
            return

        clear_report_area()
        if not data.get("tables_available", True):
            render_empty(report_container, data.get("message", "No delivery records are available in the current database."))
            return
        if not data.get("has_period_data"):
            render_empty(report_container)
            return

        report_container.grid_columnconfigure(0, weight=4)
        report_container.grid_columnconfigure(1, weight=1, minsize=300)
        report_container.grid_rowconfigure(1, weight=1)

        title_bar = panel(report_container, pad=True)
        title_bar.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, SECTION_GAP))
        tk.Label(title_bar, text="Delivery Report", bg=BG_CARD, fg=HEADER_BG, font=("Arial", 18, "bold")).pack(side="left")
        tk.Label(title_bar, text=f"{data['start_date']} to {data['end_date']}", bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 12, "bold")).pack(side="right")

        table_panel = panel(report_container, "Delivery Records")
        table_panel.grid(row=1, column=0, sticky="nsew", padx=(0, SECTION_GAP))
        wrap = tk.Frame(table_panel, bg=BG_CARD)
        wrap.pack(fill="both", expand=True)
        columns = ("date", "type", "name", "item", "qty", "address", "driver", "amount")
        headings = [
            ("date", "DATE", 105, "center"),
            ("type", "TYPE", 95, "center"),
            ("name", "CUSTOMER / WORKER", 165, "w"),
            ("item", "ITEM", 160, "w"),
            ("qty", "QTY", 90, "e"),
            ("address", "ADDRESS", 265, "w"),
            ("driver", "DRIVER / HELPER", 180, "w"),
            ("amount", "FEE / AMOUNT", 125, "e"),
        ]
        tree = create_tree(
            wrap,
            columns,
            headings,
            "DeliveryReport.Treeview",
            height=13,
            font=("Arial", 11),
            heading_font=("Arial", 11, "bold"),
            rowheight=34,
        )
        for idx, row in enumerate(data.get("rows", [])):
            qty_text = quantity(row.get("quantity"))
            unit_text = str(row.get("unit") or "").strip()
            if unit_text:
                qty_text = f"{qty_text} {unit_text}"
            insert_row(
                tree,
                (
                    row.get("report_date") or "-",
                    row.get("delivery_type") or "-",
                    row.get("customer_name") or "-",
                    row.get("item_name") or "-",
                    qty_text,
                    row.get("address") or "-",
                    row.get("driver_helper") or "-",
                    money(row.get("amount")),
                ),
                idx,
            )

        sidebar = panel(report_container, "Delivery Summary")
        sidebar.grid(row=1, column=1, sticky="nsew")
        summary_row(sidebar, "Total Records", f"{data.get('record_count', 0):,}")
        summary_row(sidebar, "CHB Deliveries", f"{data.get('chb_count', 0):,}")
        summary_row(sidebar, "Other Item Deliveries", f"{data.get('other_count', 0):,}")
        summary_row(sidebar, "Total Quantity", quantity(data.get("total_quantity", 0)))
        summary_row(sidebar, "Delivery Fees / Amount", money(data.get("total_amount", 0)), True)
        if data.get("total_worker_pay", 0):
            summary_row(sidebar, "CHB Worker Pay", money(data.get("total_worker_pay", 0)))
        make_button(sidebar, "Export to PDF", lambda: _handle_export("Delivery Report", data, report_container.winfo_toplevel())).pack(fill="x", pady=(8, 0))

    bar = create_filter_bar(root, "Delivery Report")
    start_var, end_var, period_var = add_date_range_controls(
        bar,
        (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"),
        datetime.now().strftime("%Y-%m-%d"),
        lambda: generate_report(True),
        include_period=True,
    )
    attach_auto_generate(root, generate_report, period_var=period_var)
    return generate_report


def _handle_export(report_type, data, parent=None):
    success, message = export_to_pdf(report_type, data)
    if success:
        if not os.path.isfile(message) or os.path.getsize(message) == 0:
            show_pdf_error_message(parent, f"The PDF export finished, but the saved file could not be found.\n\nExpected path:\n{message}")
            return
        show_pdf_success_message(parent, report_type, message)
        return
    if message != "Export cancelled.":
        show_pdf_error_message(parent, message)
