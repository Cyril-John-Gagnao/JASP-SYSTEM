import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import sqlite3
import os
from datetime import datetime, timedelta
from io import BytesIO

# Try to import reportlab for PDF generation
try:
    from reportlab.lib.pagesizes import letter, A4
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

DB_NAME = os.path.join(os.path.dirname(__file__), "jasp.db")

# Color scheme (consistent with main_dashboard.py) + Report specific colors
BG_PAGE = "#edeff3"
BG_SIDEBAR = "#273142"
BG_CARD = "#ffffff"
TEXT_PRIMARY = "#1f2933"
TEXT_MUTED = "#6b7280"
ACCENT = "#f5f6fa"
LINE = "#e5e7eb"
HEADER_BG = "#354657"
HEADER_FG = "#ffffff"
HIGHLIGHT_BG = "#ffff00"
HIGHLIGHT_FG = "#000000"
SUMMARY_BG = "#d9e3f0"
TABLE_HEADER_BG = "#354657"
TABLE_HEADER_FG = "#ffffff"


def spacer(parent, h=12):
    """Create vertical spacer."""
    tk.Frame(parent, height=h, bg=parent["bg"]).pack(fill="x")


def stat_card(parent, title, value, subtitle=""):
    """Create a stat card widget."""
    card = tk.Frame(parent, bg=BG_CARD, bd=0, relief="flat",
                    highlightthickness=1, highlightbackground=LINE)
    card.pack(side="left", expand=True, fill="both", padx=8)

    tk.Label(card, text=title.upper(), bg=BG_CARD, fg=TEXT_MUTED,
             font=("Arial", 10, "bold")).pack(anchor="w", padx=16, pady=(14, 2))
    tk.Label(card, text=value, bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 22, "bold")).pack(anchor="w", padx=16)
    if subtitle:
        tk.Label(card, text=subtitle, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Arial", 9)).pack(anchor="w", padx=16, pady=(0, 14))
    return card


def build_table(parent, columns, rows):
    """Build a styled table widget."""
    style = ttk.Style()
    style.configure("Reports.Treeview", font=("Arial", 9), rowheight=24,
                    background=BG_CARD, fieldbackground=BG_CARD)
    style.configure("Reports.Treeview.Heading", font=("Arial", 10, "bold"), foreground=TEXT_PRIMARY)
    style.map("Reports.Treeview", background=[("selected", ACCENT)])

    tree = ttk.Treeview(parent, columns=columns, show="headings", style="Reports.Treeview", height=10)
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
    """Render a table when rows exist; otherwise show a muted empty-state message."""
    if rows:
        build_table(container, columns, rows)
    else:
        tk.Label(container, text=empty_text, bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Arial", 11, "italic")).pack(expand=True, fill="both", pady=12)


def init_database():
    """Initialize database tables for reporting."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Sales table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sales (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            raw_price REAL DEFAULT 0,
            total REAL NOT NULL,
            ts TEXT NOT NULL
        )
    """)

    # Expenses table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            category TEXT NOT NULL,
            description TEXT,
            amount REAL NOT NULL,
            ts TEXT NOT NULL
        )
    """)

    # CHB Production table (aligned with chb_dashboard.py schema)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS chb_production (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            production_date TEXT,
            worker_name TEXT,
            cement_bags INTEGER,
            fine_sand REAL,
            total_blocks INTEGER,
            pay REAL,
            pay_rate REAL DEFAULT 200,
            ts TEXT
        )
    """)

    # Backfill columns for older databases created by previous report versions.
    cursor.execute("PRAGMA table_info(chb_production)")
    chb_cols = {col[1] for col in cursor.fetchall()}
    chb_migrations = {
        "production_date": "ALTER TABLE chb_production ADD COLUMN production_date TEXT",
        "worker_name": "ALTER TABLE chb_production ADD COLUMN worker_name TEXT",
        "cement_bags": "ALTER TABLE chb_production ADD COLUMN cement_bags INTEGER",
        "fine_sand": "ALTER TABLE chb_production ADD COLUMN fine_sand REAL",
        "total_blocks": "ALTER TABLE chb_production ADD COLUMN total_blocks INTEGER",
        "pay": "ALTER TABLE chb_production ADD COLUMN pay REAL",
        "pay_rate": "ALTER TABLE chb_production ADD COLUMN pay_rate REAL DEFAULT 200",
        "ts": "ALTER TABLE chb_production ADD COLUMN ts TEXT",
    }
    for col_name, migration_sql in chb_migrations.items():
        if col_name not in chb_cols:
            cursor.execute(migration_sql)

    # Inventory table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            quantity INTEGER NOT NULL,
            price REAL NOT NULL,
            raw_price REAL DEFAULT 0
        )
    """)

    conn.commit()
    conn.close()


def get_date_range(start_date, end_date):
    """Validate and return date range."""
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        if start > end:
            return None, "Start date must be before end date."
        return (start, end), None
    except ValueError as e:
        return None, f"Invalid date format: {e}"


def generate_financial_summary(start_date, end_date):
    """REQ-REP-01: Generate Financial Summary Report."""
    date_range, error = get_date_range(start_date, end_date)
    if error:
        return None, error

    start_dt, end_dt = date_range
    opening_date = (start_dt - timedelta(days=1)).strftime("%Y-%m-%d")

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Total sales
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) FROM sales
        WHERE DATE(ts) BETWEEN ? AND ?
    """, (start_date, end_date))
    total_sales = cursor.fetchone()[0] or 0

    # Total expenses
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM expenses
        WHERE DATE(ts) BETWEEN ? AND ?
    """, (start_date, end_date))
    total_expenses = cursor.fetchone()[0] or 0

    # CHB payouts (assume from expenses with category 'CHB Payout')
    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM expenses
        WHERE category = 'CHB Payout' AND DATE(ts) BETWEEN ? AND ?
    """, (start_date, end_date))
    chb_payouts = cursor.fetchone()[0] or 0

    # Cash movement within selected period
    cash_on_hand = total_sales - total_expenses

    # Opening cash on hand as of day before selected start date
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) FROM sales
        WHERE DATE(ts) <= ?
    """, (opening_date,))
    opening_sales = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT COALESCE(SUM(amount), 0) FROM expenses
        WHERE DATE(ts) <= ?
    """, (opening_date,))
    opening_expenses = cursor.fetchone()[0] or 0

    opening_cash_on_hand = opening_sales - opening_expenses
    new_cash_on_hand = opening_cash_on_hand + cash_on_hand

    # Detailed sales transactions for the selected date range
    cursor.execute("""
        SELECT ts, item_name, qty, price, COALESCE(raw_price, 0), total
        FROM sales
        WHERE DATE(ts) BETWEEN ? AND ?
        ORDER BY ts ASC, id ASC
    """, (start_date, end_date))
    sales_transactions = cursor.fetchall()

    # Product-level sales summary (useful for quick overview)
    cursor.execute("""
        SELECT item_name, COALESCE(SUM(qty), 0) as qty_sold, COALESCE(SUM(total), 0) as amount_sold
        FROM sales
        WHERE DATE(ts) BETWEEN ? AND ?
        GROUP BY item_name
        ORDER BY amount_sold DESC, item_name ASC
    """, (start_date, end_date))
    sales_by_product = cursor.fetchall()

    # Detailed expenses transactions for the selected date range
    cursor.execute("""
        SELECT ts, category, COALESCE(description, ''), amount
        FROM expenses
        WHERE DATE(ts) BETWEEN ? AND ?
        ORDER BY ts ASC, id ASC
    """, (start_date, end_date))
    expense_transactions = cursor.fetchall()

    # Expense summary rows for the expense spreadsheet section
    cursor.execute("""
        SELECT DATE(ts) as expense_date,
               CASE
                   WHEN TRIM(COALESCE(description, '')) = '' THEN category
                   ELSE description
               END as expense_name,
               COALESCE(SUM(amount), 0) as total_amount,
               COALESCE(category, '') as remarks
        FROM expenses
        WHERE DATE(ts) BETWEEN ? AND ?
        GROUP BY DATE(ts), expense_name, category
        ORDER BY DATE(ts) ASC, expense_name ASC
    """, (start_date, end_date))
    expense_summary_rows = cursor.fetchall()

    conn.close()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_sales": total_sales,
        "total_expenses": total_expenses,
        "chb_payouts": chb_payouts,
        "cash_on_hand": cash_on_hand,
        "opening_date": opening_date,
        "opening_cash_on_hand": opening_cash_on_hand,
        "new_cash_on_hand": new_cash_on_hand,
        "sales_transactions": sales_transactions,
        "sales_by_product": sales_by_product,
        "expense_transactions": expense_transactions,
        "expense_summary_rows": expense_summary_rows,
    }, None


