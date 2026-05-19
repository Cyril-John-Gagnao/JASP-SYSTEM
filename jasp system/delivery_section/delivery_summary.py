import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from tkinter import font as tkfont
from datetime import datetime, timedelta

from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

from .delivery_database import fetch_delivery_summary, fetch_other_item_delivery_summary
from .delivery_functions import (
    center_window,
    show_delivery_error,
    show_delivery_success,
    money,
    parse_money,
    open_date_calendar,
)


def ensure_pdf_download_table(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pdf_downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT NOT NULL,
            downloaded_at TEXT NOT NULL,
            location TEXT NOT NULL
        )
    """)


def save_pdf_download(cursor, module, location):
    ensure_pdf_download_table(cursor)
    downloaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO pdf_downloads (module, downloaded_at, location) VALUES (?, ?, ?)",
        (module, downloaded_at, location),
    )
    cursor.connection.commit()
    return downloaded_at


def fetch_pdf_downloads(cursor, module, start_date=None, end_date=None):
    ensure_pdf_download_table(cursor)
    if start_date and end_date:
        cursor.execute(
            """
            SELECT downloaded_at, location
            FROM pdf_downloads
            WHERE module = ?
              AND DATE(downloaded_at) BETWEEN ? AND ?
            ORDER BY id DESC
            """,
            (module, start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")),
        )
        return cursor.fetchall()
    cursor.execute(
        """
        SELECT downloaded_at, location
        FROM pdf_downloads
        WHERE module = ?
        ORDER BY id DESC
        """,
        (module,),
    )
    return cursor.fetchall()


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
    pdf_download_module = "delivery_summary"
    ensure_pdf_download_table(cursor)
    cursor.connection.commit()

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
                    values=(start.strftime("%Y-%m-%d"), start.strftime("%Y-%m-%d"), empty_text, "", "", "", "", "", "", ""),
                    tags=("oddrow",)
                )

            for i, row in enumerate(rows):
                transaction_date, delivery_date, item_name, quantity, unit, address, driver, helper, responsible_user, delivery_fee = row
                total_quantity += quantity
                total_fee += delivery_fee
                tag = "evenrow" if i % 2 == 0 else "oddrow"
                summary_tree.insert(
                    "",
                    "end",
                    values=(transaction_date, delivery_date, item_name, f"{quantity:,}", unit, address, driver, helper, money(delivery_fee), responsible_user),
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
                    values=(start.strftime("%Y-%m-%d"), start.strftime("%Y-%m-%d"), empty_text, "", "", "", "", "", ""),
                    tags=("oddrow",)
                )

            for i, row in enumerate(rows):
                transaction_date, delivery_date, worker, driver, address, responsible_user, blocks, fee, salary = row
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
                        responsible_user,
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

            table_data = [["Transaction Date", "Delivery Date", "Item Name", "Quantity", "Unit of Measurement", "Delivery Address", "Delivery Driver", "Helper", "Delivery Fee", "User"]]
            table_data.extend(rows)
            table_data.append(["", "", "TOTAL", f"{total_quantity:,}", "", "", "", "", money(total_fee), ""])
            return table_data, rows, f"TOTAL QUANTITY: {total_quantity:,} | Delivery Fee: {money(total_fee)}", [0.65*inch, 0.65*inch, 0.7*inch, 0.5*inch, 0.7*inch, 0.85*inch, 0.7*inch, 0.55*inch, 0.6*inch, 0.6*inch]

        total_blocks = 0
        total_fee = 0
        total_salary = 0
        for values in rows:
            total_blocks += int(str(values[5]).replace(",", "") or 0)
            total_fee += parse_money(values[6])
            total_salary += parse_money(values[7])

        table_data = [[
            "Transaction Date", "Delivery Date", "Worker Name", "Driver Name",
            "Address", "Blocks", "Delivery Fee", "Worker Salary", "User"
        ]]
        table_data.extend(rows)
        table_data.append(["", "", "", "", "TOTAL", f"{total_blocks:,}", money(total_fee), money(total_salary), ""])
        return table_data, rows, f"TOTAL: {total_blocks:,} blocks | Delivery Fee: {money(total_fee)} | Worker Salary: {money(total_salary)}", [0.8*inch, 0.75*inch, 0.85*inch, 0.85*inch, 1.0*inch, 0.75*inch, 0.55*inch, 0.7*inch, 0.75*inch]

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
                preview_tree.column(col, width=widths[col], anchor="w" if col in ("worker", "driver", "address", "user", "item", "other_address", "other_driver", "helper", "other_user") else "center", stretch=False)
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
                    save_pdf_download(cursor, pdf_download_module, file_path)
                    show_delivery_success(
                        preview_win,
                        "PDF Downloaded Successfully",
                        f"The PDF has been downloaded successfully.\n\nSaved to:\n{file_path}"
                    )
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
    tk.Button(action_frame, text="View Downloaded PDF", command=lambda: open_downloaded_pdf_window(), bg="#2563eb", fg="white", font=("Arial", 13, "bold"), width=22, padx=12, pady=8, **button_border).pack(side="left", padx=4)

    display_frame = tk.Frame(summary_win, bg=bg_main)
    display_frame.pack(fill="x", padx=12, pady=(0, 6))
    tk.Label(display_frame, text="Display:", bg=bg_main, font=("Arial", 16, "bold"), fg=text_color).pack(side="left", padx=(4, 8))
    tk.Radiobutton(display_frame, text="CHB Blocks", variable=summary_display_var, value="chb", bg=bg_main, font=("Arial", 14, "bold"), command=lambda: set_summary_display("chb")).pack(side="left", padx=6)
    tk.Radiobutton(display_frame, text="Other Items", variable=summary_display_var, value="other", bg=bg_main, font=("Arial", 14, "bold"), command=lambda: set_summary_display("other")).pack(side="left", padx=6)

    chb_cols = ("transaction", "delivery", "worker", "driver", "address", "blocks", "fee", "salary", "user")
    other_cols = ("transaction_date", "delivery_date", "item", "quantity", "unit", "other_address", "other_driver", "helper", "other_fee", "other_user")
    chb_summary_headings = {
        "transaction": "Transaction Date",
        "delivery": "Delivery Date",
        "worker": "Worker Name",
        "driver": "Driver Name",
        "address": "Address",
        "blocks": "Blocks",
        "fee": "Delivery Fee",
        "salary": "Worker Salary",
        "user": "User",
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
        "other_user": "User",
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
        "user": 140,
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
        "other_user": 140,
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
                anchor="w" if col in ("worker", "driver", "address", "user", "item", "other_address", "other_driver", "helper", "other_user") else "center",
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
            "user": 58,
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
            "other_user": 58,
            "other_fee": 52,
        }
        min_widths = {
            "transaction": 145,
            "delivery": 130,
            "worker": 145,
            "driver": 145,
            "address": 190,
            "user": 130,
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
            "other_user": 130,
            "other_fee": 125,
        }
        max_widths = {
            "transaction": 210,
            "delivery": 200,
            "worker": 280,
            "driver": 280,
            "address": 460,
            "user": 240,
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
            "other_user": 240,
            "other_fee": 180,
        }

        headings = get_summary_headings()
        for col in tree_widget["columns"]:
            width = heading_font.measure(headings[col]) + padding[col]
            for item in tree_widget.get_children():
                width = max(width, row_font.measure(str(tree_widget.set(item, col))) + padding[col])
            width = max(min_widths[col], min(width, max_widths[col]))
            tree_widget.column(col, width=width, minwidth=min_widths[col], stretch=False)

    def open_pdf_location(path):
        if not path or path == "Not downloaded":
            messagebox.showinfo("PDF Location", "This summary has not been downloaded yet.", parent=summary_win)
            return
        if not os.path.exists(path):
            messagebox.showwarning("PDF Location", "The saved PDF file could not be found.", parent=summary_win)
            return
        try:
            os.startfile(path)
        except Exception as e:
            show_delivery_error(summary_win, "Error", f"Failed to open PDF:\n{str(e)}")

    def open_downloaded_pdf_window():
        pdf_win = tk.Toplevel(summary_win)
        pdf_win.title("Downloaded Delivery PDFs")
        pdf_win.geometry("980x540")
        pdf_win.configure(bg=bg_main)
        pdf_win.transient(summary_win)

        tk.Label(pdf_win, text="Downloaded PDF Files", bg=bg_main, fg="#1e40af", font=("Arial", 22, "bold")).pack(anchor="w", padx=14, pady=(14, 8))
        tk.Label(
            pdf_win,
            text="Click the PDF location to open or view the downloaded PDF.",
            bg=bg_main,
            fg="#334155",
            font=("Arial", 15, "bold")
        ).pack(anchor="w", padx=14, pady=(0, 8))

        pdf_period_var = tk.StringVar(value="Day")
        pdf_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        def compute_pdf_range():
            try:
                selected = datetime.strptime(pdf_date_var.get(), "%Y-%m-%d")
            except Exception:
                selected = datetime.now()
                pdf_date_var.set(selected.strftime("%Y-%m-%d"))
            if pdf_period_var.get() == "Week":
                start_date = selected - timedelta(days=selected.weekday())
                end_date = start_date + timedelta(days=6)
            elif pdf_period_var.get() == "Month":
                start_date = datetime(selected.year, selected.month, 1)
                if selected.month == 12:
                    end_date = datetime(selected.year, 12, 31)
                else:
                    end_date = datetime(selected.year, selected.month + 1, 1) - timedelta(days=1)
            else:
                start_date = selected
                end_date = selected
            return start_date, end_date

        def empty_pdf_message():
            period = pdf_period_var.get()
            if period == "Day":
                if pdf_date_var.get() == datetime.now().strftime("%Y-%m-%d"):
                    return "No PDFs downloaded today."
                return "No PDFs downloaded on this date."
            if period == "Week":
                return "No PDFs downloaded this week."
            return "No PDFs downloaded this month."

        filter_frame = tk.Frame(pdf_win, bg=bg_main)
        filter_frame.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(filter_frame, text="Period:", bg=bg_main, font=("Arial", 14, "bold")).pack(side="left", padx=(0, 8))
        for period in ("Day", "Week", "Month"):
            tk.Radiobutton(filter_frame, text=period, variable=pdf_period_var, value=period, bg=bg_main, font=("Arial", 13)).pack(side="left", padx=4)
        tk.Label(filter_frame, text="Date:", bg=bg_main, font=("Arial", 14, "bold")).pack(side="left", padx=(18, 6))
        tk.Entry(filter_frame, textvariable=pdf_date_var, width=13, font=("Arial", 13), relief="solid", bd=1).pack(side="left", padx=4)
        tk.Button(filter_frame, text="Calendar", command=lambda: open_date_calendar(pdf_win, pdf_date_var, load_pdf_records), bg="#2563eb", fg="white", font=("Arial", 12, "bold"), padx=8, pady=4, **button_border).pack(side="left", padx=4)
        tk.Button(filter_frame, text="Apply", command=lambda: load_pdf_records(), bg="#059669", fg="white", font=("Arial", 12, "bold"), padx=8, pady=4, **button_border).pack(side="left", padx=4)

        pdf_frame = tk.Frame(pdf_win, bg=bg_main)
        pdf_frame.pack(fill="both", expand=True, padx=14, pady=(0, 10))
        pdf_style = ttk.Style()
        pdf_style.configure("DownloadedPDF.Treeview", font=("Arial", 14), rowheight=40)
        pdf_style.configure("DownloadedPDF.Treeview.Heading", font=("Arial", 15, "bold"), padding=(6, 8, 6, 8))
        pdf_tree = ttk.Treeview(pdf_frame, columns=("date", "location"), show="headings")
        pdf_tree.configure(style="DownloadedPDF.Treeview")
        pdf_tree.heading("date", text="Date Downloaded")
        pdf_tree.heading("location", text="PDF Location")
        pdf_tree.column("date", width=220, anchor="center")
        pdf_tree.column("location", width=620, anchor="w")
        pdf_tree.pack(side="left", fill="both", expand=True)
        pdf_scroll = ttk.Scrollbar(pdf_frame, orient="vertical", command=pdf_tree.yview)
        pdf_scroll.pack(side="right", fill="y")
        pdf_tree.configure(yscrollcommand=pdf_scroll.set)

        def load_pdf_records():
            for item in pdf_tree.get_children():
                pdf_tree.delete(item)
            start_date, end_date = compute_pdf_range()
            downloaded_pdf_records = fetch_pdf_downloads(cursor, pdf_download_module, start_date, end_date)
            if downloaded_pdf_records:
                for downloaded_at, location in downloaded_pdf_records:
                    pdf_tree.insert("", "end", values=(downloaded_at, location))
            else:
                pdf_tree.insert("", "end", values=("", empty_pdf_message()))

        def on_pdf_click(event):
            if pdf_tree.identify_column(event.x) != "#2":
                return
            item_id = pdf_tree.identify_row(event.y)
            if not item_id:
                return
            values = pdf_tree.item(item_id, "values")
            if values and len(values) > 1:
                open_pdf_location(values[1])

        pdf_tree.bind("<ButtonRelease-1>", on_pdf_click)
        load_pdf_records()
        tk.Button(pdf_win, text="Close", command=pdf_win.destroy, bg="#dc2626", fg="white", font=("Arial", 12, "bold"), padx=14, pady=6, **button_border).pack(anchor="e", padx=14, pady=(0, 12))

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


