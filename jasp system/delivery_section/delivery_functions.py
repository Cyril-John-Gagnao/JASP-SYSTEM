import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont
import calendar
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

from .delivery_database import (
    insert_delivery,
    insert_other_item_delivery,
    update_other_item_delivery_record,
    delete_other_item_delivery_record,
    update_delivery_record,
    delete_delivery_record,
    fetch_delivery_rows,
    fetch_other_item_delivery_rows,
    fetch_delivery_summary,
    fetch_other_item_delivery_summary,
)
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
    delivery_win.destroy()


def refresh_data(load_data):
    load_data()


def money(value):
    return f"₱{value:,.2f}"


def parse_money(value):
    cleaned = "".join(ch for ch in str(value) if ch.isdigit() or ch in ".-")
    return float(cleaned or 0)


def open_date_calendar(parent, date_var):
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


def open_delivery_summary(parent_win, cursor, bg_main, text_color):
    summary_win = tk.Toplevel(parent_win)
    summary_win.title("Delivery Summary")
    summary_win.geometry("1050x580")
    summary_win.configure(bg=bg_main)

    summary_win.update_idletasks()
    x = (summary_win.winfo_screenwidth() // 2) - (1050 // 2)
    y = (summary_win.winfo_screenheight() // 2) - (580 // 2)
    summary_win.geometry(f"1050x580+{x}+{y}")

    period_var = tk.StringVar(value="day")
    date_sel = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    summary_display_var = tk.StringVar(value="chb")
    def compute_range():
        p = period_var.get()
        if p == "day":
            d = datetime.strptime(date_sel.get(), "%Y-%m-%d")
            start = d
            end = d
        elif p == "week":
            d = datetime.strptime(date_sel.get(), "%Y-%m-%d")
            start = d - timedelta(days=d.weekday())
            end = start + timedelta(days=6)
        elif p == "month":
            try:
                d = datetime.strptime(date_sel.get(), "%Y-%m-%d")
                m = d.month
                y = d.year
            except Exception:
                m = datetime.now().month
                y = datetime.now().year
            start = datetime(y, m, 1)
            if m == 12:
                end = datetime(y, 12, 31)
            else:
                end = datetime(y, m + 1, 1) - timedelta(days=1)
        else:
            start = None
            end = None
        return start, end

    def load_summary():
        configure_summary_tree()
        for row_id in summary_tree.get_children():
            summary_tree.delete(row_id)

        start, end = compute_range()
        empty_text = "No deliveries today" if period_var.get() == "day" else "No deliveries in this period"

        if summary_display_var.get() == "other":
            rows = fetch_other_item_delivery_summary(cursor, start, end)
            total_quantity = 0
            total_fee = 0

            if not rows:
                summary_tree.insert(
                    "",
                    "end",
                    values=(start.strftime("%Y-%m-%d"), start.strftime("%Y-%m-%d"), empty_text, "", "", "", "", ""),
                    tags=("oddrow",)
                )

            for i, row in enumerate(rows):
                transaction_date, delivery_date, item_name, quantity, unit, address, driver, helper, delivery_fee = row
                total_quantity += quantity
                total_fee += delivery_fee
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                summary_tree.insert(
                    "",
                    "end",
                    values=(transaction_date, delivery_date, item_name, f"{quantity:,}", unit, address, driver, helper, money(delivery_fee)),
                    tags=(tag,)
                )

            totals_var.set(f"TOTAL QUANTITY: {total_quantity:,} | Delivery Fee: {money(total_fee)}")
        else:
            rows = fetch_delivery_summary(cursor, start, end)
            total_blocks = 0
            total_fee = 0
            total_salary = 0

            if not rows:
                summary_tree.insert(
                    "",
                    "end",
                    values=(start.strftime("%Y-%m-%d"), start.strftime("%Y-%m-%d"), empty_text, "", "", "", "", ""),
                    tags=("oddrow",)
                )

            for i, row in enumerate(rows):
                transaction_date, delivery_date, worker, driver, address, blocks, fee, salary = row
                total_blocks += blocks
                total_fee += fee
                total_salary += salary
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                summary_tree.insert(
                    "",
                    "end",
                    values=(
                        transaction_date,
                        delivery_date,
                        worker,
                        driver,
                        address,
                        f"{blocks:,}",
                        money(fee),
                        money(salary),
                    ),
                    tags=(tag,)
                )

            totals_var.set(f"TOTAL: {total_blocks:,} blocks | Delivery Fee: {money(total_fee)} | Worker Salary: {money(total_salary)}")
        auto_adjust_summary_columns(summary_tree)

    def get_summary_title():
        start, end = compute_range()
        summary_name = "Other Items Delivery Summary" if summary_display_var.get() == "other" else "CHB Blocks Delivery Summary"
        if period_var.get() == "day":
            return f"Daily {summary_name} - {start.strftime('%B %d, %Y')}"
        if period_var.get() == "week":
            return f"Weekly {summary_name} - {start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
        return f"Monthly {summary_name} - {start.strftime('%B %Y')}"

    def get_summary_table_data():
        rows = []
        for item in summary_tree.get_children():
            values = summary_tree.item(item, "values")
            rows.append(values)

        if summary_display_var.get() == "other":
            total_quantity = 0
            total_fee = 0
            for values in rows:
                total_quantity += int(str(values[3]).replace(",", "") or 0)
                total_fee += parse_money(values[8])

            table_data = [["Transaction Date", "Delivery Date", "Item Name", "Quantity", "Unit of Measurement", "Delivery Address", "Delivery Driver", "Helper", "Delivery Fee"]]
            table_data.extend(rows)
            table_data.append(["", "", "TOTAL", f"{total_quantity:,}", "", "", "", "", money(total_fee)])
            return table_data, rows, f"TOTAL QUANTITY: {total_quantity:,} | Delivery Fee: {money(total_fee)}", [0.7*inch, 0.7*inch, 0.8*inch, 0.55*inch, 0.8*inch, 1.0*inch, 0.8*inch, 0.65*inch, 0.65*inch]

        total_blocks = 0
        total_fee = 0
        total_salary = 0
        for values in rows:
            total_blocks += int(str(values[5]).replace(",", "") or 0)
            total_fee += parse_money(values[6])
            total_salary += parse_money(values[7])

        table_data = [[
            "Transaction Date", "Delivery Date", "Worker Name", "Driver Name",
            "Address", "Blocks", "Delivery Fee", "Worker Salary"
        ]]
        table_data.extend(rows)
        table_data.append(["", "", "", "", "TOTAL", f"{total_blocks:,}", money(total_fee), money(total_salary)])
        return table_data, rows, f"TOTAL: {total_blocks:,} blocks | Delivery Fee: {money(total_fee)} | Worker Salary: {money(total_salary)}", [0.95*inch, 0.9*inch, 1.0*inch, 1.0*inch, 1.25*inch, 0.65*inch, 0.8*inch, 0.9*inch]

    def save_summary_pdf(file_path, title_text, table_data, col_widths):
        pdf = SimpleDocTemplate(file_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "DeliverySummaryTitle",
            parent=styles["Heading1"],
            fontSize=16,
            textColor=colors.HexColor("#2563eb"),
            spaceAfter=12,
            alignment=1
        )
        footer_style = ParagraphStyle(
            "DeliverySummaryFooter",
            parent=styles["Normal"],
            fontSize=9,
            textColor=colors.grey,
            alignment=1
        )

        elements.append(Paragraph(title_text, title_style))

        table = Table(
            table_data,
            colWidths=col_widths
        )
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 8),
            ("FONTSIZE", (0, 1), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
            ("TOPPADDING", (0, 0), (-1, 0), 8),
            ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#93c5fd")),
            ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.black),
            ("ROWBACKGROUNDS", (0, 1), (-1, -2), [colors.white, colors.HexColor("#e0f2fe")]),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.25*inch))
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))
        pdf.build(elements)

    def open_pdf_preview():
        try:
            load_summary()
            title_text = get_summary_title()
            table_data, rows, totals_text, pdf_col_widths = get_summary_table_data()

            preview_win = tk.Toplevel(summary_win)
            preview_win.title("Delivery Summary Preview")
            preview_win.geometry("1050x580")
            preview_win.configure(bg=bg_main)
            preview_win.transient(summary_win)

            preview_win.update_idletasks()
            x = (preview_win.winfo_screenwidth() // 2) - (1050 // 2)
            y = (preview_win.winfo_screenheight() // 2) - (580 // 2)
            preview_win.geometry(f"1050x580+{x}+{y}")

            tk.Label(
                preview_win,
                text=title_text,
                bg=bg_main,
                fg="#1e40af",
                font=("Arial", 16, "bold")
            ).pack(fill="x", padx=14, pady=(14, 8))

            preview_frame = tk.Frame(preview_win, bg=bg_main)
            preview_frame.pack(fill="both", expand=True, padx=12, pady=8)
            preview_frame.columnconfigure(0, weight=1)
            preview_frame.rowconfigure(0, weight=1)

            preview_tree = ttk.Treeview(
                preview_frame,
                columns=get_summary_columns(),
                show="headings",
                style="DeliverySummary.Treeview"
            )
            preview_tree.grid(row=0, column=0, sticky="nsew")
            preview_vsb = ttk.Scrollbar(preview_frame, orient="vertical", command=preview_tree.yview)
            preview_hsb = ttk.Scrollbar(preview_frame, orient="horizontal", command=preview_tree.xview)
            preview_tree.configure(yscrollcommand=preview_vsb.set, xscrollcommand=preview_hsb.set)
            preview_vsb.grid(row=0, column=1, sticky="ns")
            preview_hsb.grid(row=1, column=0, sticky="ew")

            headings = get_summary_headings()
            widths = get_summary_widths()
            for col in get_summary_columns():
                preview_tree.heading(col, text=headings[col])
                preview_tree.column(col, width=widths[col], anchor="w" if col in ("worker", "driver", "address", "item", "other_address", "other_driver", "helper") else "center", stretch=False)
            preview_tree.tag_configure("oddrow", background="#ffffff", font=("Arial", 13))
            preview_tree.tag_configure("evenrow", background="#93c5fd", font=("Arial", 13))

            for index, row in enumerate(rows):
                tag = "evenrow" if index % 2 == 0 else "oddrow"
                preview_tree.insert("", "end", values=row, tags=(tag,))
            auto_adjust_summary_columns(preview_tree)

            tk.Label(
                preview_win,
                text=totals_text,
                bg=bg_main,
                fg="#1e40af",
                font=("Arial", 13, "bold")
            ).pack(fill="x", padx=12, pady=(0, 10))

            action_frame = tk.Frame(preview_win, bg=bg_main)
            action_frame.pack(fill="x", padx=12, pady=(0, 12))

            def choose_file_and_save():
                try:
                    file_path = filedialog.asksaveasfilename(
                        parent=preview_win,
                        defaultextension=".pdf",
                        filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                        initialfile=f"delivery_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    )
                    if not file_path:
                        return
                    save_summary_pdf(file_path, title_text, table_data, pdf_col_widths)
                    show_delivery_success(preview_win, "Success", f"PDF exported successfully!\n{file_path}")
                    preview_win.destroy()
                except Exception as e:
                    show_delivery_error(preview_win, "Error", f"Failed to export PDF:\n{str(e)}")

            preview_button_border = {
                "bd": 2,
                "relief": "solid",
                "highlightthickness": 1,
                "highlightbackground": "black",
                "highlightcolor": "black",
            }
            tk.Button(action_frame, text="Save as PDF", command=choose_file_and_save, bg="#059669", fg="white", font=("Arial", 11, "bold"), width=16, padx=12, pady=8, **preview_button_border).pack(side="right", padx=6)
            tk.Button(action_frame, text="Close Preview", command=preview_win.destroy, bg="#64748b", fg="white", font=("Arial", 11, "bold"), width=16, padx=12, pady=8, **preview_button_border).pack(side="right", padx=6)

        except Exception as e:
            show_delivery_error(summary_win, "Error", f"Failed to preview summary:\n{str(e)}")

    top_frame = tk.Frame(summary_win, bg=bg_main)
    top_frame.pack(fill="x", pady=12, padx=10)

    button_border = {
        "bd": 2,
        "relief": "solid",
        "highlightthickness": 1,
        "highlightbackground": "black",
        "highlightcolor": "black",
    }

    def set_period(period):
        period_var.set(period)
        if period == "day":
            date_sel.set(datetime.now().strftime("%Y-%m-%d"))
        load_summary()

    tk.Label(top_frame, text="Period:", bg=bg_main, font=("Arial", 16, "bold"), fg=text_color).pack(side="left", padx=6)
    tk.Radiobutton(top_frame, text="Day", variable=period_var, value="day", bg=bg_main, font=("Arial", 15), command=lambda: set_period("day")).pack(side="left", padx=8)
    tk.Radiobutton(top_frame, text="Week", variable=period_var, value="week", bg=bg_main, font=("Arial", 15), command=lambda: set_period("week")).pack(side="left", padx=8)
    tk.Radiobutton(top_frame, text="Month", variable=period_var, value="month", bg=bg_main, font=("Arial", 15), command=lambda: set_period("month")).pack(side="left", padx=8)

    def set_summary_display(display_type):
        summary_display_var.set(display_type)
        load_summary()

    date_frame = tk.Frame(top_frame, bg=bg_main)
    date_frame.pack(side="left", padx=(30, 10))

    tk.Label(date_frame, text="Date:", bg=bg_main, font=("Arial", 16, "bold"), fg=text_color).pack(side="left", padx=(0, 6))
    tk.Entry(date_frame, textvariable=date_sel, width=15, font=("Arial", 15), relief="solid", bd=1).pack(side="left", padx=4)
    tk.Button(date_frame, text="Calendar", command=lambda: open_date_calendar(summary_win, date_sel), bg="#3b82f6", fg="white", font=("Arial", 13, "bold"), padx=10, pady=6, **button_border).pack(side="left", padx=4)
    tk.Button(date_frame, text="Apply", command=load_summary, bg="#1e3a8a", fg="white", font=("Arial", 13, "bold"), width=9, padx=8, pady=6, **button_border).pack(side="left", padx=4)
    tk.Button(top_frame, text="Close", command=summary_win.destroy, bg="#dc2626", fg="white", font=("Arial", 13, "bold"), padx=18, pady=6, **button_border).pack(side="right", padx=4)

    action_frame = tk.Frame(summary_win, bg=bg_main)
    action_frame.pack(fill="x", padx=12, pady=(0, 6))
    tk.Button(action_frame, text="Preview / Download PDF", command=open_pdf_preview, bg="#059669", fg="white", font=("Arial", 13, "bold"), width=24, padx=12, pady=8, **button_border).pack(side="left", padx=4)

    display_frame = tk.Frame(summary_win, bg=bg_main)
    display_frame.pack(fill="x", padx=12, pady=(0, 6))
    tk.Label(display_frame, text="Display:", bg=bg_main, font=("Arial", 16, "bold"), fg=text_color).pack(side="left", padx=(4, 8))
    tk.Radiobutton(display_frame, text="CHB Blocks", variable=summary_display_var, value="chb", bg=bg_main, font=("Arial", 14, "bold"), command=lambda: set_summary_display("chb")).pack(side="left", padx=6)
    tk.Radiobutton(display_frame, text="Other Items", variable=summary_display_var, value="other", bg=bg_main, font=("Arial", 14, "bold"), command=lambda: set_summary_display("other")).pack(side="left", padx=6)

    chb_cols = ("transaction", "delivery", "worker", "driver", "address", "blocks", "fee", "salary")
    other_cols = ("transaction_date", "delivery_date", "item", "quantity", "unit", "other_address", "other_driver", "helper", "other_fee")
    chb_summary_headings = {
        "transaction": "Transaction Date",
        "delivery": "Delivery Date",
        "worker": "Worker Name",
        "driver": "Driver Name",
        "address": "Address",
        "blocks": "Blocks",
        "fee": "Delivery Fee",
        "salary": "Worker Salary",
    }
    other_summary_headings = {
        "transaction_date": "Transaction Date",
        "delivery_date": "Delivery Date",
        "item": "Item Name",
        "quantity": "Quantity",
        "unit": "Unit of Measurement",
        "other_address": "Delivery Address",
        "other_driver": "Delivery Driver",
        "helper": "Helper",
        "other_fee": "Delivery Fee",
    }
    chb_summary_widths = {
        "transaction": 130,
        "delivery": 120,
        "worker": 150,
        "driver": 150,
        "address": 210,
        "blocks": 100,
        "fee": 120,
        "salary": 130,
    }
    other_summary_widths = {
        "transaction_date": 135,
        "delivery_date": 135,
        "item": 160,
        "quantity": 105,
        "unit": 155,
        "other_address": 230,
        "other_driver": 160,
        "helper": 140,
        "other_fee": 130,
    }

    def get_summary_columns():
        return other_cols if summary_display_var.get() == "other" else chb_cols

    def get_summary_headings():
        return other_summary_headings if summary_display_var.get() == "other" else chb_summary_headings

    def get_summary_widths():
        return other_summary_widths if summary_display_var.get() == "other" else chb_summary_widths

    def configure_summary_tree():
        selected_cols = get_summary_columns()
        headings = get_summary_headings()
        widths = get_summary_widths()
        summary_tree.configure(columns=selected_cols)
        for col in selected_cols:
            summary_tree.heading(col, text=headings[col])
            summary_tree.column(
                col,
                width=widths[col],
                minwidth=90,
                anchor="w" if col in ("worker", "driver", "address", "item", "other_address", "other_driver", "helper") else "center",
                stretch=False
            )

    style = ttk.Style()
    style.configure("DeliverySummary.Treeview", font=("Arial", 13), rowheight=38)
    style.configure("DeliverySummary.Treeview.Heading", font=("Arial", 14, "bold"), padding=(6, 8, 6, 8))

    def auto_adjust_summary_columns(tree_widget):
        tree_widget.update_idletasks()
        heading_font = tkfont.Font(font=style.lookup("DeliverySummary.Treeview.Heading", "font"))
        row_font = tkfont.Font(font=style.lookup("DeliverySummary.Treeview", "font"))
        padding = {
            "transaction": 42,
            "delivery": 42,
            "worker": 58,
            "driver": 58,
            "address": 70,
            "blocks": 42,
            "fee": 52,
            "salary": 58,
            "transaction_date": 42,
            "delivery_date": 42,
            "item": 58,
            "quantity": 42,
            "unit": 58,
            "other_address": 70,
            "other_driver": 58,
            "helper": 58,
            "other_fee": 52,
        }
        min_widths = {
            "transaction": 145,
            "delivery": 130,
            "worker": 145,
            "driver": 145,
            "address": 190,
            "blocks": 95,
            "fee": 130,
            "salary": 145,
            "transaction_date": 135,
            "delivery_date": 135,
            "item": 150,
            "quantity": 105,
            "unit": 150,
            "other_address": 210,
            "other_driver": 155,
            "helper": 135,
            "other_fee": 125,
        }
        max_widths = {
            "transaction": 210,
            "delivery": 200,
            "worker": 280,
            "driver": 280,
            "address": 460,
            "blocks": 140,
            "fee": 190,
            "salary": 210,
            "transaction_date": 190,
            "delivery_date": 190,
            "item": 280,
            "quantity": 150,
            "unit": 220,
            "other_address": 460,
            "other_driver": 280,
            "helper": 260,
            "other_fee": 180,
        }

        headings = get_summary_headings()
        for col in get_summary_columns():
            width = heading_font.measure(headings[col]) + padding[col]
            for item in tree_widget.get_children():
                width = max(width, row_font.measure(str(tree_widget.set(item, col))) + padding[col])
            width = max(min_widths[col], min(width, max_widths[col]))
            tree_widget.column(col, width=width, minwidth=min_widths[col], stretch=False)

    tree_frame = tk.Frame(summary_win, bg=bg_main)
    tree_frame.pack(fill="both", expand=True, padx=12, pady=12)
    tree_frame.columnconfigure(0, weight=1)
    tree_frame.rowconfigure(0, weight=1)

    summary_tree = ttk.Treeview(tree_frame, columns=get_summary_columns(), show="headings", style="DeliverySummary.Treeview")
    configure_summary_tree()
    summary_tree.grid(row=0, column=0, sticky="nsew")
    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=summary_tree.yview)
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=summary_tree.xview)
    summary_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    summary_tree.tag_configure("oddrow", background="#ffffff", font=("Arial", 13))
    summary_tree.tag_configure("evenrow", background="#93c5fd", font=("Arial", 13))

    totals_var = tk.StringVar(value="")
    tk.Label(summary_win, textvariable=totals_var, bg=bg_main, font=("Arial", 15, "bold"), fg="#1e40af").pack(fill="x", padx=12, pady=(0, 12))

    load_summary()


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
        item_name = entry_by_label["Item Name"].get().strip()
        quantity_text = entry_by_label["Quantity"].get().strip()
        unit_of_measurement = entry_by_label["Unit of Measurement"].get().strip()
        delivery_address = entry_by_label["Delivery Address"].get().strip()
        delivery_driver = entry_by_label["Delivery Driver"].get().strip()
        helper = entry_by_label["Helper"].get().strip()
        delivery_fee_text = entry_by_label["Delivery Fee"].get().strip()

        try:
            quantity = int(quantity_text)
        except Exception:
            show_delivery_error(form_win, "Error", "Quantity must be a whole number.")
            return None

        try:
            delivery_fee = float(delivery_fee_text or 0)
        except Exception:
            show_delivery_error(form_win, "Error", "Delivery fee must be a valid number.")
            return None

        if not item_name or not unit_of_measurement or not delivery_address or not delivery_driver or not helper:
            show_delivery_error(form_win, "Error", "Fill all fields.")
            return None

        if quantity <= 0:
            show_delivery_error(form_win, "Error", "Quantity must be greater than zero.")
            return None

        return transaction_date_var.get(), delivery_date_var.get(), item_name, quantity, unit_of_measurement, delivery_address, delivery_driver, helper, delivery_fee

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
    try:
        blocks = int(blocks_entry.get())
        delivery_fee = float(delivery_fee_entry.get() or 0)
        payment_per = float(payment_var.get())
        total = blocks * payment_per
    except:
        show_delivery_error(delivery_win, "Error", "Invalid input")
        return

    worker = worker_entry.get()
    driver_name = driver_entry.get()
    address = address_entry.get()
    transaction_date = transaction_date_var.get()
    date = date_var.get()

    if not worker:
        show_delivery_error(delivery_win, "Error", "Fill all fields")
        return

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

    try:
        blocks = int(blocks_entry.get())
        delivery_fee = float(delivery_fee_entry.get() or 0)
        payment_per = float(payment_var.get())
        total = blocks * payment_per
    except:
        show_delivery_error(delivery_win, "Error", "Invalid input")
        return

    if not ask_delivery_confirmation(delivery_win, "Confirm Update", f"Update record for {worker_entry.get()}?", "Update"):
        return

    update_delivery_record(conn, cursor, selected_id.get(), transaction_date_var.get(), date_var.get(), worker_entry.get(), driver_entry.get(), address_entry.get(), blocks, delivery_fee, payment_per, total)
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
            tree.insert("", "end", values=("", today, today, "No deliveries for today", "", "", "", "", ""), tags=('oddrow',))
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
            tree.insert("", "end", values=("", today, today, "No other item deliveries for today", "", "", "", "", "", ""), tags=("oddrow",))
            return

        for row_index, row in enumerate(rows):
            tag = "evenrow" if row_index % 2 == 0 else "oddrow"
            tree.insert("", "end", values=tuple(row), tags=(tag,))
    except Exception as e:
        show_delivery_error(delivery_win, "Error", f"Failed to load other item deliveries: {str(e)}")


def on_closing(conn, delivery_win):
    conn.close()
    delivery_win.destroy()