def generate_weekly_sales(end_date_str):
    """REQ-REP-02: Generate Weekly Sales Statistics Report."""
    try:
        end_date = datetime.strptime(end_date_str, "%Y-%m-%d")
        start_date = end_date - timedelta(days=6)
    except ValueError:
        return None, "Invalid date format."

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    weekly_data = []
    for i in range(7):
        current_date = start_date + timedelta(days=i)
        date_str = current_date.strftime("%Y-%m-%d")
        day_name = current_date.strftime("%A")

        cursor.execute("""
            SELECT COALESCE(SUM(total), 0) FROM sales
            WHERE DATE(ts) = ?
        """, (date_str,))
        daily_revenue = cursor.fetchone()[0] or 0
        weekly_data.append((day_name, date_str, daily_revenue))

    conn.close()

    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "daily_data": weekly_data,
    }, None


def generate_chb_production(start_date, end_date):
    """REQ-REP-03: Generate CHB Production Report."""
    date_range, error = get_date_range(start_date, end_date)
    if error:
        return None, error

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(chb_production)")
    col_names = {col[1] for col in cursor.fetchall()}

    # Support both old report schema and the CHB dashboard schema.
    if {"cement_consumed", "blocks_produced"}.issubset(col_names):
        cement_col = "cement_consumed"
        blocks_col = "blocks_produced"
    elif {"cement_bags", "total_blocks"}.issubset(col_names):
        cement_col = "cement_bags"
        blocks_col = "total_blocks"
    else:
        conn.close()
        return None, "CHB table schema is incompatible for reporting."

    if "ts" in col_names and "production_date" in col_names:
        date_expr = "DATE(COALESCE(ts, production_date))"
        date_select = "COALESCE(ts, production_date)"
        date_order = "COALESCE(ts, production_date)"
    elif "ts" in col_names:
        date_expr = "DATE(ts)"
        date_select = "ts"
        date_order = "ts"
    elif "production_date" in col_names:
        date_expr = "DATE(production_date)"
        date_select = "production_date"
        date_order = "production_date"
    else:
        conn.close()
        return None, "CHB table has no date field (ts/production_date)."

    cursor.execute(f"""
        SELECT
            COALESCE(SUM({cement_col}), 0) as total_cement,
            COALESCE(SUM({blocks_col}), 0) as total_blocks
        FROM chb_production
        WHERE {date_expr} BETWEEN ? AND ?
    """, (start_date, end_date))
    result = cursor.fetchone()
    total_cement = result[0] or 0
    total_blocks = result[1] or 0

    # Get detailed entries
    cursor.execute(f"""
        SELECT {date_select}, {cement_col}, {blocks_col}
        FROM chb_production
        WHERE {date_expr} BETWEEN ? AND ?
        ORDER BY {date_order} DESC, id DESC
    """, (start_date, end_date))
    entries = cursor.fetchall()

    conn.close()

    # Calculate efficiency metrics
    efficiency = (total_blocks / total_cement * 100) if total_cement > 0 else 0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_cement": total_cement,
        "total_blocks": total_blocks,
        "efficiency": efficiency,
        "entries": entries,
    }, None


def generate_inventory_status():
    """REQ-REP-04: Generate Inventory Status Report."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT name, quantity, price FROM items
        ORDER BY quantity ASC
    """)
    all_items = cursor.fetchall()

    low_stock = [(name, qty, price) for name, qty, price in all_items if qty < 10]

    conn.close()

    return {
        "all_items": all_items,
        "low_stock": low_stock,
        "total_items": len(all_items),
    }, None


