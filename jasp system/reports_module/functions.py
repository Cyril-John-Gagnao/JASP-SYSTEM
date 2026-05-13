import sqlite3
from datetime import datetime, timedelta
from tkinter import filedialog

from .constants import WORKER_PAYOUT_CATEGORY_NAMES
from .database import DB_NAME

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False


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
          AND COALESCE(payment_status, 'Paid') <> 'Void'
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
    # Revenue = Total Sales - (Material Expenses + Worker Payouts)
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
                    AND COALESCE(payment_status, 'Paid') <> 'Void'
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
          AND COALESCE(payment_status, 'Paid') <> 'Void'
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
              AND COALESCE(payment_status, 'Paid') <> 'Void'
        """, (date_str,))
        daily_revenue = cursor.fetchone()[0] or 0
        weekly_data.append((day_name, date_str, daily_revenue))

    cursor.execute("""
        SELECT COUNT(*) FROM sales
        WHERE DATE(ts) BETWEEN ? AND ?
          AND COALESCE(payment_status, 'Paid') <> 'Void'
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
