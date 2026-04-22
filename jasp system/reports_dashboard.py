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
NO_DATA_PERIOD_MESSAGE = "No data available for the selected period."
WORKER_PAYOUT_CATEGORY_NAMES = (
    "chb payout",
    "worker payout",
    "worker payouts",
    "payroll",
    "salary",
)


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


def _resolve_chb_date_fields(cursor):
    """Resolve CHB production date expressions for filtering/reporting."""
    cursor.execute("PRAGMA table_info(chb_production)")
    chb_cols = {col[1] for col in cursor.fetchall()}

    if "ts" in chb_cols and "production_date" in chb_cols:
        return "DATE(COALESCE(ts, production_date))", "COALESCE(ts, production_date)", "COALESCE(ts, production_date)", chb_cols
    if "ts" in chb_cols:
        return "DATE(ts)", "ts", "ts", chb_cols
    if "production_date" in chb_cols:
        return "DATE(production_date)", "production_date", "production_date", chb_cols
    return None, None, None, chb_cols


def generate_financial_summary(start_date, end_date):
    """REQ-REP-01: Generate Financial Summary Report."""
    _, error = get_date_range(start_date, end_date)
    if error:
        return None, error

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Total sales from completed/finalized transaction rows.
    # In this codebase, sales rows are inserted only during finalized POS checkout.
    cursor.execute("""
        SELECT COALESCE(SUM(total), 0) FROM sales
        WHERE ts IS NOT NULL
          AND qty > 0
          AND total >= 0
          AND DATE(ts) BETWEEN ? AND ?
    """, (start_date, end_date))
    total_sales = cursor.fetchone()[0] or 0

    # Material expenses (production materials) are pulled from expense rows,
    # excluding worker-payout categories to avoid double counting.
    payout_placeholders = ", ".join(["?"] * len(WORKER_PAYOUT_CATEGORY_NAMES))
    material_params = (start_date, end_date, *WORKER_PAYOUT_CATEGORY_NAMES)

    cursor.execute(f"""
        SELECT COALESCE(SUM(amount), 0) FROM expenses
        WHERE DATE(ts) BETWEEN ? AND ?
          AND amount > 0
          AND LOWER(TRIM(COALESCE(category, ''))) NOT IN ({payout_placeholders})
    """, material_params)
    material_expenses = cursor.fetchone()[0] or 0

    # Worker payouts are sourced from CHB production records (pay column).
    worker_payouts = 0
    worker_payout_transactions = []
    date_expr, date_select, date_order, chb_cols = _resolve_chb_date_fields(cursor)
    if date_expr and "pay" in chb_cols:
        cursor.execute(f"""
            SELECT COALESCE(SUM(pay), 0)
            FROM chb_production
            WHERE pay IS NOT NULL
              AND pay > 0
              AND {date_expr} BETWEEN ? AND ?
        """, (start_date, end_date))
        worker_payouts = cursor.fetchone()[0] or 0

        cursor.execute(f"""
            SELECT {date_select}, COALESCE(worker_name, ''), COALESCE(pay, 0)
            FROM chb_production
            WHERE pay IS NOT NULL
              AND pay > 0
              AND {date_expr} BETWEEN ? AND ?
            ORDER BY {date_order} ASC, id ASC
        """, (start_date, end_date))
        worker_payout_transactions = cursor.fetchall()

    # SRS formula:
    # Revenue = Total Sales − (Material Expenses + Worker Payouts)
    total_revenue = total_sales - (material_expenses + worker_payouts)

    # SRS wording: cash on hand based on completed sales transactions.
    cash_on_hand = total_sales

    # Detailed sales transactions for the selected date range
    cursor.execute("""
        SELECT ts, item_name, qty, price, COALESCE(raw_price, 0), total
        FROM sales
                WHERE ts IS NOT NULL
                    AND qty > 0
                    AND total >= 0
                    AND DATE(ts) BETWEEN ? AND ?
        ORDER BY ts ASC, id ASC
    """, (start_date, end_date))
    sales_transactions = cursor.fetchall()

    # Product-level sales summary (useful for quick overview)
    cursor.execute("""
        SELECT item_name, COALESCE(SUM(qty), 0) as qty_sold, COALESCE(SUM(total), 0) as amount_sold
        FROM sales
        WHERE ts IS NOT NULL
          AND qty > 0
          AND total >= 0
          AND DATE(ts) BETWEEN ? AND ?
        GROUP BY item_name
        ORDER BY amount_sold DESC, item_name ASC
    """, (start_date, end_date))
    sales_by_product = cursor.fetchall()

    # Detailed material expense transactions for the selected date range.
    cursor.execute(f"""
        SELECT ts, category, COALESCE(description, ''), amount
        FROM expenses
        WHERE DATE(ts) BETWEEN ? AND ?
          AND amount > 0
          AND LOWER(TRIM(COALESCE(category, ''))) NOT IN ({payout_placeholders})
        ORDER BY ts ASC, id ASC
    """, material_params)
    expense_transactions = cursor.fetchall()

    # Material expense summary rows for the expense spreadsheet section.
    cursor.execute(f"""
        SELECT DATE(ts) as expense_date,
               CASE
                   WHEN TRIM(COALESCE(description, '')) = '' THEN category
                   ELSE description
               END as expense_name,
               COALESCE(SUM(amount), 0) as total_amount,
               COALESCE(category, '') as remarks
        FROM expenses
        WHERE DATE(ts) BETWEEN ? AND ?
          AND amount > 0
          AND LOWER(TRIM(COALESCE(category, ''))) NOT IN ({payout_placeholders})
        GROUP BY DATE(ts), expense_name, category
        ORDER BY DATE(ts) ASC, expense_name ASC
    """, material_params)
    expense_summary_rows = cursor.fetchall()

    has_period_data = bool(sales_transactions or expense_transactions or worker_payout_transactions)

    conn.close()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_sales": total_sales,
        "material_expenses": material_expenses,
        "worker_payouts": worker_payouts,
        "total_revenue": total_revenue,
        # Legacy aliases kept for compatibility with old callers.
        "total_expenses": material_expenses,
        "chb_payouts": worker_payouts,
        "cash_on_hand": cash_on_hand,
        "sales_transactions": sales_transactions,
        "sales_by_product": sales_by_product,
        "expense_transactions": expense_transactions,
        "expense_summary_rows": expense_summary_rows,
        "worker_payout_transactions": worker_payout_transactions,
        "has_period_data": has_period_data,
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

    cursor.execute("""
        SELECT COUNT(*) FROM sales
        WHERE DATE(ts) BETWEEN ? AND ?
    """, (start_date.strftime("%Y-%m-%d"), end_date.strftime("%Y-%m-%d")))
    has_period_data = (cursor.fetchone()[0] or 0) > 0

    conn.close()

    return {
        "start_date": start_date.strftime("%Y-%m-%d"),
        "end_date": end_date.strftime("%Y-%m-%d"),
        "daily_data": weekly_data,
        "has_period_data": has_period_data,
    }, None