def export_to_pdf(report_type, report_data):
    """REQ-REP-05: Export report to PDF."""
    if not HAS_REPORTLAB:
        return False, "ReportLab not installed. Install with: pip install reportlab"

    try:
        file_path = filedialog.asksaveasfilename(
            defaultextension=".pdf",
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
            initialfile=f"{report_type}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        )
        if not file_path:
            return False, "Export cancelled."

        # Create PDF
        pdf = SimpleDocTemplate(file_path, pagesize=letter,
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()

        # Title
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=20,
            textColor=colors.HexColor("#1f2933"),
            spaceAfter=12
        )
        story.append(Paragraph(f"{report_type} Report", title_style))
        story.append(Spacer(1, 0.2*inch))

        # Build content based on report type
        if report_type == "Financial Summary":
            _build_financial_pdf(story, report_data, styles)
        elif report_type == "Weekly Sales Statistics":
            _build_weekly_sales_pdf(story, report_data, styles)
        elif report_type == "CHB Production":
            _build_chb_production_pdf(story, report_data, styles)
        elif report_type == "Inventory Status":
            _build_inventory_pdf(story, report_data, styles)

        story.append(Spacer(1, 0.3*inch))
        footer = Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal'])
        story.append(footer)

        pdf.build(story)
        return True, f"Report exported successfully:\n{file_path}"
    except Exception as e:
        return False, f"PDF export failed: {str(e)}"


def _build_financial_pdf(story, data, styles):
    """Build financial summary PDF content."""
    story.append(Paragraph(f"Period: {data['start_date']} to {data['end_date']}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    summary_data = [
        ["Metric", "Amount (₱)"],
        ["Total Sales", f"{data['total_sales']:,.2f}"],
        ["Total Expenses", f"{data['total_expenses']:,.2f}"],
        ["CHB Payouts", f"{data['chb_payouts']:,.2f}"],
        ["Cash on Hand", f"{data['cash_on_hand']:,.2f}"],
    ]

    table = Table(summary_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)

    sales_by_product = data.get('sales_by_product', [])
    if sales_by_product:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Products Sold Summary", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))

        product_rows = [["Product", "Qty Sold", "Amount (₱)"]]
        for item_name, qty_sold, amount_sold in sales_by_product:
            product_rows.append([item_name, f"{int(qty_sold):,}", f"{amount_sold:,.2f}"])

        product_table = Table(product_rows, colWidths=[2.7*inch, 1.0*inch, 1.3*inch])
        product_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (1, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
        ]))
        story.append(product_table)

    sales_transactions = data.get('sales_transactions', [])
    if sales_transactions:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Sales Transactions", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))

        sales_rows = [["Date/Time", "Product", "Qty", "Amount (₱)"]]
        for ts, item_name, qty, _price, _raw_price, total in sales_transactions:
            sales_rows.append([str(ts)[:19], item_name, f"{int(qty):,}", f"{total:,.2f}"])

        sales_table = Table(sales_rows, colWidths=[1.5*inch, 2.1*inch, 0.7*inch, 1.2*inch])
        sales_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(sales_table)

    expense_transactions = data.get('expense_transactions', [])
    if expense_transactions:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Expense Transactions", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))

        expense_rows = [["Date/Time", "Category", "Description", "Amount (₱)"]]
        for ts, category, description, amount in expense_transactions:
            expense_rows.append([
                str(ts)[:19],
                category or "-",
                description or "-",
                f"{amount:,.2f}",
            ])

        expense_table = Table(expense_rows, colWidths=[1.3*inch, 1.1*inch, 2.0*inch, 1.1*inch])
        expense_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (3, 1), (3, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (2, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(expense_table)


def _build_weekly_sales_pdf(story, data, styles):
    """Build weekly sales PDF content."""
    story.append(Paragraph(f"Period: {data['start_date']} to {data['end_date']}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    sales_data = [["Day", "Date", "Revenue (₱)"]]
    for day, date, revenue in data['daily_data']:
        sales_data.append([day, date, f"{revenue:,.2f}"])

    table = Table(sales_data, colWidths=[1.5*inch, 1.5*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
    ]))
    story.append(table)


def _build_chb_production_pdf(story, data, styles):
    """Build CHB production PDF content."""
    story.append(Paragraph(f"Period: {data['start_date']} to {data['end_date']}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    summary_data = [
        ["Metric", "Value"],
        ["Total Cement Consumed (kg)", f"{data['total_cement']:,.2f}"],
        ["Total Blocks Produced (pcs)", f"{data['total_blocks']:,}"],
        ["Production Efficiency (%)", f"{data['efficiency']:.2f}%"],
    ]

    table = Table(summary_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
    ]))
    story.append(table)

    if data['entries']:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Detailed Entries", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))

        entries_data = [["Date/Time", "Cement (kg)", "Blocks (pcs)"]]
        for ts, cement, blocks in data['entries']:
            entries_data.append([ts, f"{cement:,.2f}", f"{blocks:,}"])

        entries_table = Table(entries_data, colWidths=[2*inch, 1.5*inch, 1.5*inch])
        entries_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTSIZE', (0, 0), (-1, -1), 9),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
        ]))
        story.append(entries_table)


def _build_inventory_pdf(story, data, styles):
    """Build inventory status PDF content."""
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    summary_data = [
        ["Metric", "Value"],
        ["Total Items", str(data['total_items'])],
        ["Low Stock Items", str(len(data['low_stock']))],
    ]

    table = Table(summary_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(table)

    if data['low_stock']:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Low Stock Items (< 10 pcs)", styles['Heading2']))
        story.append(Spacer(1, 0.1*inch))

        items_data = [["Item Name", "Quantity", "Price (₱)"]]
        for name, qty, price in data['low_stock']:
            items_data.append([name, str(qty), f"{price:,.2f}"])

        items_table = Table(items_data, colWidths=[2.5*inch, 1*inch, 1.5*inch])
        items_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('BACKGROUND', (0, 1), (-1, -1), colors.lightyellow),
        ]))
        story.append(items_table)

    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("All Inventory Items", styles['Heading2']))
    story.append(Spacer(1, 0.1*inch))

    all_items_data = [["Item Name", "Quantity", "Price (₱)"]]
    for name, qty, price in data['all_items']:
        all_items_data.append([name, str(qty), f"{price:,.2f}"])

    all_items_table = Table(all_items_data, colWidths=[2.5*inch, 1*inch, 1.5*inch])
    all_items_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#273142")),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.black),
    ]))
    story.append(all_items_table)


