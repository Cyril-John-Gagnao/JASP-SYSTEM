import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import calendar
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

from .delivery_database import (
    insert_delivery,
    update_delivery_record,
    delete_delivery_record,
    fetch_delivery_rows,
    fetch_delivery_summary,
    fetch_latest_delivery_summary_date,
)


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
            tk.Label(grid_frame, text=day_name, bg="#ffffff", fg="#1e293b", font=("Arial", 9, "bold"), width=5).grid(row=0, column=col, padx=1, pady=2)

        today = datetime.now()
        for row_index, week in enumerate(calendar.monthcalendar(year_var.get(), month_var.get()), start=1):
            for col_index, day in enumerate(week):
                if day == 0:
                    tk.Label(grid_frame, text="", bg="#ffffff", width=5).grid(row=row_index, column=col_index, padx=1, pady=1)
                    continue

                is_today = day == today.day and month_var.get() == today.month and year_var.get() == today.year
                tk.Button(
                    grid_frame,
                    text=str(day),
                    width=5,
                    bg="#2563eb" if is_today else "#f8fafc",
                    fg="white" if is_today else "#1e293b",
                    relief="flat",
                    command=lambda d=day: select_date(d)
                ).grid(row=row_index, column=col_index, padx=1, pady=1)

    tk.Button(header, text="<", command=lambda: change_month(-1), bg="#e0f2fe", relief="flat", width=4).pack(side="left")
    tk.Label(header, textvariable=title_var, bg="#ffffff", fg="#1e293b", font=("Arial", 11, "bold"), width=18).pack(side="left", padx=8)
    tk.Button(header, text=">", command=lambda: change_month(1), bg="#e0f2fe", relief="flat", width=4).pack(side="left")

    render_calendar()

    cal_win.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (cal_win.winfo_width() // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (cal_win.winfo_height() // 2)
    cal_win.geometry(f"+{x}+{y}")


def open_delivery_summary(parent_win, cursor, bg_main, text_color):
    latest_date = fetch_latest_delivery_summary_date(cursor)
    try:
        default_date = datetime.strptime(latest_date[:10], "%Y-%m-%d") if latest_date else datetime.now()
    except Exception:
        default_date = datetime.now()

    summary_win = tk.Toplevel(parent_win)
    summary_win.title("Delivery Summary")
    summary_win.geometry("1050x580")
    summary_win.configure(bg=bg_main)

    summary_win.update_idletasks()
    x = (summary_win.winfo_screenwidth() // 2) - (1050 // 2)
    y = (summary_win.winfo_screenheight() // 2) - (580 // 2)
    summary_win.geometry(f"1050x580+{x}+{y}")

    period_var = tk.StringVar(value="day")
    date_sel = tk.StringVar(value=default_date.strftime("%Y-%m-%d"))
    months = [
        "January", "February", "March", "April", "May", "June",
        "July", "August", "September", "October", "November", "December"
    ]
    month_var = tk.StringVar(value=default_date.strftime("%B"))
    year_var = tk.StringVar(value=str(default_date.year))
    years = [str(y) for y in range(datetime.now().year - 5, datetime.now().year + 1)]
    if str(default_date.year) not in years:
        years.append(str(default_date.year))
        years.sort(key=int)

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
                m = months.index(month_var.get()) + 1
                y = int(year_var.get())
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
        for row_id in summary_tree.get_children():
            summary_tree.delete(row_id)

        start, end = compute_range()
        rows = fetch_delivery_summary(cursor, start, end)
        total_blocks = 0
        total_fee = 0
        total_salary = 0

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

    def get_summary_title():
        start, end = compute_range()
        if period_var.get() == "day":
            return f"Daily Delivery Summary - {start.strftime('%B %d, %Y')}"
        if period_var.get() == "week":
            return f"Weekly Delivery Summary - {start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
        return f"Monthly Delivery Summary - {start.strftime('%B %Y')}"

    def get_summary_table_data():
        rows = []
        total_blocks = 0
        total_fee = 0
        total_salary = 0

        for item in summary_tree.get_children():
            values = summary_tree.item(item, "values")
            rows.append(values)
            total_blocks += int(str(values[5]).replace(",", "") or 0)
            total_fee += parse_money(values[6])
            total_salary += parse_money(values[7])

        table_data = [[
            "Transaction Date", "Delivery Date", "Worker Name", "Driver Name",
            "Address", "Blocks", "Delivery Fee", "Worker Salary"
        ]]
        table_data.extend(rows)
        table_data.append(["", "", "", "", "TOTAL", f"{total_blocks:,}", money(total_fee), money(total_salary)])
        return table_data, rows, total_blocks, total_fee, total_salary

    def save_summary_pdf(file_path, title_text, table_data):
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
            colWidths=[0.95*inch, 0.9*inch, 1.0*inch, 1.0*inch, 1.25*inch, 0.65*inch, 0.8*inch, 0.9*inch]
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
            table_data, rows, total_blocks, total_fee, total_salary = get_summary_table_data()

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
                columns=cols,
                show="headings",
                style="DeliverySummary.Treeview"
            )
            preview_tree.grid(row=0, column=0, sticky="nsew")
            preview_vsb = ttk.Scrollbar(preview_frame, orient="vertical", command=preview_tree.yview)
            preview_hsb = ttk.Scrollbar(preview_frame, orient="horizontal", command=preview_tree.xview)
            preview_tree.configure(yscrollcommand=preview_vsb.set, xscrollcommand=preview_hsb.set)
            preview_vsb.grid(row=0, column=1, sticky="ns")
            preview_hsb.grid(row=1, column=0, sticky="ew")

            headings = {
                "transaction": "Transaction Date",
                "delivery": "Delivery Date",
                "worker": "Worker Name",
                "driver": "Driver Name",
                "address": "Address",
                "blocks": "Blocks",
                "fee": "Delivery Fee",
                "salary": "Worker Salary",
            }
            widths = {
                "transaction": 130,
                "delivery": 120,
                "worker": 150,
                "driver": 150,
                "address": 210,
                "blocks": 100,
                "fee": 120,
                "salary": 130,
            }
            for col in cols:
                preview_tree.heading(col, text=headings[col])
                preview_tree.column(col, width=widths[col], anchor="w" if col in ("worker", "driver", "address") else "center", stretch=False)
            preview_tree.tag_configure("oddrow", background="#ffffff", font=("Arial", 11))
            preview_tree.tag_configure("evenrow", background="#93c5fd", font=("Arial", 11))

            for index, row in enumerate(rows):
                tag = "evenrow" if index % 2 == 0 else "oddrow"
                preview_tree.insert("", "end", values=row, tags=(tag,))

            tk.Label(
                preview_win,
                text=f"TOTAL: {total_blocks:,} blocks | Delivery Fee: {money(total_fee)} | Worker Salary: {money(total_salary)}",
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
                    save_summary_pdf(file_path, title_text, table_data)
                    messagebox.showinfo("Success", f"PDF exported successfully!\n{file_path}", parent=preview_win)
                    preview_win.destroy()
                except Exception as e:
                    messagebox.showerror("Error", f"Failed to export PDF:\n{str(e)}", parent=preview_win)

            tk.Button(action_frame, text="Save as PDF", command=choose_file_and_save, bg="#059669", fg="white", font=("Arial", 11, "bold"), width=16, padx=12, pady=8, relief="flat").pack(side="right", padx=6)
            tk.Button(action_frame, text="Close Preview", command=preview_win.destroy, bg="#64748b", fg="white", font=("Arial", 11, "bold"), width=16, padx=12, pady=8, relief="flat").pack(side="right", padx=6)

        except Exception as e:
            messagebox.showerror("Error", f"Failed to preview summary:\n{str(e)}", parent=summary_win)

    top_frame = tk.Frame(summary_win, bg=bg_main)
    top_frame.pack(fill="x", pady=12, padx=10)

    tk.Label(top_frame, text="Period:", bg=bg_main, font=("Arial", 11, "bold"), fg=text_color).pack(side="left", padx=6)
    tk.Radiobutton(top_frame, text="Day", variable=period_var, value="day", bg=bg_main, font=("Arial", 10), command=load_summary).pack(side="left", padx=8)
    tk.Radiobutton(top_frame, text="Week", variable=period_var, value="week", bg=bg_main, font=("Arial", 10), command=load_summary).pack(side="left", padx=8)
    tk.Radiobutton(top_frame, text="Month", variable=period_var, value="month", bg=bg_main, font=("Arial", 10), command=load_summary).pack(side="left", padx=8)

    date_frame = tk.Frame(top_frame, bg=bg_main)
    date_frame.pack(side="left", padx=(30, 10))

    tk.Label(date_frame, text="Date:", bg=bg_main, font=("Arial", 11, "bold"), fg=text_color).pack(side="left", padx=(0, 6))
    tk.Entry(date_frame, textvariable=date_sel, width=15, font=("Arial", 11), relief="solid", bd=1).pack(side="left", padx=4)
    tk.Button(date_frame, text="Cal", command=lambda: open_date_calendar(summary_win, date_sel), bg="#3b82f6", fg="white", font=("Arial", 9, "bold"), relief="flat", padx=6).pack(side="left", padx=4)

    month_year_frame = tk.Frame(top_frame, bg=bg_main)
    month_year_frame.pack(side="left", padx=10)

    ttk.Combobox(month_year_frame, values=months, textvariable=month_var, width=12, state="readonly", font=("Arial", 10)).pack(side="left", padx=4)
    ttk.Combobox(month_year_frame, values=years, textvariable=year_var, width=8, state="readonly", font=("Arial", 10)).pack(side="left", padx=4)
    tk.Button(month_year_frame, text="Apply", command=load_summary, bg="#3b82f6", fg="white", font=("Arial", 10, "bold"), width=10, padx=8, pady=5, relief="flat").pack(side="left", padx=4)

    action_frame = tk.Frame(summary_win, bg=bg_main)
    action_frame.pack(fill="x", padx=12, pady=(0, 6))
    tk.Button(action_frame, text="Preview / Download PDF", command=open_pdf_preview, bg="#059669", fg="white", font=("Arial", 10, "bold"), width=24, padx=12, pady=6, relief="flat").pack(side="left", padx=4)

    cols = ("transaction", "delivery", "worker", "driver", "address", "blocks", "fee", "salary")
    style = ttk.Style()
    style.configure("DeliverySummary.Treeview", font=("Arial", 11), rowheight=30)
    style.configure("DeliverySummary.Treeview.Heading", font=("Arial", 12, "bold"))

    tree_frame = tk.Frame(summary_win, bg=bg_main)
    tree_frame.pack(fill="both", expand=True, padx=12, pady=12)
    tree_frame.columnconfigure(0, weight=1)
    tree_frame.rowconfigure(0, weight=1)

    summary_tree = ttk.Treeview(tree_frame, columns=cols, show="headings", style="DeliverySummary.Treeview")
    summary_tree.heading("transaction", text="Transaction Date")
    summary_tree.heading("delivery", text="Delivery Date")
    summary_tree.heading("worker", text="Worker Name")
    summary_tree.heading("driver", text="Driver Name")
    summary_tree.heading("address", text="Address")
    summary_tree.heading("blocks", text="Blocks")
    summary_tree.heading("fee", text="Delivery Fee")
    summary_tree.heading("salary", text="Worker Salary")
    summary_tree.column("transaction", width=130, anchor="center")
    summary_tree.column("delivery", width=120, anchor="center")
    summary_tree.column("worker", width=150, anchor="w")
    summary_tree.column("driver", width=150, anchor="w")
    summary_tree.column("address", width=210, anchor="w")
    summary_tree.column("blocks", width=100, anchor="center")
    summary_tree.column("fee", width=120, anchor="center")
    summary_tree.column("salary", width=130, anchor="center")
    summary_tree.grid(row=0, column=0, sticky="nsew")
    vsb = ttk.Scrollbar(tree_frame, orient="vertical", command=summary_tree.yview)
    hsb = ttk.Scrollbar(tree_frame, orient="horizontal", command=summary_tree.xview)
    summary_tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
    vsb.grid(row=0, column=1, sticky="ns")
    hsb.grid(row=1, column=0, sticky="ew")
    summary_tree.tag_configure("oddrow", background="#ffffff", font=("Arial", 11))
    summary_tree.tag_configure("evenrow", background="#93c5fd", font=("Arial", 11))

    totals_var = tk.StringVar(value="")
    tk.Label(summary_win, textvariable=totals_var, bg=bg_main, font=("Arial", 13, "bold"), fg="#1e40af").pack(fill="x", padx=12, pady=(0, 12))

    load_summary()


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
        messagebox.showerror("Error", "Invalid input", parent=delivery_win)
        return

    worker = worker_entry.get()
    driver_name = driver_entry.get()
    address = address_entry.get()
    transaction_date = transaction_date_var.get()
    date = date_var.get()

    if not worker:
        messagebox.showerror("Error", "Fill all fields", parent=delivery_win)
        return

    if not messagebox.askyesno("Confirm Save", f"Save delivery record for {worker}?", parent=delivery_win):
        return

    insert_delivery(conn, cursor, transaction_date, date, worker, driver_name, address, blocks, delivery_fee, payment_per, total)
    load_data()
    clear_form()
    messagebox.showinfo("Success", "Delivery record saved successfully!", parent=delivery_win)


def update_delivery(conn, cursor, delivery_win, selected_id, transaction_date_var, worker_entry, date_var, driver_entry, address_entry, blocks_entry, delivery_fee_entry, payment_var, load_data, clear_form):
    if not selected_id.get():
        messagebox.showerror("Error", "Select a record", parent=delivery_win)
        return

    try:
        blocks = int(blocks_entry.get())
        delivery_fee = float(delivery_fee_entry.get() or 0)
        payment_per = float(payment_var.get())
        total = blocks * payment_per
    except:
        messagebox.showerror("Error", "Invalid input", parent=delivery_win)
        return

    if not messagebox.askyesno("Confirm Update", f"Update record for {worker_entry.get()}?", parent=delivery_win):
        return

    update_delivery_record(conn, cursor, selected_id.get(), transaction_date_var.get(), date_var.get(), worker_entry.get(), driver_entry.get(), address_entry.get(), blocks, delivery_fee, payment_per, total)
    load_data()
    clear_form()
    messagebox.showinfo("Success", "Record updated successfully!", parent=delivery_win)


def delete_delivery(conn, cursor, delivery_win, selected_id, worker_entry, load_data, clear_form):
    if not selected_id.get():
        return

    if not messagebox.askyesno("Confirm Delete", f"Delete record for {worker_entry.get()}?\n\nThis action cannot be undone.", parent=delivery_win):
        return

    delete_delivery_record(conn, cursor, selected_id.get())
    load_data()
    clear_form()
    messagebox.showinfo("Success", "Record deleted successfully!", parent=delivery_win)


def on_tree_configure(event, tree):
    tree.update_idletasks()


def on_select(event, tree, selected_id, transaction_date_var, date_var, worker_entry, driver_entry, address_entry, blocks_entry, delivery_fee_entry, auto_calc):
    selected = tree.focus()
    values = tree.item(selected, "values")

    if values:
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
        rows = fetch_delivery_rows(cursor, keyword, sort_option)

        row_index = 0
        for row in rows:
            tag = 'evenrow' if row_index % 2 == 0 else 'oddrow'
            tree.insert("", "end", values=tuple(row), tags=(tag,))
            row_index += 1
    except Exception as e:
        messagebox.showerror("Error", f"Failed to load data: {str(e)}", parent=delivery_win)


def on_closing(conn, delivery_win):
    conn.close()
    delivery_win.destroy()
