import tkinter as tk
from datetime import datetime
from tkinter import font as tkfont
from tkinter import filedialog, messagebox, ttk

from jasp_theme import DASHBOARD_CONTENT_BG

from .main_database import fetch_most_items_summary, fetch_recent_transaction_summary
from .main_functions import (
    ACCENT,
    BG_CARD,
    PRIMARY,
    TEXT_PRIMARY,
    center_window,
    compact_items,
    compact_txn_id,
    compute_summary_range,
    format_dashboard_datetime,
    money,
    open_date_calendar,
)

# Use the shared dashboard content background for summary windows.
SUMMARY_BG = DASHBOARD_CONTENT_BG


def open_recent_transactions_summary(parent):
    # Open the sales transactions summary window.
    summary_win = tk.Toplevel(parent)
    summary_win.title("Recent Transactions Summary")
    summary_win.configure(bg=SUMMARY_BG)
    summary_win.transient(parent)

    # Store selected filters, titles, totals, and current transaction rows.
    period_var = tk.StringVar(value="Day")
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    title_var = tk.StringVar()
    totals_var = tk.StringVar()
    current_rows = []

    def title_text():
        # Build the summary title from the selected period and date.
        start, end = compute_summary_range(period_var.get(), date_var.get())
        if period_var.get() == "Day":
            return f"Sales Transactions - {start.strftime('%B %d, %Y')}"
        if period_var.get() == "Week":
            return f"Sales Transactions - {start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
        return f"Sales Transactions - {start.strftime('%B %Y')}"

    def clear_tree(tree):
        # Remove all rows from a summary Treeview.
        for item in tree.get_children():
            tree.delete(item)

    # Define recent transaction summary columns and width limits.
    summary_headings = [
        ("txn", "TXN ID", 80, 120, "w"),
        ("date", "Date & Time", 170, 250, "w"),
        ("items", "Item(s) Sold", 220, 430, "w"),
        ("qty", "Qty", 70, 100, "e"),
        ("total", "Total", 110, 160, "e"),
        ("cashier", "Cashier", 120, 220, "w"),
        ("status", "Status", 90, 130, "center"),
    ]

    def adjust_summary_columns(tree):
        # Measure visible rows and resize transaction summary columns.
        tree.update_idletasks()
        body_font = tkfont.Font(family="Arial", size=12)
        heading_font = tkfont.Font(family="Arial", size=11, weight="bold")
        widths = {}

        for index, (col, heading, min_width, max_width, _anchor) in enumerate(summary_headings):
            widest = heading_font.measure(heading)
            for item in tree.get_children():
                values = tree.item(item, "values")
                if index < len(values):
                    widest = max(widest, body_font.measure(str(values[index])))
            widths[col] = min(max(widest + 32, min_width), max_width)

        total_width = sum(widths.values())
        available_width = max(tree.winfo_width() - 24, total_width)
        if total_width < available_width:
            extra = available_width - total_width
            per_column = extra // max(len(summary_headings), 1)
            for col in widths:
                widths[col] += per_column

        for col, _heading, _min_width, _max_width, anchor in summary_headings:
            tree.column(col, width=widths[col], minwidth=widths[col], anchor=anchor, stretch=True)

    def load_summary():
        # Reload transaction summary rows and totals for the selected period.
        nonlocal current_rows
        start, end = compute_summary_range(period_var.get(), date_var.get())
        data = fetch_recent_transaction_summary(start, end)
        current_rows = data["transactions"]
        clear_tree(summary_tree)
        if not current_rows:
            # Show an empty row when no transactions match the selected period.
            summary_tree.insert(
                "",
                "end",
                values=("", "", "No transactions for the selected period.", "", "", "", ""),
                tags=("even",),
            )
        for index, row in enumerate(current_rows):
            # Insert each transaction row with compacted values.
            txn_id, ts, item_summary, item_count, qty, total, cashier, status = row
            summary_tree.insert(
                "",
                "end",
                values=(
                    compact_txn_id(txn_id),
                    format_dashboard_datetime(ts),
                    compact_items(item_summary, item_count),
                    f"{qty:,}",
                    money(total),
                    cashier or "Admin",
                    status or "Paid",
                ),
                tags=("even" if index % 2 == 0 else "odd",),
            )
        adjust_summary_columns(summary_tree)

        title_var.set(title_text())
        totals_var.set(
            f"Transactions: {data['transaction_count']:,}   |   "
            f"Items Sold: {data['total_qty']:,}   |   Total Sales: {money(data['total_sales'])}"
        )

    def build_pdf(file_path, title, rows):
        # Build a PDF export for recent transactions.
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ImportError as exc:
            raise RuntimeError("ReportLab is required to export PDF. Install it with: pip install reportlab") from exc

        # Build the PDF table rows and fallback empty row.
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "SalesSummaryTitle",
            parent=styles["Heading1"],
            textColor=colors.HexColor(PRIMARY),
            fontSize=18,
            alignment=1,
            spaceAfter=10,
        )
        table_data = [["TXN ID", "Date & Time", "Items", "Qty", "Total", "Cashier", "Status"]]
        for row in rows:
            table_data.append(list(row))
        if len(table_data) == 1:
            table_data.append(["No transactions", "", "", "", "", "", ""])

        doc = SimpleDocTemplate(file_path, pagesize=landscape(letter), topMargin=0.45*inch, bottomMargin=0.45*inch)
        table = Table(table_data, colWidths=[1.15*inch, 1.8*inch, 2.25*inch, 0.65*inch, 1.05*inch, 1.1*inch, 0.85*inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (3, 1), (4, -1), "RIGHT"),
            ("ALIGN", (6, 1), (6, -1), "CENTER"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eff6ff")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story = [
            Paragraph(title, title_style),
            Paragraph(totals_var.get(), styles["Normal"]),
            Spacer(1, 0.12*inch),
            table,
            Spacer(1, 0.12*inch),
            Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]),
        ]
        doc.build(story)

    def open_preview():
        # Open a preview window before exporting recent transactions to PDF.
        load_summary()
        rows = [summary_tree.item(item, "values") for item in summary_tree.get_children()]
        preview = tk.Toplevel(summary_win)
        preview.title("Sales Summary Preview")
        preview.configure(bg=SUMMARY_BG)
        preview.transient(summary_win)

        # Build the preview header, totals, and table.
        tk.Label(preview, text=title_var.get(), bg=SUMMARY_BG, fg=PRIMARY,
                 font=("Arial", 18, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(preview, text=totals_var.get(), bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=(0, 8))

        preview_frame = tk.Frame(preview, bg=BG_CARD)
        preview_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        preview_tree = create_summary_tree(preview_frame, "SalesSummaryPreview.Treeview")
        for index, row in enumerate(rows):
            preview_tree.insert("", "end", values=row, tags=("even" if index % 2 == 0 else "odd",))
        adjust_summary_columns(preview_tree)

        actions = tk.Frame(preview, bg=SUMMARY_BG)
        actions.pack(fill="x", padx=16, pady=(0, 14))

        def save_pdf():
            # Ask where to save the PDF and export the preview rows.
            file_path = filedialog.asksaveasfilename(
                parent=preview,
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"sales_transactions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            )
            if not file_path:
                return
            try:
                build_pdf(file_path, title_var.get(), rows)
                messagebox.showinfo(
                    "PDF Downloaded Successfully",
                    f"The PDF has been downloaded successfully.\n\nSaved to:\n{file_path}",
                    parent=preview,
                )
                preview.destroy()
            except Exception as exc:
                messagebox.showerror("Export Failed", str(exc), parent=preview)

        tk.Button(actions, text="Save as PDF", command=save_pdf, bg="#059669", fg="white",
                  font=("Arial", 11, "bold"), relief="flat", padx=14, pady=8).pack(side="right", padx=5)
        tk.Button(actions, text="Close Preview", command=preview.destroy, bg="#64748b", fg="white",
                  font=("Arial", 11, "bold"), relief="flat", padx=14, pady=8).pack(side="right", padx=5)
        center_window(preview, 1040, 580, summary_win)

    def create_summary_tree(parent_frame, style_name):
        # Create a styled summary Treeview with scrollbars.
        columns = ("txn", "date", "items", "qty", "total", "cashier", "status")
        style = ttk.Style()
        style.configure(style_name, font=("Arial", 12), rowheight=34, background=BG_CARD, fieldbackground=BG_CARD)
        style.configure(f"{style_name}.Heading", font=("Arial", 11, "bold"), foreground=TEXT_PRIMARY)
        tree = ttk.Treeview(parent_frame, columns=columns, show="headings", style=style_name)
        vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(parent_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)
        for col, heading, min_width, _max_width, anchor in summary_headings:
            tree.heading(col, text=heading)
            tree.column(col, width=min_width, minwidth=min_width, anchor=anchor, stretch=True)
        tree.tag_configure("even", background="#e0f2fe")
        tree.tag_configure("odd", background="#ffffff")
        return tree

    # Build summary filter controls and action buttons.
    controls = tk.Frame(summary_win, bg=SUMMARY_BG)
    controls.pack(fill="x", padx=16, pady=(14, 8))
    summary_button_options = {
        "fg": "white",
        "font": ("Arial", 13, "bold"),
        "relief": "solid",
        "bd": 2,
        "highlightbackground": "black",
        "highlightcolor": "black",
        "highlightthickness": 1,
        "padx": 12,
        "pady": 7,
    }
    tk.Label(controls, text="Period:", bg=SUMMARY_BG, fg=TEXT_PRIMARY,
             font=("Arial", 15, "bold")).pack(side="left", padx=(0, 8))
    for period in ("Day", "Week", "Month"):
        tk.Radiobutton(controls, text=period, variable=period_var, value=period,
                       bg=SUMMARY_BG, fg=TEXT_PRIMARY, font=("Arial", 14),
                       command=load_summary).pack(side="left", padx=5)

    tk.Label(controls, text="Date:", bg=SUMMARY_BG, fg=TEXT_PRIMARY,
             font=("Arial", 15, "bold")).pack(side="left", padx=(24, 8))
    date_entry = tk.Entry(controls, textvariable=date_var, width=13, font=("Arial", 14), relief="solid", bd=2)
    date_entry.pack(side="left", padx=4)
    tk.Button(controls, text="Calendar", command=lambda: open_date_calendar(summary_win, date_var),
              bg=PRIMARY, **summary_button_options).pack(side="left", padx=4)
    tk.Button(controls, text="Apply", command=load_summary, bg=PRIMARY,
              **summary_button_options).pack(side="left", padx=4)
    tk.Button(controls, text="Close", command=summary_win.destroy, bg="#dc2626",
              **summary_button_options).pack(side="right")

    # Build title, totals, export action, and summary table.
    tk.Label(summary_win, textvariable=title_var, bg=SUMMARY_BG, fg=PRIMARY,
             font=("Arial", 18, "bold")).pack(anchor="w", padx=16)
    tk.Label(summary_win, textvariable=totals_var, bg=SUMMARY_BG, fg=TEXT_PRIMARY,
             font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=(2, 8))

    action_row = tk.Frame(summary_win, bg=SUMMARY_BG)
    action_row.pack(fill="x", padx=16, pady=(0, 8))
    tk.Button(action_row, text="Preview / Convert PDF", command=open_preview, bg="#059669", fg="white",
              font=("Arial", 11, "bold"), relief="flat", padx=14, pady=8).pack(side="left")

    table_frame = tk.Frame(summary_win, bg=BG_CARD)
    table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
    summary_tree = create_summary_tree(table_frame, "SalesSummary.Treeview")

    # Load initial transaction summary data.
    load_summary()
    center_window(summary_win, 1120, 650, parent)


def open_most_items_summary(parent):
    # Open the most-items-sold summary window.
    summary_win = tk.Toplevel(parent)
    summary_win.title("Most Items Sold Summary")
    summary_win.configure(bg=SUMMARY_BG)
    summary_win.transient(parent)

    # Store selected filters, title, and totals for the item summary.
    period_var = tk.StringVar(value="Day")
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    title_var = tk.StringVar()
    totals_var = tk.StringVar()

    # Define most-items summary columns and width limits.
    headings = [
        ("item", "Item Name", 260, 520, "w"),
        ("qty", "Items Sold", 120, 170, "e"),
        ("sales", "Sales Count", 120, 170, "e"),
        ("total", "Total Sales", 140, 190, "e"),
        ("latest", "Latest Sale", 190, 260, "w"),
        ("user", "User", 110, 180, "w"),
    ]

    def title_text():
        # Build the most-items summary title from period and date.
        start, end = compute_summary_range(period_var.get(), date_var.get())
        if period_var.get() == "Day":
            return f"Most Items Sold - {start.strftime('%B %d, %Y')}"
        if period_var.get() == "Week":
            return f"Most Items Sold - {start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
        return f"Most Items Sold - {start.strftime('%B %Y')}"

    def clear_tree(tree):
        # Remove all rows from a summary Treeview.
        for item in tree.get_children():
            tree.delete(item)

    def adjust_columns(tree):
        # Measure visible rows and resize most-items summary columns.
        tree.update_idletasks()
        body_font = tkfont.Font(family="Arial", size=12)
        heading_font = tkfont.Font(family="Arial", size=11, weight="bold")
        widths = {}
        for index, (col, heading, min_width, max_width, _anchor) in enumerate(headings):
            widest = heading_font.measure(heading)
            for item in tree.get_children():
                values = tree.item(item, "values")
                if index < len(values):
                    widest = max(widest, body_font.measure(str(values[index])))
            widths[col] = min(max(widest + 34, min_width), max_width)
        total_width = sum(widths.values())
        available_width = max(tree.winfo_width() - 24, total_width)
        if total_width < available_width:
            extra = (available_width - total_width) // max(len(headings), 1)
            for col in widths:
                widths[col] += extra
        for col, _heading, _min_width, _max_width, anchor in headings:
            tree.column(col, width=widths[col], minwidth=widths[col], anchor=anchor, stretch=True)

    def create_tree(parent_frame, style_name):
        # Create a styled most-items Treeview with scrollbars.
        columns = tuple(col for col, *_rest in headings)
        style = ttk.Style()
        style.configure(style_name, font=("Arial", 12), rowheight=34, background=BG_CARD, fieldbackground=BG_CARD)
        style.configure(f"{style_name}.Heading", font=("Arial", 11, "bold"), foreground=TEXT_PRIMARY)
        tree = ttk.Treeview(parent_frame, columns=columns, show="headings", style=style_name)
        vsb = ttk.Scrollbar(parent_frame, orient="vertical", command=tree.yview)
        hsb = ttk.Scrollbar(parent_frame, orient="horizontal", command=tree.xview)
        tree.configure(yscrollcommand=vsb.set, xscrollcommand=hsb.set)
        tree.grid(row=0, column=0, sticky="nsew")
        vsb.grid(row=0, column=1, sticky="ns")
        hsb.grid(row=1, column=0, sticky="ew")
        parent_frame.grid_rowconfigure(0, weight=1)
        parent_frame.grid_columnconfigure(0, weight=1)
        for col, heading, min_width, _max_width, anchor in headings:
            tree.heading(col, text=heading)
            tree.column(col, width=min_width, minwidth=min_width, anchor=anchor, stretch=True)
        tree.tag_configure("even", background="#e0f2fe")
        tree.tag_configure("odd", background="#ffffff")
        return tree

    def load_summary():
        # Reload most-items rows and totals for the selected period.
        start, end = compute_summary_range(period_var.get(), date_var.get())
        data = fetch_most_items_summary(start, end)
        clear_tree(summary_tree)
        if not data["items"]:
            # Show an empty row when no items were sold in the selected period.
            summary_tree.insert(
                "",
                "end",
                values=("No items sold for the selected period.", "", "", "", "", ""),
                tags=("even",),
            )
        for index, row in enumerate(data["items"]):
            # Insert each item row with formatted quantity and sales totals.
            item_name, qty, sales_count, total_sales, latest_ts, user = row
            summary_tree.insert(
                "",
                "end",
                values=(item_name, f"{qty:,}", f"{sales_count:,}", money(total_sales), format_dashboard_datetime(latest_ts), user or "Admin"),
                tags=("even" if index % 2 == 0 else "odd",),
            )
        adjust_columns(summary_tree)
        title_var.set(title_text())
        totals_var.set(
            f"Items: {data['item_count']:,}   |   Items Sold: {data['total_qty']:,}   |   Total Sales: {money(data['total_sales'])}"
        )

    def build_pdf(file_path, title, rows):
        # Build a PDF export for the most-items-sold summary.
        try:
            from reportlab.lib import colors
            from reportlab.lib.pagesizes import letter, landscape
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import inch
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
        except ImportError as exc:
            raise RuntimeError("ReportLab is required to export PDF. Install it with: pip install reportlab") from exc

        # Build the PDF table rows and fallback empty row.
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "MostItemsSummaryTitle",
            parent=styles["Heading1"],
            textColor=colors.HexColor(PRIMARY),
            fontSize=18,
            alignment=1,
            spaceAfter=10,
        )
        table_data = [["Item Name", "Items Sold", "Sales Count", "Total Sales", "Latest Sale", "User"]]
        table_data.extend(list(row) for row in rows)
        if len(table_data) == 1:
            table_data.append(["No items sold", "", "", "", "", ""])
        doc = SimpleDocTemplate(file_path, pagesize=landscape(letter), topMargin=0.45*inch, bottomMargin=0.45*inch)
        table = Table(table_data, colWidths=[2.6*inch, 0.9*inch, 1.0*inch, 1.2*inch, 1.8*inch, 1.1*inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PRIMARY)),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 8),
            ("ALIGN", (1, 1), (3, -1), "RIGHT"),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#eff6ff")]),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ]))
        story = [
            Paragraph(title, title_style),
            Paragraph(totals_var.get(), styles["Normal"]),
            Spacer(1, 0.12*inch),
            table,
            Spacer(1, 0.12*inch),
            Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]),
        ]
        doc.build(story)

    def open_preview():
        # Open a preview window before exporting most-items data to PDF.
        load_summary()
        rows = [summary_tree.item(item, "values") for item in summary_tree.get_children()]
        preview = tk.Toplevel(summary_win)
        preview.title("Most Items Sold Preview")
        preview.configure(bg=SUMMARY_BG)
        preview.transient(summary_win)
        # Build the preview table and totals display.
        tk.Label(preview, text=title_var.get(), bg=SUMMARY_BG, fg=PRIMARY,
                 font=("Arial", 18, "bold")).pack(anchor="w", padx=16, pady=(14, 4))
        tk.Label(preview, text=totals_var.get(), bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=(0, 8))
        preview_frame = tk.Frame(preview, bg=BG_CARD)
        preview_frame.pack(fill="both", expand=True, padx=16, pady=(0, 10))
        preview_tree = create_tree(preview_frame, "MostItemsPreview.Treeview")
        for index, row in enumerate(rows):
            preview_tree.insert("", "end", values=row, tags=("even" if index % 2 == 0 else "odd",))
        adjust_columns(preview_tree)
        actions = tk.Frame(preview, bg=SUMMARY_BG)
        actions.pack(fill="x", padx=16, pady=(0, 14))

        def save_pdf():
            # Ask where to save the PDF and export the preview rows.
            file_path = filedialog.asksaveasfilename(
                parent=preview,
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"most_items_sold_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            )
            if not file_path:
                return
            try:
                build_pdf(file_path, title_var.get(), rows)
                messagebox.showinfo(
                    "PDF Downloaded Successfully",
                    f"The PDF has been downloaded successfully.\n\nSaved to:\n{file_path}",
                    parent=preview,
                )
                preview.destroy()
            except Exception as exc:
                messagebox.showerror("Export Failed", str(exc), parent=preview)

        tk.Button(actions, text="Save as PDF", command=save_pdf, bg="#059669", fg="white",
                  font=("Arial", 11, "bold"), relief="flat", padx=14, pady=8).pack(side="right", padx=5)
        tk.Button(actions, text="Close Preview", command=preview.destroy, bg="#64748b", fg="white",
                  font=("Arial", 11, "bold"), relief="flat", padx=14, pady=8).pack(side="right", padx=5)
        center_window(preview, 980, 560, summary_win)

    # Build filter controls for period and date.
    controls = tk.Frame(summary_win, bg=SUMMARY_BG)
    controls.pack(fill="x", padx=16, pady=(14, 8))
    button_options = {
        "fg": "white",
        "font": ("Arial", 13, "bold"),
        "relief": "solid",
        "bd": 2,
        "highlightbackground": "black",
        "highlightcolor": "black",
        "highlightthickness": 1,
        "padx": 12,
        "pady": 7,
    }
    tk.Label(controls, text="Period:", bg=SUMMARY_BG, fg=TEXT_PRIMARY,
             font=("Arial", 15, "bold")).pack(side="left", padx=(0, 8))
    for period in ("Day", "Week", "Month"):
        tk.Radiobutton(controls, text=period, variable=period_var, value=period,
                       bg=SUMMARY_BG, fg=TEXT_PRIMARY, font=("Arial", 14),
                       command=load_summary).pack(side="left", padx=5)
    tk.Label(controls, text="Date:", bg=SUMMARY_BG, fg=TEXT_PRIMARY,
             font=("Arial", 15, "bold")).pack(side="left", padx=(24, 8))
    tk.Entry(controls, textvariable=date_var, width=13, font=("Arial", 14), relief="solid", bd=2).pack(side="left", padx=4)
    tk.Button(controls, text="Calendar", command=lambda: open_date_calendar(summary_win, date_var),
              bg=PRIMARY, **button_options).pack(side="left", padx=4)
    tk.Button(controls, text="Apply", command=load_summary, bg=PRIMARY,
              **button_options).pack(side="left", padx=4)
    tk.Button(controls, text="Close", command=summary_win.destroy, bg="#dc2626",
              **button_options).pack(side="right")

    # Build title, totals, export action, and summary table.
    tk.Label(summary_win, textvariable=title_var, bg=SUMMARY_BG, fg=PRIMARY,
             font=("Arial", 18, "bold")).pack(anchor="w", padx=16)
    tk.Label(summary_win, textvariable=totals_var, bg=SUMMARY_BG, fg=TEXT_PRIMARY,
             font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=(2, 8))
    action_row = tk.Frame(summary_win, bg=SUMMARY_BG)
    action_row.pack(fill="x", padx=16, pady=(0, 8))
    tk.Button(action_row, text="Preview / Convert PDF", command=open_preview, bg="#059669", fg="white",
              font=("Arial", 11, "bold"), relief="flat", padx=14, pady=8).pack(side="left")
    table_frame = tk.Frame(summary_win, bg=BG_CARD)
    table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
    summary_tree = create_tree(table_frame, "MostItemsSummary.Treeview")
    # Load initial most-items summary data.
    load_summary()
    center_window(summary_win, 980, 620, parent)