# ================= FIX: CENTERED FULL-WIDTH SCROLLABLE FRAME HELPER =================
def create_centered_scrollable_frame(parent):
    """
    Creates a canvas with a scrollable frame that automatically updates
    to span 95% of the canvas width and stays centered.
    """
    canvas = tk.Canvas(parent, bg=BG_PAGE, highlightthickness=0)
    scrollbar = ttk.Scrollbar(parent, orient="vertical", command=canvas.yview)
    scrollable_frame = tk.Frame(canvas, bg=BG_PAGE)

    # Update scroll region when inner frame contents change
    scrollable_frame.bind(
        "<Configure>",
        lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
    )

    # Place window anchored at top-center ('n')
    window_id = canvas.create_window((0, 0), window=scrollable_frame, anchor="n")

    # Update inner frame width to match canvas and center it on resize
    def on_canvas_configure(e):
        # Set to 95% width for a "near full width" look with slight side margins
        canvas.itemconfig(window_id, width=e.width * 0.95)
        # Re-center based on new width
        canvas.coords(window_id, (e.width / 2, 0))

    canvas.bind("<Configure>", on_canvas_configure)
    canvas.configure(yscrollcommand=scrollbar.set)

    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    return scrollable_frame
# ===================================================================================


def open_reports():
    """Open Reports & Analytics Dashboard in a new window."""
    reports_window = tk.Toplevel()
    reports_window.title("Reports & Analytics")
    reports_window.state("zoomed")
    reports_window.configure(bg=BG_PAGE)

    init_database()

    # ================= HEADER =================
    header = tk.Frame(reports_window, bg=BG_CARD, height=64, highlightthickness=1,
                      highlightbackground=LINE)
    header.pack(fill="x")
    tk.Label(header, text="Reports & Analytics", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 18, "bold")).pack(side="left", padx=20, pady=14)
    
    tk.Button(header, text="← Back", bg="#dc2626", fg="white",
              font=("Arial", 10, "bold"), relief="flat", bd=0,
              padx=12, pady=8,
              activebackground="#b91c1c",
              command=reports_window.destroy).pack(side="right", padx=14, pady=10)

    # ================= MAIN CONTENT =================
    content = tk.Frame(reports_window, bg=BG_PAGE)
    content.pack(fill="both", expand=True, pady=18)

    # Create notebook (tabs)
    notebook = ttk.Notebook(content)
    notebook.pack(fill="both", expand=True)

    # Tab 1: Financial Summary
    fin_frame = tk.Frame(notebook, bg=BG_PAGE)
    notebook.add(fin_frame, text="Financial Summary")
    _build_financial_summary_tab(fin_frame)

    # Tab 2: Weekly Sales
    weekly_frame = tk.Frame(notebook, bg=BG_PAGE)
    notebook.add(weekly_frame, text="Weekly Sales")
    _build_weekly_sales_tab(weekly_frame)

    # Tab 3: CHB Production
    chb_frame = tk.Frame(notebook, bg=BG_PAGE)
    notebook.add(chb_frame, text="CHB Production")
    _build_chb_production_tab(chb_frame)

    # Tab 4: Inventory Status
    inventory_frame = tk.Frame(notebook, bg=BG_PAGE)
    notebook.add(inventory_frame, text="Inventory Status")
    _build_inventory_status_tab(inventory_frame)