def generate_chb_production(start_date, end_date):
    """REQ-REP-03: Generate CHB Production Report."""
    date_range, error = get_date_range(start_date, end_date)
    if error:
        return None, error

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    date_expr, date_select, date_order, col_names = _resolve_chb_date_fields(cursor)

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

    if not date_expr:
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
        "has_period_data": bool(entries),
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
        ["Cash on Hand (Completed Sales)", f"{data['cash_on_hand']:,.2f}"],
        ["Material Expenses", f"{data['material_expenses']:,.2f}"],
        ["Worker Payouts (CHB)", f"{data['worker_payouts']:,.2f}"],
        ["Total Cost (Materials + Payouts)", f"{(data['material_expenses'] + data['worker_payouts']):,.2f}"],
        ["Revenue", f"{data['total_revenue']:,.2f}"],
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


def _render_no_data_message(parent):
    """Render SRS-compliant no-data message for period-filtered reports."""
    no_data_frame = tk.Frame(parent, bg=BG_CARD, padx=16, pady=14)
    no_data_frame.pack(fill="x", pady=6, padx=12)
    tk.Label(
        no_data_frame,
        text=NO_DATA_PERIOD_MESSAGE,
        bg=BG_CARD,
        fg=TEXT_MUTED,
        font=("Arial", 11, "italic")
    ).pack(anchor="w")