def _build_financial_summary_tab(parent):
    """Build Financial Summary Report tab with centered, full-width layout."""
    # Replaced manual canvas setup with centered helper
    scrollable_frame = create_centered_scrollable_frame(parent)

    # Date range selection
    selection_frame = tk.Frame(scrollable_frame, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=LINE, padx=16, pady=12)
    selection_frame.pack(fill="both", expand=False, pady=12, padx=12)

    tk.Label(selection_frame, text="Period Selection", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

    date_frame = tk.Frame(selection_frame, bg=BG_CARD)
    date_frame.pack(fill="x")

    tk.Label(date_frame, text="Start Date:", bg=BG_CARD, font=("Arial", 9)).pack(side="left", padx=(0, 8))
    start_entry = tk.Entry(date_frame, width=13, font=("Arial", 9))
    start_entry.pack(side="left", padx=(0, 16))
    start_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))

    tk.Label(date_frame, text="End Date:", bg=BG_CARD, font=("Arial", 9)).pack(side="left", padx=(0, 8))
    end_entry = tk.Entry(date_frame, width=13, font=("Arial", 9))
    end_entry.pack(side="left", padx=(0, 16))
    end_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

    def generate_report():
        start = start_entry.get()
        end = end_entry.get()
        data, error = generate_financial_summary(start, end)

        if error:
            messagebox.showerror("Error", error)
            return

        # Clear old report
        for widget in scrollable_frame.winfo_children()[1:]:
            widget.destroy()

        def money(val):
            return f"₱{val:,.2f}"

        def fmt_short_date(ts_value):
            text = str(ts_value or "")
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
                try:
                    dt = datetime.strptime(text[:19], fmt)
                    return dt.strftime("%m-%d-%y")
                except ValueError:
                    continue
            return text[:10]

        # Report Header (previous design)
        header_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        header_frame.pack(fill="x", pady=(12, 6), padx=12)

        tk.Label(header_frame, text="FINANCIAL SUMMARY REPORT", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 14, "bold")).pack(anchor="w")
        tk.Label(header_frame, text=f"Period: {start} to {end}", bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Arial", 9)).pack(anchor="w", pady=(2, 0))

        # Key Metrics Section (previous design)
        metrics_frame = tk.Frame(scrollable_frame, bg=SUMMARY_BG, padx=16, pady=12)
        metrics_frame.pack(fill="x", pady=6, padx=12)

        col1_frame = tk.Frame(metrics_frame, bg=SUMMARY_BG)
        col1_frame.pack(side="left", fill="both", expand=True, padx=(0, 16))

        tk.Label(col1_frame, text="TOTAL SALES", bg=SUMMARY_BG, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(col1_frame, text=money(data["total_sales"]), bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 12))

        tk.Label(col1_frame, text="TOTAL EXPENSES", bg=SUMMARY_BG, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(col1_frame, text=money(data["total_expenses"]), bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 12))

        col2_frame = tk.Frame(metrics_frame, bg=SUMMARY_BG)
        col2_frame.pack(side="left", fill="both", expand=True, padx=(16, 0))

        tk.Label(col2_frame, text="CHB PAYOUTS", bg=SUMMARY_BG, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(col2_frame, text=money(data["chb_payouts"]), bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 16, "bold")).pack(anchor="w", pady=(0, 12))

        # Cash on Hand (previous design)
        highlight_frame = tk.Frame(scrollable_frame, bg=HIGHLIGHT_BG, padx=16, pady=10)
        highlight_frame.pack(fill="x", pady=6, padx=12)

        tk.Label(highlight_frame, text="CASH ON HAND", bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG,
                 font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(highlight_frame, text=money(data["cash_on_hand"]), bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG,
                 font=("Arial", 20, "bold")).pack(anchor="w", pady=(4, 0))

        # Uniform table list (similar to other dashboard lists)
        items_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        items_frame.pack(fill="x", pady=6, padx=12)

        tk.Label(items_frame, text="ITEMS SOLD LIST", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        sales_rows = data.get("sales_transactions", [])
        if sales_rows:
            table_wrap = tk.Frame(items_frame, bg=BG_CARD)
            table_wrap.pack(fill="x")

            style = ttk.Style()
            style.configure("FinancialList.Treeview", font=("Arial", 10), rowheight=26,
                            background=BG_CARD, fieldbackground=BG_CARD)
            style.configure("FinancialList.Treeview.Heading", font=("Arial", 10, "bold"), foreground=TEXT_PRIMARY)
            style.map("FinancialList.Treeview", background=[("selected", ACCENT)])

            columns = (
                "date", "product", "unit", "price_purchased", "price_jasp",
                "qty", "total_purchased", "total_jasp", "markup"
            )
            tree = ttk.Treeview(table_wrap, columns=columns, show="headings", style="FinancialList.Treeview", height=8)

            headings = [
                ("date", "DATE", 110),
                ("product", "PRODUCT", 250),
                ("unit", "UNIT", 70),
                ("price_purchased", "PURCHASED", 120),
                ("price_jasp", "JASP", 110),
                ("qty", "QUANTITY", 110),
                ("total_purchased", "TOTAL PURCHASED", 150),
                ("total_jasp", "TOTAL JASP", 130),
                ("markup", "MARKED UP", 130),
            ]

            for col, title, width in headings:
                anchor = "w" if col in ("product",) else "center"
                tree.heading(col, text=title)
                tree.column(col, width=width, anchor=anchor, stretch=True)

            for ts, item_name, qty, jasp_unit_price, purchased_unit_price, jasp_total in sales_rows:
                qty_val = float(qty or 0)
                purchased_unit = float(purchased_unit_price or 0)
                jasp_unit = float(jasp_unit_price or 0)
                jasp_total_val = float(jasp_total or 0)
                purchased_total = purchased_unit * qty_val
                marked_up = jasp_total_val - purchased_total

                tree.insert(
                    "", "end",
                    values=(
                        fmt_short_date(ts),
                        str(item_name or "-"),
                        "pc",
                        money(purchased_unit),
                        money(jasp_unit),
                        f"{qty_val:,.2f}",
                        money(purchased_total),
                        money(jasp_total_val),
                        money(marked_up),
                    )
                )

            tree.pack(side="left", fill="x", expand=True)
            table_scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=table_scroll.set)
            table_scroll.pack(side="right", fill="y")
        else:
            tk.Label(items_frame, text="No sales found for selected date range.", bg=BG_CARD,
                     fg=TEXT_MUTED, font=("Arial", 10, "italic")).pack(anchor="w")

        # Expense table (uniform layout, placed under items list)
        expense_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        expense_frame.pack(fill="x", pady=6, padx=12)

        tk.Label(expense_frame, text="EXPENSE LIST", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        exp_rows = data.get("expense_summary_rows", [])
        if exp_rows:
            exp_wrap = tk.Frame(expense_frame, bg=BG_CARD)
            exp_wrap.pack(fill="x")

            exp_columns = ("date", "expense_name", "total_expense", "remarks")
            exp_tree = ttk.Treeview(exp_wrap, columns=exp_columns, show="headings", style="FinancialList.Treeview", height=6)

            exp_headings = [
                ("date", "DATE", 120),
                ("expense_name", "EXPENSE NAME", 420),
                ("total_expense", "TOTAL EXPENSE", 160),
                ("remarks", "REMARKS", 220),
            ]

            for col, title, width in exp_headings:
                anchor = "w" if col in ("expense_name", "remarks") else "center"
                exp_tree.heading(col, text=title)
                exp_tree.column(col, width=width, anchor=anchor, stretch=True)

            for expense_date, expense_name, total_amount, remarks in exp_rows:
                exp_tree.insert(
                    "", "end",
                    values=(
                        fmt_short_date(expense_date),
                        str(expense_name or "-"),
                        money(float(total_amount or 0)),
                        str(remarks or ""),
                    )
                )

            exp_tree.pack(side="left", fill="x", expand=True)
            exp_scroll = ttk.Scrollbar(exp_wrap, orient="vertical", command=exp_tree.yview)
            exp_tree.configure(yscrollcommand=exp_scroll.set)
            exp_scroll.pack(side="right", fill="y")
        else:
            tk.Label(expense_frame, text="No expenses found for selected date range.", bg=BG_CARD,
                     fg=TEXT_MUTED, font=("Arial", 10, "italic")).pack(anchor="w")

        subtotal_row = tk.Frame(expense_frame, bg=BG_CARD)
        subtotal_row.pack(fill="x", pady=(8, 0))
        tk.Label(subtotal_row, text="SUB-TOTAL", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 10, "bold"), anchor="e", padx=8, pady=4).pack(side="left", fill="x", expand=True)
        tk.Label(subtotal_row, text=money(data["total_expenses"]), bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 10, "bold"), anchor="e", padx=8, pady=4, width=18).pack(side="left")

        # Financial Summary table (placed under expense table)
        summary_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        summary_frame.pack(fill="x", pady=6, padx=12)

        tk.Label(summary_frame, text="FINANCIAL SUMMARY", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        summary_data = [
            ("Metric", "Amount"),
            (f"Cash on Hand as of {data['opening_date']}", money(data["opening_cash_on_hand"])),
            ("Cash In/Sales", money(data["total_sales"])),
            ("Cash Out/Expenses", f"-{money(data['total_expenses'])}"),
            (f"Cash on Hand as of {data['end_date']}", money(data["new_cash_on_hand"])),
        ]

        table_frame = tk.Frame(summary_frame, bg=BG_CARD)
        table_frame.pack(fill="x", pady=(0, 12))

        for idx, (metric, amount) in enumerate(summary_data):
            row_bg = HIGHLIGHT_BG if idx == len(summary_data) - 1 else BG_CARD
            row_frame = tk.Frame(table_frame, bg=row_bg)
            row_frame.pack(fill="x", pady=3)

            if idx == 0:
                tk.Label(row_frame, text=metric, bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                         font=("Arial", 9, "bold"), anchor="w", padx=8, pady=6).pack(side="left", fill="x", expand=True)
                tk.Label(row_frame, text=amount, bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                         font=("Arial", 9, "bold"), anchor="e", padx=8, pady=6, width=25).pack(side="left")
            else:
                tk.Label(row_frame, text=metric, bg=row_bg, fg=TEXT_PRIMARY,
                         font=("Arial", 10, "bold" if idx == len(summary_data) - 1 else "normal"),
                         anchor="w", padx=8, pady=4).pack(side="left", fill="x", expand=True)
                tk.Label(row_frame, text=amount, bg=row_bg, fg=TEXT_PRIMARY,
                         font=("Arial", 10, "bold"), anchor="e", padx=8, pady=4, width=25).pack(side="left")

        # Export button
        export_btn = tk.Button(
            summary_frame,
            text="📄 Export to PDF",
            command=lambda: _handle_export("Financial Summary", data),
            font=("Arial", 10, "bold"),
            bg="#2563eb",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=8
        )
        export_btn.pack(anchor="e", pady=(12, 0))

    gen_btn = tk.Button(selection_frame, text="Generate Report", command=generate_report,
                        font=("Arial", 10, "bold"), bg="#2563eb", fg="white",
                        relief="flat", bd=0, padx=12, pady=8)
    gen_btn.pack(anchor="e", pady=(10, 0))


def _build_weekly_sales_tab(parent):
    """Build Weekly Sales Statistics tab with full-width centered layout."""
    # Replaced manual canvas setup with centered helper
    scrollable_frame = create_centered_scrollable_frame(parent)

    # Date selection
    selection_frame = tk.Frame(scrollable_frame, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=LINE, padx=16, pady=12)
    selection_frame.pack(fill="x", expand=False, pady=12, padx=12)

    tk.Label(selection_frame, text="Period Selection (Last 7 Days)", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

    date_frame = tk.Frame(selection_frame, bg=BG_CARD)
    date_frame.pack(fill="x")

    tk.Label(date_frame, text="End Date:", bg=BG_CARD, font=("Arial", 9)).pack(side="left", padx=(0, 8))
    end_entry = tk.Entry(date_frame, width=13, font=("Arial", 9))
    end_entry.pack(side="left", padx=(0, 16))
    end_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

    def generate_report():
        data, error = generate_weekly_sales(end_entry.get())

        if error:
            messagebox.showerror("Error", error)
            return

        # Clear old report
        for widget in scrollable_frame.winfo_children()[1:]:
            widget.destroy()

        # Report Header
        header_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        header_frame.pack(fill="x", expand=False, pady=6, padx=12)

        tk.Label(header_frame, text="WEEKLY SALES STATISTICS REPORT", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 14, "bold")).pack(anchor="w")
        tk.Label(header_frame, text=f"Period: {data['start_date']} to {data['end_date']}", 
                 bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 9)).pack(anchor="w", pady=(2, 0))

        # Sales details table
        table_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        table_frame.pack(fill="x", expand=False, pady=6, padx=12)

        tk.Label(table_frame, text="DAILY REVENUE BREAKDOWN", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        # Calculate total weekly revenue
        total_revenue = sum(revenue for _, _, revenue in data["daily_data"])

        # Table headers
        header_row = tk.Frame(table_frame, bg=SUMMARY_BG)
        header_row.pack(fill="x", pady=(0, 4))

        tk.Label(header_row, text="Day", bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                 font=("Arial", 9, "bold"), width=20, anchor="w", padx=8, pady=6).pack(side="left", fill="x", expand=True)
        tk.Label(header_row, text="Date", bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                 font=("Arial", 9, "bold"), width=20, anchor="w", padx=8, pady=6).pack(side="left", fill="x", expand=True)
        tk.Label(header_row, text="Revenue (₱)", bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                 font=("Arial", 9, "bold"), width=25, anchor="e", padx=8, pady=6).pack(side="left")

        # Table rows
        for day, date, revenue in data["daily_data"]:
            row_frame = tk.Frame(table_frame, bg=BG_CARD)
            row_frame.pack(fill="x", pady=2)

            tk.Label(row_frame, text=day, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 9), width=20, anchor="w", padx=8, pady=4).pack(side="left", fill="x", expand=True)
            tk.Label(row_frame, text=date, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 9), width=20, anchor="w", padx=8, pady=4).pack(side="left", fill="x", expand=True)
            tk.Label(row_frame, text=f"₱{revenue:,.2f}", bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 9), width=25, anchor="e", padx=8, pady=4).pack(side="left")

        # Total row (highlighted)
        total_frame = tk.Frame(table_frame, bg=HIGHLIGHT_BG)
        total_frame.pack(fill="x", pady=(8, 0))

        tk.Label(total_frame, text="TOTAL", bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG,
                 font=("Arial", 9, "bold"), width=20, anchor="w", padx=8, pady=6).pack(side="left", fill="x", expand=True)
        tk.Label(total_frame, text="", bg=HIGHLIGHT_BG, width=20).pack(side="left", fill="x", expand=True)
        tk.Label(total_frame, text=f"₱{total_revenue:,.2f}", bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG,
                 font=("Arial", 10, "bold"), width=25, anchor="e", padx=8, pady=6).pack(side="left")

        # Export button
        export_btn = tk.Button(
            table_frame,
            text="📄 Export to PDF",
            command=lambda: _handle_export("Weekly Sales Statistics", data),
            font=("Arial", 10, "bold"),
            bg="#2563eb",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=8
        )
        export_btn.pack(anchor="e", pady=(12, 0))

    gen_btn = tk.Button(selection_frame, text="Generate Report", command=generate_report,
                        font=("Arial", 10, "bold"), bg="#2563eb", fg="white",
                        relief="flat", bd=0, padx=12, pady=8)
    gen_btn.pack(anchor="e", pady=(10, 0))