def open_reports():
    """Open Reports & Analytics Dashboard in a new window."""
    reports_window = tk.Toplevel()
    reports_window.title("Reports & Analytics")
    reports_window.state("zoomed")
    reports_window.configure(bg=BG_PAGE)

    init_database()

    # ================= HEADER (CHB-LIKE CENTERED TITLE) =================
    header = tk.Frame(reports_window, bg=BG_PAGE)
    header.pack(fill="x", padx=20, pady=(12, 8))
    header.columnconfigure(0, weight=1)
    header.columnconfigure(1, weight=1)
    header.columnconfigure(2, weight=1)

    tk.Label(
        header,
        text="Reports & Analytics Dashboard",
        bg=BG_PAGE,
        fg=TEXT_PRIMARY,
        font=("Arial", 18, "bold")
    ).grid(row=0, column=1)

    header_btns = tk.Frame(header, bg=BG_PAGE)
    header_btns.grid(row=0, column=2, sticky="e")
    tk.Button(
        header_btns,
        text="← Back",
        bg="#2563eb",
        fg="white",
        font=("Arial", 10, "bold"),
        relief="flat",
        bd=0,
        padx=14,
        pady=6,
        activebackground="#1d4ed8",
        command=reports_window.destroy
    ).pack(side="left", padx=4)

    # ================= MAIN CONTENT =================
    content = tk.Frame(reports_window, bg=BG_PAGE)
    content.pack(fill="both", expand=True, padx=20, pady=(0, 14))

    notebook_style = ttk.Style()
    notebook_style.configure("Reports.TNotebook", background=BG_PAGE, borderwidth=0)
    notebook_style.configure("Reports.TNotebook.Tab", font=("Arial", 10, "bold"), padding=(14, 8))
    notebook_style.map("Reports.TNotebook.Tab", background=[("selected", BG_CARD)], foreground=[("selected", TEXT_PRIMARY)])

    # Create notebook (tabs)
    notebook = ttk.Notebook(content, style="Reports.TNotebook")
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
    """Build Financial Summary tab with CHB-style split layout."""
    scrollable_frame = create_centered_scrollable_frame(parent)

    selection_frame = tk.Frame(
        scrollable_frame,
        bg=BG_CARD,
        highlightthickness=1,
        highlightbackground=LINE,
        padx=16,
        pady=12,
    )
    selection_frame.pack(fill="x", pady=12, padx=12)

    tk.Label(
        selection_frame,
        text="Financial Summary Filters",
        bg=BG_CARD,
        fg=TEXT_PRIMARY,
        font=("Arial", 12, "bold"),
    ).pack(anchor="w")
    tk.Label(
        selection_frame,
        text="Select the report period, then generate financial details and totals.",
        bg=BG_CARD,
        fg=TEXT_MUTED,
        font=("Arial", 9),
    ).pack(anchor="w", pady=(2, 10))

    controls = tk.Frame(selection_frame, bg=BG_CARD)
    controls.pack(fill="x")

    tk.Label(controls, text="Start Date", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 9, "bold")).pack(side="left", padx=(0, 8))
    start_entry = tk.Entry(controls, width=13, font=("Arial", 9))
    start_entry.pack(side="left", padx=(0, 16))
    start_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))

    tk.Label(controls, text="End Date", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 9, "bold")).pack(side="left", padx=(0, 8))
    end_entry = tk.Entry(controls, width=13, font=("Arial", 9))
    end_entry.pack(side="left", padx=(0, 16))
    end_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

    report_container = tk.Frame(scrollable_frame, bg=BG_PAGE)
    report_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def clear_report_area():
        for widget in report_container.winfo_children():
            widget.destroy()

    def money(val):
        return f"₱{float(val or 0):,.2f}"

    def fmt_short_date(ts_value):
        text = str(ts_value or "")
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
            try:
                dt = datetime.strptime(text[:19], fmt)
                return dt.strftime("%m-%d-%y")
            except ValueError:
                continue
        return text[:10]

    def generate_report():
        start = start_entry.get().strip()
        end = end_entry.get().strip()
        data, error = generate_financial_summary(start, end)

        if error:
            messagebox.showerror("Error", error)
            return

        clear_report_area()

        if not data.get("has_period_data"):
            _render_no_data_message(report_container)
            return

        header_card = tk.Frame(report_container, bg=BG_CARD, highlightthickness=1, highlightbackground=LINE, padx=16, pady=12)
        header_card.pack(fill="x", pady=(0, 10))
        tk.Label(header_card, text="Financial Summary Report", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 14, "bold")).pack(anchor="w")
        tk.Label(header_card, text=f"Period: {start} to {end}", bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 9)).pack(anchor="w", pady=(2, 0))

        split = tk.Frame(report_container, bg=BG_PAGE)
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)

        left_col = tk.Frame(split, bg=BG_PAGE)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        right_col = tk.Frame(split, bg=BG_PAGE)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        metrics_card = tk.Frame(left_col, bg=BG_CARD, highlightthickness=1, highlightbackground=LINE, padx=14, pady=12)
        metrics_card.pack(fill="x", pady=(0, 10))
        tk.Label(metrics_card, text="Key Financial Metrics", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        grid = tk.Frame(metrics_card, bg=BG_CARD)
        grid.pack(fill="x")

        metric_specs = [
            ("Total Sales", money(data["total_sales"])),
            ("Cash On Hand", money(data["cash_on_hand"])),
            ("Material Expenses", money(data["material_expenses"])),
            ("Worker Payouts", money(data["worker_payouts"])),
        ]
        for idx, (title, value) in enumerate(metric_specs):
            tile = tk.Frame(grid, bg=SUMMARY_BG, padx=10, pady=8)
            tile.grid(row=idx // 2, column=idx % 2, sticky="nsew", padx=4, pady=4)
            tk.Label(tile, text=title.upper(), bg=SUMMARY_BG, fg=TEXT_MUTED, font=("Arial", 8, "bold")).pack(anchor="w")
            tk.Label(tile, text=value, bg=SUMMARY_BG, fg=TEXT_PRIMARY, font=("Arial", 14, "bold")).pack(anchor="w", pady=(2, 0))
        grid.columnconfigure(0, weight=1)
        grid.columnconfigure(1, weight=1)

        style = ttk.Style()
        style.configure("FinancialData.Treeview", font=("Arial", 9), rowheight=24, background=BG_CARD, fieldbackground=BG_CARD)
        style.configure("FinancialData.Treeview.Heading", font=("Arial", 9, "bold"), foreground=TEXT_PRIMARY)
        style.map("FinancialData.Treeview", background=[("selected", ACCENT)])

        sales_card = tk.Frame(left_col, bg=BG_CARD, highlightthickness=1, highlightbackground=LINE, padx=14, pady=12)
        sales_card.pack(fill="both", expand=True, pady=(0, 10))
        tk.Label(sales_card, text="Items Sold", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        sales_rows = data.get("sales_transactions", [])
        if sales_rows:
            sales_wrap = tk.Frame(sales_card, bg=BG_CARD)
            sales_wrap.pack(fill="both", expand=True)
            columns = ("date", "product", "unit", "purchased", "jasp", "qty", "total_purchased", "total_jasp", "markup")
            tree = ttk.Treeview(sales_wrap, columns=columns, show="headings", style="FinancialData.Treeview", height=8)

            headings = [
                ("date", "DATE", 100),
                ("product", "PRODUCT", 190),
                ("unit", "UNIT", 60),
                ("purchased", "PURCHASED", 95),
                ("jasp", "JASP", 95),
                ("qty", "QTY", 80),
                ("total_purchased", "TOTAL PURCHASED", 120),
                ("total_jasp", "TOTAL JASP", 100),
                ("markup", "MARKUP", 100),
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
                    "",
                    "end",
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
                    ),
                )

            tree.pack(side="left", fill="both", expand=True)
            sales_scroll = ttk.Scrollbar(sales_wrap, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=sales_scroll.set)
            sales_scroll.pack(side="right", fill="y")
        else:
            tk.Label(sales_card, text=NO_DATA_PERIOD_MESSAGE, bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 10, "italic")).pack(anchor="w")

        expense_card = tk.Frame(left_col, bg=BG_CARD, highlightthickness=1, highlightbackground=LINE, padx=14, pady=12)
        expense_card.pack(fill="both", expand=True)
        tk.Label(expense_card, text="Material Expense List", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        exp_rows = data.get("expense_summary_rows", [])
        if exp_rows:
            exp_wrap = tk.Frame(expense_card, bg=BG_CARD)
            exp_wrap.pack(fill="both", expand=True)

            exp_columns = ("date", "expense_name", "total_expense", "remarks")
            exp_tree = ttk.Treeview(exp_wrap, columns=exp_columns, show="headings", style="FinancialData.Treeview", height=6)
            exp_headings = [
                ("date", "DATE", 100),
                ("expense_name", "EXPENSE NAME", 260),
                ("total_expense", "TOTAL EXPENSE", 120),
                ("remarks", "REMARKS", 160),
            ]
            for col, title, width in exp_headings:
                anchor = "w" if col in ("expense_name", "remarks") else "center"
                exp_tree.heading(col, text=title)
                exp_tree.column(col, width=width, anchor=anchor, stretch=True)

            for expense_date, expense_name, total_amount, remarks in exp_rows:
                exp_tree.insert(
                    "",
                    "end",
                    values=(
                        fmt_short_date(expense_date),
                        str(expense_name or "-"),
                        money(total_amount),
                        str(remarks or ""),
                    ),
                )

            exp_tree.pack(side="left", fill="both", expand=True)
            exp_scroll = ttk.Scrollbar(exp_wrap, orient="vertical", command=exp_tree.yview)
            exp_tree.configure(yscrollcommand=exp_scroll.set)
            exp_scroll.pack(side="right", fill="y")
        else:
            tk.Label(expense_card, text=NO_DATA_PERIOD_MESSAGE, bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 10, "italic")).pack(anchor="w")

        subtotal_row = tk.Frame(expense_card, bg=BG_CARD)
        subtotal_row.pack(fill="x", pady=(8, 0))
        tk.Label(subtotal_row, text="Material Sub-Total", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 10, "bold"), anchor="e").pack(side="left", fill="x", expand=True)
        tk.Label(subtotal_row, text=money(data["material_expenses"]), bg=SUMMARY_BG, fg=TEXT_PRIMARY, font=("Arial", 10, "bold"), padx=8, pady=4).pack(side="left")

        summary_card = tk.Frame(right_col, bg=BG_CARD, highlightthickness=1, highlightbackground=LINE, padx=14, pady=12)
        summary_card.pack(fill="x", pady=(0, 10))
        tk.Label(summary_card, text="Financial Summary", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))

        summary_rows = [
            ("Total Sales", money(data["total_sales"])),
            ("Cash On Hand", money(data["cash_on_hand"])),
            ("Material Expenses", f"-{money(data['material_expenses'])}"),
            ("Worker Payouts (CHB)", f"-{money(data['worker_payouts'])}"),
            ("Total Cost (Materials + Payouts)", f"-{money(data['material_expenses'] + data['worker_payouts'])}"),
            ("Revenue", money(data["total_revenue"])),
        ]
        for idx, (metric, amount) in enumerate(summary_rows):
            row_bg = HIGHLIGHT_BG if idx == len(summary_rows) - 1 else BG_CARD
            row = tk.Frame(summary_card, bg=row_bg)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=metric, bg=row_bg, fg=TEXT_PRIMARY, font=("Arial", 9, "bold" if idx == len(summary_rows) - 1 else "normal")).pack(side="left", anchor="w")
            tk.Label(row, text=amount, bg=row_bg, fg=TEXT_PRIMARY, font=("Arial", 9, "bold"), anchor="e").pack(side="right")

        revenue_card = tk.Frame(right_col, bg=HIGHLIGHT_BG, highlightthickness=1, highlightbackground=LINE, padx=14, pady=12)
        revenue_card.pack(fill="x", pady=(0, 10))
        tk.Label(revenue_card, text="Total Revenue", bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG, font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(revenue_card, text=money(data["total_revenue"]), bg=HIGHLIGHT_BG, fg=HIGHLIGHT_FG, font=("Arial", 22, "bold")).pack(anchor="w", pady=(2, 0))

        actions_card = tk.Frame(right_col, bg=BG_CARD, highlightthickness=1, highlightbackground=LINE, padx=14, pady=12)
        actions_card.pack(fill="x")
        tk.Label(actions_card, text="Actions", bg=BG_CARD, fg=TEXT_PRIMARY, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Button(
            actions_card,
            text="Export to PDF",
            command=lambda: _handle_export("Financial Summary", data),
            font=("Arial", 10, "bold"),
            bg="#2563eb",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            activebackground="#1d4ed8",
        ).pack(fill="x")

    tk.Button(
        controls,
        text="Generate Report",
        command=generate_report,
        font=("Arial", 10, "bold"),
        bg="#2563eb",
        fg="white",
        relief="flat",
        bd=0,
        padx=14,
        pady=8,
        activebackground="#1d4ed8",
    ).pack(side="right")


def _build_weekly_sales_tab(parent):
    """Build Weekly Sales Statistics tab with CHB-style split layout."""
    scrollable_frame = create_centered_scrollable_frame(parent)

    selection_frame = tk.Frame(scrollable_frame, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=LINE, padx=16, pady=12)
    selection_frame.pack(fill="x", pady=12, padx=12)

    tk.Label(selection_frame, text="Weekly Sales Filters", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 12, "bold")).pack(anchor="w")
    tk.Label(selection_frame, text="Uses selected end date to compute the latest 7-day revenue range.",
             bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 9)).pack(anchor="w", pady=(2, 10))

    controls = tk.Frame(selection_frame, bg=BG_CARD)
    controls.pack(fill="x")

    tk.Label(controls, text="End Date", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 9, "bold")).pack(side="left", padx=(0, 8))
    end_entry = tk.Entry(controls, width=13, font=("Arial", 9))
    end_entry.pack(side="left", padx=(0, 16))
    end_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

    report_container = tk.Frame(scrollable_frame, bg=BG_PAGE)
    report_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def clear_report_area():
        for widget in report_container.winfo_children():
            widget.destroy()

    def generate_report():
        data, error = generate_weekly_sales(end_entry.get().strip())

        if error:
            messagebox.showerror("Error", error)
            return

        clear_report_area()

        if not data.get("has_period_data"):
            _render_no_data_message(report_container)
            return

        total_revenue = sum(revenue for _, _, revenue in data["daily_data"])

        header_card = tk.Frame(report_container, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=LINE, padx=16, pady=12)
        header_card.pack(fill="x", pady=(0, 10))
        tk.Label(header_card, text="Weekly Sales Statistics", bg=BG_CARD,
                 fg=TEXT_PRIMARY, font=("Arial", 14, "bold")).pack(anchor="w")
        tk.Label(header_card, text=f"Period: {data['start_date']} to {data['end_date']}",
                 bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 9)).pack(anchor="w", pady=(2, 0))

        split = tk.Frame(report_container, bg=BG_PAGE)
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)

        left_col = tk.Frame(split, bg=BG_PAGE)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right_col = tk.Frame(split, bg=BG_PAGE)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        style = ttk.Style()
        style.configure("WeeklyData.Treeview", font=("Arial", 9), rowheight=24,
                        background=BG_CARD, fieldbackground=BG_CARD)
        style.configure("WeeklyData.Treeview.Heading", font=("Arial", 9, "bold"), foreground=TEXT_PRIMARY)
        style.map("WeeklyData.Treeview", background=[("selected", ACCENT)])

        table_card = tk.Frame(left_col, bg=BG_CARD, highlightthickness=1,
                              highlightbackground=LINE, padx=14, pady=12)
        table_card.pack(fill="both", expand=True)
        tk.Label(table_card, text="Daily Revenue Breakdown", bg=BG_CARD,
                 fg=TEXT_PRIMARY, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        table_wrap = tk.Frame(table_card, bg=BG_CARD)
        table_wrap.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            table_wrap,
            columns=("day", "date", "revenue"),
            show="headings",
            style="WeeklyData.Treeview",
            height=10,
        )
        tree.heading("day", text="DAY")
        tree.heading("date", text="DATE")
        tree.heading("revenue", text="REVENUE")
        tree.column("day", width=170, anchor="w")
        tree.column("date", width=150, anchor="center")
        tree.column("revenue", width=170, anchor="e")

        for day, date, revenue in data["daily_data"]:
            tree.insert("", "end", values=(day, date, f"₱{revenue:,.2f}"))

        tree.pack(side="left", fill="both", expand=True)
        table_scroll = ttk.Scrollbar(table_wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=table_scroll.set)
        table_scroll.pack(side="right", fill="y")

        right_top = tk.Frame(right_col, bg=BG_CARD, highlightthickness=1,
                             highlightbackground=LINE, padx=14, pady=12)
        right_top.pack(fill="x", pady=(0, 10))
        tk.Label(right_top, text="Summary", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))

        rows = [
            ("Days Counted", str(len(data["daily_data"]))),
            ("Start Date", data["start_date"]),
            ("End Date", data["end_date"]),
        ]
        for label_text, value in rows:
            row = tk.Frame(right_top, bg=BG_CARD)
            row.pack(fill="x", pady=2)
            tk.Label(row, text=label_text, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 9)).pack(side="left")
            tk.Label(row, text=value, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 9, "bold")).pack(side="right")

        total_card = tk.Frame(right_col, bg=HIGHLIGHT_BG, highlightthickness=1,
                              highlightbackground=LINE, padx=14, pady=12)
        total_card.pack(fill="x", pady=(0, 10))
        tk.Label(total_card, text="Total Weekly Revenue", bg=HIGHLIGHT_BG,
                 fg=HIGHLIGHT_FG, font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(total_card, text=f"₱{total_revenue:,.2f}", bg=HIGHLIGHT_BG,
                 fg=HIGHLIGHT_FG, font=("Arial", 22, "bold")).pack(anchor="w", pady=(2, 0))

        actions_card = tk.Frame(right_col, bg=BG_CARD, highlightthickness=1,
                                highlightbackground=LINE, padx=14, pady=12)
        actions_card.pack(fill="x")
        tk.Label(actions_card, text="Actions", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Button(
            actions_card,
            text="Export to PDF",
            command=lambda: _handle_export("Weekly Sales Statistics", data),
            font=("Arial", 10, "bold"),
            bg="#2563eb",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            activebackground="#1d4ed8",
        ).pack(fill="x")

    tk.Button(controls, text="Generate Report", command=generate_report,
              font=("Arial", 10, "bold"), bg="#2563eb", fg="white",
              relief="flat", bd=0, padx=14, pady=8,
              activebackground="#1d4ed8").pack(side="right")


def _build_chb_production_tab(parent):
    """Build CHB Production Report tab with CHB-style split layout."""
    scrollable_frame = create_centered_scrollable_frame(parent)

    selection_frame = tk.Frame(scrollable_frame, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=LINE, padx=16, pady=12)
    selection_frame.pack(fill="x", pady=12, padx=12)

    tk.Label(selection_frame, text="CHB Production Filters", bg=BG_CARD,
             fg=TEXT_PRIMARY, font=("Arial", 12, "bold")).pack(anchor="w")
    tk.Label(selection_frame, text="Generate production totals and efficiency for the selected period.",
             bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 9)).pack(anchor="w", pady=(2, 10))

    controls = tk.Frame(selection_frame, bg=BG_CARD)
    controls.pack(fill="x")

    tk.Label(controls, text="Start Date", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 9, "bold")).pack(side="left", padx=(0, 8))
    start_entry = tk.Entry(controls, width=13, font=("Arial", 9))
    start_entry.pack(side="left", padx=(0, 16))
    start_entry.insert(0, (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d"))

    tk.Label(controls, text="End Date", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 9, "bold")).pack(side="left", padx=(0, 8))
    end_entry = tk.Entry(controls, width=13, font=("Arial", 9))
    end_entry.pack(side="left", padx=(0, 16))
    end_entry.insert(0, datetime.now().strftime("%Y-%m-%d"))

    report_container = tk.Frame(scrollable_frame, bg=BG_PAGE)
    report_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def clear_report_area():
        for widget in report_container.winfo_children():
            widget.destroy()

    def generate_report():
        start = start_entry.get().strip()
        end = end_entry.get().strip()
        data, error = generate_chb_production(start, end)

        if error:
            messagebox.showerror("Error", error)
            return

        clear_report_area()

        if not data.get("has_period_data"):
            _render_no_data_message(report_container)
            return

        header_card = tk.Frame(report_container, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=LINE, padx=16, pady=12)
        header_card.pack(fill="x", pady=(0, 10))
        tk.Label(header_card, text="CHB Production Report", bg=BG_CARD,
                 fg=TEXT_PRIMARY, font=("Arial", 14, "bold")).pack(anchor="w")
        tk.Label(header_card, text=f"Period: {start} to {end}", bg=BG_CARD,
                 fg=TEXT_MUTED, font=("Arial", 9)).pack(anchor="w", pady=(2, 0))

        split = tk.Frame(report_container, bg=BG_PAGE)
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)

        left_col = tk.Frame(split, bg=BG_PAGE)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right_col = tk.Frame(split, bg=BG_PAGE)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        style = ttk.Style()
        style.configure("CHBData.Treeview", font=("Arial", 9), rowheight=24,
                        background=BG_CARD, fieldbackground=BG_CARD)
        style.configure("CHBData.Treeview.Heading", font=("Arial", 9, "bold"), foreground=TEXT_PRIMARY)
        style.map("CHBData.Treeview", background=[("selected", ACCENT)])

        details_card = tk.Frame(left_col, bg=BG_CARD, highlightthickness=1,
                                highlightbackground=LINE, padx=14, pady=12)
        details_card.pack(fill="both", expand=True)
        tk.Label(details_card, text="Production Details", bg=BG_CARD,
                 fg=TEXT_PRIMARY, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        entries = data.get("entries", [])
        if entries:
            wrap = tk.Frame(details_card, bg=BG_CARD)
            wrap.pack(fill="both", expand=True)

            tree = ttk.Treeview(
                wrap,
                columns=("ts", "cement", "blocks"),
                show="headings",
                style="CHBData.Treeview",
                height=12,
            )
            tree.heading("ts", text="DATE/TIME")
            tree.heading("cement", text="CEMENT (KG)")
            tree.heading("blocks", text="BLOCKS")
            tree.column("ts", width=220, anchor="w")
            tree.column("cement", width=120, anchor="e")
            tree.column("blocks", width=120, anchor="e")

            for ts, cement, blocks in entries:
                tree.insert("", "end", values=(str(ts), f"{float(cement or 0):,.2f}", f"{int(blocks or 0):,}"))

            tree.pack(side="left", fill="both", expand=True)
            scroll = ttk.Scrollbar(wrap, orient="vertical", command=tree.yview)
            tree.configure(yscrollcommand=scroll.set)
            scroll.pack(side="right", fill="y")
        else:
            tk.Label(details_card, text=NO_DATA_PERIOD_MESSAGE, bg=BG_CARD,
                     fg=TEXT_MUTED, font=("Arial", 10, "italic")).pack(anchor="w")

        metrics_card = tk.Frame(right_col, bg=BG_CARD, highlightthickness=1,
                                highlightbackground=LINE, padx=14, pady=12)
        metrics_card.pack(fill="x", pady=(0, 10))
        tk.Label(metrics_card, text="Summary", bg=BG_CARD,
                 fg=TEXT_PRIMARY, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))

        metric_rows = [
            ("Total Cement Consumed", f"{data['total_cement']:,.2f} kg"),
            ("Total Blocks Produced", f"{data['total_blocks']:,} pcs"),
            ("Production Efficiency", f"{data['efficiency']:.2f}%"),
        ]
        for label_text, value in metric_rows:
            row = tk.Frame(metrics_card, bg=BG_CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label_text, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 9)).pack(side="left")
            tk.Label(row, text=value, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 10, "bold")).pack(side="right")

        efficiency_card = tk.Frame(right_col, bg=SUMMARY_BG, highlightthickness=1,
                                   highlightbackground=LINE, padx=14, pady=12)
        efficiency_card.pack(fill="x", pady=(0, 10))
        tk.Label(efficiency_card, text="Efficiency", bg=SUMMARY_BG,
                 fg=TEXT_MUTED, font=("Arial", 10, "bold")).pack(anchor="w")
        tk.Label(efficiency_card, text=f"{data['efficiency']:.2f}%", bg=SUMMARY_BG,
                 fg=TEXT_PRIMARY, font=("Arial", 22, "bold")).pack(anchor="w", pady=(2, 0))

        actions_card = tk.Frame(right_col, bg=BG_CARD, highlightthickness=1,
                                highlightbackground=LINE, padx=14, pady=12)
        actions_card.pack(fill="x")
        tk.Label(actions_card, text="Actions", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Button(
            actions_card,
            text="Export to PDF",
            command=lambda: _handle_export("CHB Production", data),
            font=("Arial", 10, "bold"),
            bg="#2563eb",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            activebackground="#1d4ed8",
        ).pack(fill="x")

    tk.Button(controls, text="Generate Report", command=generate_report,
              font=("Arial", 10, "bold"), bg="#2563eb", fg="white",
              relief="flat", bd=0, padx=14, pady=8,
              activebackground="#1d4ed8").pack(side="right")


def _build_inventory_status_tab(parent):
    """Build Inventory Status tab with CHB-style split layout."""
    scrollable_frame = create_centered_scrollable_frame(parent)

    selection_frame = tk.Frame(scrollable_frame, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=LINE, padx=16, pady=12)
    selection_frame.pack(fill="x", pady=12, padx=12)

    tk.Label(selection_frame, text="Inventory Status", bg=BG_CARD, fg=TEXT_PRIMARY,
             font=("Arial", 12, "bold")).pack(anchor="w")
    tk.Label(selection_frame, text="Generate a snapshot of all inventory and low stock items.",
             bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 9)).pack(anchor="w", pady=(2, 10))

    controls = tk.Frame(selection_frame, bg=BG_CARD)
    controls.pack(fill="x")

    report_container = tk.Frame(scrollable_frame, bg=BG_PAGE)
    report_container.pack(fill="both", expand=True, padx=12, pady=(0, 12))

    def clear_report_area():
        for widget in report_container.winfo_children():
            widget.destroy()

    def generate_report():
        data, error = generate_inventory_status()

        if error:
            messagebox.showerror("Error", error)
            return

        clear_report_area()

        header_card = tk.Frame(report_container, bg=BG_CARD, highlightthickness=1,
                               highlightbackground=LINE, padx=16, pady=12)
        header_card.pack(fill="x", pady=(0, 10))
        tk.Label(header_card, text="Inventory Status Report", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 14, "bold")).pack(anchor="w")
        tk.Label(header_card, text=f"As of: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                 bg=BG_CARD, fg=TEXT_MUTED, font=("Arial", 9)).pack(anchor="w", pady=(2, 0))

        split = tk.Frame(report_container, bg=BG_PAGE)
        split.pack(fill="both", expand=True)
        split.columnconfigure(0, weight=3)
        split.columnconfigure(1, weight=2)

        left_col = tk.Frame(split, bg=BG_PAGE)
        left_col.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        right_col = tk.Frame(split, bg=BG_PAGE)
        right_col.grid(row=0, column=1, sticky="nsew", padx=(8, 0))

        style = ttk.Style()
        style.configure("InventoryData.Treeview", font=("Arial", 9), rowheight=24,
                        background=BG_CARD, fieldbackground=BG_CARD)
        style.configure("InventoryData.Treeview.Heading", font=("Arial", 9, "bold"), foreground=TEXT_PRIMARY)
        style.map("InventoryData.Treeview", background=[("selected", ACCENT)])

        all_items_card = tk.Frame(left_col, bg=BG_CARD, highlightthickness=1,
                                  highlightbackground=LINE, padx=14, pady=12)
        all_items_card.pack(fill="both", expand=True)
        tk.Label(all_items_card, text="All Inventory Items", bg=BG_CARD,
                 fg=TEXT_PRIMARY, font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 10))

        all_wrap = tk.Frame(all_items_card, bg=BG_CARD)
        all_wrap.pack(fill="both", expand=True)

        tree = ttk.Treeview(
            all_wrap,
            columns=("name", "qty", "price"),
            show="headings",
            style="InventoryData.Treeview",
            height=14,
        )
        tree.heading("name", text="ITEM NAME")
        tree.heading("qty", text="QUANTITY")
        tree.heading("price", text="PRICE")
        tree.column("name", width=280, anchor="w")
        tree.column("qty", width=120, anchor="e")
        tree.column("price", width=120, anchor="e")

        for name, qty, price in data.get("all_items", []):
            tree.insert("", "end", values=(str(name), str(qty), f"₱{float(price or 0):,.2f}"))

        tree.pack(side="left", fill="both", expand=True)
        all_scroll = ttk.Scrollbar(all_wrap, orient="vertical", command=tree.yview)
        tree.configure(yscrollcommand=all_scroll.set)
        all_scroll.pack(side="right", fill="y")

        summary_card = tk.Frame(right_col, bg=BG_CARD, highlightthickness=1,
                                highlightbackground=LINE, padx=14, pady=12)
        summary_card.pack(fill="x", pady=(0, 10))
        tk.Label(summary_card, text="Summary", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))

        summary_rows = [
            ("Total Items In Inventory", f"{data.get('total_items', 0):,}"),
            ("Low Stock Items (< 10)", f"{len(data.get('low_stock', [])):,}"),
        ]
        for label_text, value in summary_rows:
            row = tk.Frame(summary_card, bg=BG_CARD)
            row.pack(fill="x", pady=3)
            tk.Label(row, text=label_text, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 9)).pack(side="left")
            tk.Label(row, text=value, bg=BG_CARD, fg=TEXT_PRIMARY,
                     font=("Arial", 10, "bold")).pack(side="right")

        low_card = tk.Frame(right_col, bg="#fff1f2", highlightthickness=1,
                            highlightbackground="#fecdd3", padx=14, pady=12)
        low_card.pack(fill="both", expand=True, pady=(0, 10))
        tk.Label(low_card, text="Low Stock Alerts", bg="#fff1f2", fg="#9f1239",
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))

        low_stock_rows = data.get("low_stock", [])
        if low_stock_rows:
            low_wrap = tk.Frame(low_card, bg="#fff1f2")
            low_wrap.pack(fill="both", expand=True)
            low_tree = ttk.Treeview(
                low_wrap,
                columns=("name", "qty"),
                show="headings",
                style="InventoryData.Treeview",
                height=8,
            )
            low_tree.heading("name", text="ITEM")
            low_tree.heading("qty", text="QTY")
            low_tree.column("name", width=200, anchor="w")
            low_tree.column("qty", width=90, anchor="e")
            for name, qty, _ in low_stock_rows:
                low_tree.insert("", "end", values=(str(name), str(qty)))
            low_tree.pack(side="left", fill="both", expand=True)
            low_scroll = ttk.Scrollbar(low_wrap, orient="vertical", command=low_tree.yview)
            low_tree.configure(yscrollcommand=low_scroll.set)
            low_scroll.pack(side="right", fill="y")
        else:
            tk.Label(low_card, text="No low stock alerts for this snapshot.",
                     bg="#fff1f2", fg="#9f1239", font=("Arial", 10, "italic")).pack(anchor="w")

        actions_card = tk.Frame(right_col, bg=BG_CARD, highlightthickness=1,
                                highlightbackground=LINE, padx=14, pady=12)
        actions_card.pack(fill="x")
        tk.Label(actions_card, text="Actions", bg=BG_CARD, fg=TEXT_PRIMARY,
                 font=("Arial", 11, "bold")).pack(anchor="w", pady=(0, 8))
        tk.Button(
            actions_card,
            text="Export to PDF",
            command=lambda: _handle_export("Inventory Status", data),
            font=("Arial", 10, "bold"),
            bg="#2563eb",
            fg="white",
            relief="flat",
            bd=0,
            padx=12,
            pady=8,
            activebackground="#1d4ed8",
        ).pack(fill="x")

    tk.Button(controls, text="Generate Report", command=generate_report,
              font=("Arial", 10, "bold"), bg="#2563eb", fg="white",
              relief="flat", bd=0, padx=14, pady=8,
              activebackground="#1d4ed8").pack(side="right")


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