def _build_chb_production_tab(parent):
    """Build CHB Production Report tab with full-width centered layout."""
    # Replaced manual canvas setup with centered helper
    scrollable_frame = create_centered_scrollable_frame(parent)

    # Date range selection
    selection_frame = tk.Frame(scrollable_frame, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=LINE, padx=16, pady=12)
    selection_frame.pack(fill="x", expand=False, pady=12, padx=12)

    tk.Label(selection_frame, text="Period Selection", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

    date_frame = tk.Frame(selection_frame, bg=BG_CARD)
    date_frame.pack(fill="x")

    tk.Label(date_frame, text="Start Date:", bg=BG_CARD, font=("Arial", 9)).pack(side="left", padx=(0, 8))
    start_entry = tk.Entry(date_frame, width=13, font=("Arial", 9))
    start_entry.pack(side="left", padx=(0, 16))
    start_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))

    tk.Label(date_frame, text="End Date:", bg=BG_CARD, font=("Arial", 9)).pack(side="left", padx=(0, 8))
    end_entry = tk.Entry(date_frame, width=13, font=("Arial", 9))
    end_entry.pack(side="left", padx=(0, 16))
    end_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

    def generate_report():
        start = start_entry.get()
        end = end_entry.get()
        data, error = generate_chb_production(start, end)

        if error:
            messagebox.showerror("Error", error)
            return

        # Clear old report
        for widget in scrollable_frame.winfo_children()[1:]:
            widget.destroy()

        # Report Header
        header_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        header_frame.pack(fill="x", expand=False, pady=6, padx=12)

        tk.Label(header_frame, text="CHB PRODUCTION REPORT", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 14, "bold")).pack(anchor="w")
        tk.Label(header_frame, text=f"Period: {start} to {end}", bg=BG_CARD, fg=TEXT_MUTED,
                 font=("Arial", 9)).pack(anchor="w", pady=(2, 0))

        # Key Metrics Section
        metrics_frame = tk.Frame(scrollable_frame, bg=SUMMARY_BG, padx=16, pady=12)
        metrics_frame.pack(fill="x", expand=False, pady=6, padx=12)

        # Three columns for landscape
        col1_frame = tk.Frame(metrics_frame, bg=SUMMARY_BG)
        col1_frame.pack(side="left", fill="both", expand=True, padx=(0, 16))

        tk.Label(col1_frame, text="TOTAL CEMENT CONSUMED", bg=SUMMARY_BG, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(col1_frame, text=f"{data['total_cement']:,.2f} kg", bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 16, "bold")).pack(anchor="w")

        col2_frame = tk.Frame(metrics_frame, bg=SUMMARY_BG)
        col2_frame.pack(side="left", fill="both", expand=True, padx=(0, 16))

        tk.Label(col2_frame, text="TOTAL BLOCKS PRODUCED", bg=SUMMARY_BG, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(col2_frame, text=f"{data['total_blocks']:,} pcs", bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 16, "bold")).pack(anchor="w")

        col3_frame = tk.Frame(metrics_frame, bg=SUMMARY_BG)
        col3_frame.pack(side="left", fill="both", expand=True)

        tk.Label(col3_frame, text="PRODUCTION EFFICIENCY", bg=SUMMARY_BG, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(col3_frame, text=f"{data['efficiency']:.2f}%", bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 16, "bold")).pack(anchor="w")

        # Detailed entries if available
        if data['entries']:
            details_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
            details_frame.pack(fill="x", expand=False, pady=6, padx=12)

            tk.Label(details_frame, text="PRODUCTION DETAILS", bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

            # Table headers
            header_row = tk.Frame(details_frame, bg=SUMMARY_BG)
            header_row.pack(fill="x", pady=(0, 4))

            tk.Label(header_row, text="Date/Time", bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                     font=("Arial", 9, "bold"), width=30, anchor="w", padx=8, pady=6).pack(side="left", fill="x", expand=True)
            tk.Label(header_row, text="Cement (kg)", bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                     font=("Arial", 9, "bold"), width=20, anchor="e", padx=8, pady=6).pack(side="left")
            tk.Label(header_row, text="Blocks (pcs)", bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                     font=("Arial", 9, "bold"), width=20, anchor="e", padx=8, pady=6).pack(side="left")

            # Table rows
            for ts, cement, blocks in data["entries"]:
                row_frame = tk.Frame(details_frame, bg=BG_CARD)
                row_frame.pack(fill="x", pady=2)

                tk.Label(row_frame, text=ts, bg=BG_CARD, fg=TEXT_PRIMARY,
                         font=("Arial", 9), width=30, anchor="w", padx=8, pady=4).pack(side="left", fill="x", expand=True)
                tk.Label(row_frame, text=f"{cement:,.2f}", bg=BG_CARD, fg=TEXT_PRIMARY,
                         font=("Arial", 9), width=20, anchor="e", padx=8, pady=4).pack(side="left")
                tk.Label(row_frame, text=f"{blocks:,}", bg=BG_CARD, fg=TEXT_PRIMARY,
                         font=("Arial", 9), width=20, anchor="e", padx=8, pady=4).pack(side="left")

            # Export button
            export_btn = tk.Button(
                details_frame,
                text="📄 Export to PDF",
                command=lambda: _handle_export("CHB Production", data),
                font=("Arial", 10, "bold"),
                bg="#2563eb",
                fg="white",
                relief="flat",
                bd=0,
                padx=12,
                pady=8
            )
            export_btn.pack(anchor="e", pady=(12, 0))
        else:
            # Export button when no entries
            export_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
            export_frame.pack(fill="x", expand=False, pady=6, padx=12)

            export_btn = tk.Button(
                export_frame,
                text="📄 Export to PDF",
                command=lambda: _handle_export("CHB Production", data),
                font=("Arial", 10, "bold"),
                bg="#2563eb",
                fg="white",
                relief="flat",
                bd=0,
                padx=12,
                pady=8
            )
            export_btn.pack(anchor="e")

    gen_btn = tk.Button(selection_frame, text="Generate Report", command=generate_report,
                        font=("Arial", 10, "bold"), bg="#2563eb", fg="white",
                        relief="flat", bd=0, padx=12, pady=8)
    gen_btn.pack(anchor="e", pady=(10, 0))


def _build_inventory_status_tab(parent):
    """Build Inventory Status Report tab with full-width centered layout."""
    # Replaced manual canvas setup with centered helper
    scrollable_frame = create_centered_scrollable_frame(parent)

    # Button frame
    button_frame = tk.Frame(scrollable_frame, bg=BG_CARD, highlightthickness=1,
                            highlightbackground=LINE, padx=16, pady=12)
    button_frame.pack(fill="x", expand=False, pady=12, padx=12)

    tk.Label(button_frame, text="Inventory Status Report", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 11, "bold")).pack(anchor="w")

    def generate_report():
        data, error = generate_inventory_status()

        if error:
            messagebox.showerror("Error", error)
            return

        # Clear old report
        for widget in scrollable_frame.winfo_children()[1:]:
            widget.destroy()

        # Report Header
        header_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        header_frame.pack(fill="x", expand=False, pady=6, padx=12)

        tk.Label(header_frame, text="INVENTORY STATUS REPORT", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 14, "bold")).pack(anchor="w")
        tk.Label(header_frame, text=f"As of: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", 
                 bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 9)).pack(anchor="w", pady=(2, 0))

        # Summary Metrics
        metrics_frame = tk.Frame(scrollable_frame, bg=SUMMARY_BG, padx=16, pady=12)
        metrics_frame.pack(fill="x", expand=False, pady=6, padx=12)

        # Two columns for landscape
        col1_frame = tk.Frame(metrics_frame, bg=SUMMARY_BG)
        col1_frame.pack(side="left", fill="both", expand=True, padx=(0, 16))

        tk.Label(col1_frame, text="TOTAL ITEMS IN INVENTORY", bg=SUMMARY_BG, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(col1_frame, text=f"{data['total_items']:,}", bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 18, "bold")).pack(anchor="w")

        col2_frame = tk.Frame(metrics_frame, bg=SUMMARY_BG)
        col2_frame.pack(side="left", fill="both", expand=True)

        tk.Label(col2_frame, text="LOW STOCK ITEMS (< 10 pcs)", bg=SUMMARY_BG, fg=TEXT_MUTED,
                 font=("Arial", 9, "bold")).pack(anchor="w")
        tk.Label(col2_frame, text=f"{len(data['low_stock']):,}", bg=SUMMARY_BG, fg=TEXT_PRIMARY,
                 font=("Arial", 18, "bold")).pack(anchor="w")

        # Low Stock Section
        if data['low_stock']:
            low_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
            low_frame.pack(fill="x", expand=False, pady=6, padx=12)

            tk.Label(low_frame, text="⚠ LOW STOCK ALERTS", bg=BG_CARD, fg="#dc2626",
                     font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

            # Table headers
            header_row = tk.Frame(low_frame, bg="#ffcccc")
            header_row.pack(fill="x", pady=(0, 4))

            tk.Label(header_row, text="Item Name", bg="#ffcccc", fg="#7f1d1d",
                     font=("Arial", 9, "bold"), width=40, anchor="w", padx=8, pady=6).pack(side="left", fill="x", expand=True)
            tk.Label(header_row, text="Quantity", bg="#ffcccc", fg="#7f1d1d",
                     font=("Arial", 9, "bold"), width=15, anchor="e", padx=8, pady=6).pack(side="left")
            tk.Label(header_row, text="Price (₱)", bg="#ffcccc", fg="#7f1d1d",
                     font=("Arial", 9, "bold"), width=20, anchor="e", padx=8, pady=6).pack(side="left")

            # Table rows
            for name, qty, price in data["low_stock"]:
                row_frame = tk.Frame(low_frame, bg="#ffe5e5")
                row_frame.pack(fill="x", pady=2)

                tk.Label(row_frame, text=name, bg="#ffe5e5", fg=TEXT_PRIMARY,
                         font=("Arial", 9), width=40, anchor="w", padx=8, pady=4).pack(side="left", fill="x", expand=True)
                tk.Label(row_frame, text=str(qty), bg="#ffe5e5", fg=TEXT_PRIMARY,
                         font=("Arial", 9, "bold"), width=15, anchor="e", padx=8, pady=4).pack(side="left")
                tk.Label(row_frame, text=f"₱{price:,.2f}", bg="#ffe5e5", fg=TEXT_PRIMARY,
                         font=("Arial", 9), width=20, anchor="e", padx=8, pady=4).pack(side="left")

        # All Items Section
        all_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        all_frame.pack(fill="both", expand=True, pady=6, padx=12)

        tk.Label(all_frame, text="ALL INVENTORY ITEMS", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        # Table headers
        header_row = tk.Frame(all_frame, bg=SUMMARY_BG)
        header_row.pack(fill="x", pady=(0, 4))

        tk.Label(header_row, text="Item Name", bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                 font=("Arial", 9, "bold"), width=40, anchor="w", padx=8, pady=6).pack(side="left", fill="x", expand=True)
        tk.Label(header_row, text="Quantity", bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                 font=("Arial", 9, "bold"), width=15, anchor="e", padx=8, pady=6).pack(side="left")
        tk.Label(header_row, text="Price (₱)", bg=SUMMARY_BG, fg=TABLE_HEADER_FG,
                 font=("Arial", 9, "bold"), width=20, anchor="e", padx=8, pady=6).pack(side="left")

        # Table rows
        alternate_bg = False
        for name, qty, price in data["all_items"]:
            row_bg = "#f8f8f8" if alternate_bg else BG_CARD
            row_frame = tk.Frame(all_frame, bg=row_bg)
            row_frame.pack(fill="x", pady=1)

            tk.Label(row_frame, text=name, bg=row_bg, fg=TEXT_PRIMARY,
                     font=("Arial", 9), width=40, anchor="w", padx=8, pady=4).pack(side="left", fill="x", expand=True)
            tk.Label(row_frame, text=str(qty), bg=row_bg, fg=TEXT_PRIMARY,
                     font=("Arial", 9), width=15, anchor="e", padx=8, pady=4).pack(side="left")
            tk.Label(row_frame, text=f"₱{price:,.2f}", bg=row_bg, fg=TEXT_PRIMARY,
                     font=("Arial", 9), width=20, anchor="e", padx=8, pady=4).pack(side="left")
            
            alternate_bg = not alternate_bg

        # Export button
        export_frame = tk.Frame(scrollable_frame, bg=BG_CARD, padx=16, pady=12)
        export_frame.pack(fill="x", expand=False, pady=6, padx=12)

        export_btn = tk.Button(
            export_frame,
            text="📄 Export to PDF",
            command=lambda: _handle_export("Inventory Status", data),
            font=("Arial", 10, "bold"),
            bg="#2563eb",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=8
        )
        export_btn.pack(anchor="e")

    gen_btn = tk.Button(button_frame, text="Generate Report", command=generate_report,
                        font=("Arial", 10, "bold"), bg="#2563eb", fg="white",
                        relief="flat", bd=0, padx=12, pady=8)
    gen_btn.pack(anchor="e", pady=(10, 0))


def _handle_export(report_type, data):
    """Handle PDF export with user feedback."""
    success, message = export_to_pdf(report_type, data)
    if success:
        messagebox.showinfo("Success", message)
    else:
        messagebox.showerror("Export Failed", message)


if __name__ == "__main__":
    root = tk.Tk()
    open_reports()
    root.mainloop()