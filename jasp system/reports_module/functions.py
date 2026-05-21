import calendar
import os
import sqlite3
from datetime import datetime, timedelta
from tkinter import filedialog

from .constants import NO_DATA_PERIOD_MESSAGE
from .database import DB_NAME
from chb_module.chb_database import FINE_SAND_BAGS_PER_CUBIC_METER
from inventory_module.inventory_functions import is_low_stock_item

try:
    from reportlab.lib.pagesizes import letter
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image
    from reportlab.lib import colors
    HAS_REPORTLAB = True
except ImportError:
    HAS_REPORTLAB = False

from jasp_theme import logo_path


PDF_HEADER_BG = "#2D2D2D"
PDF_LOGO_CONTAINER_BG = "#676767"
PDF_TABLE_HEADER_BG = "#2D2D2D"
PDF_BORDER = "#333333"
PDF_ROW_ALT = "#f2f2f2"


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


def get_report_date_range(filter_type, reference_date=None, custom_start=None, custom_end=None):
    """Return validated report start/end dates as YYYY-MM-DD strings."""
    period = (filter_type or "Custom").strip().lower()

    if period == "custom":
        date_range, error = get_date_range(custom_start or "", custom_end or "")
        if error:
            return None, None, error
        start, end = date_range
        return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), None

    try:
        selected = datetime.strptime((reference_date or datetime.now().strftime("%Y-%m-%d")).strip(), "%Y-%m-%d")
    except ValueError as e:
        return None, None, f"Invalid date format: {e}"

    if period == "day":
        start = end = selected
    elif period == "week":
        start = selected - timedelta(days=selected.weekday())
        end = start + timedelta(days=6)
    elif period == "month":
        start = selected.replace(day=1)
        end = selected.replace(day=calendar.monthrange(selected.year, selected.month)[1])
    else:
        return None, None, "Invalid report period. Use Day, Week, Month, or Custom."

    return start.strftime("%Y-%m-%d"), end.strftime("%Y-%m-%d"), None


def _format_report_quantity(value):
    try:
        qty = float(value or 0)
    except (TypeError, ValueError):
        return str(value or 0)
    return f"{qty:,.3f}".rstrip("0").rstrip(".")


def _resolve_chb_date_fields(cursor):
    """Resolve CHB production date expressions for filtering/reporting."""
    cursor.execute("PRAGMA table_info(chb_production)")
    chb_cols = {col[1] for col in cursor.fetchall()}

    if "ts" in chb_cols and "production_date" in chb_cols:
        date_value = "COALESCE(NULLIF(production_date, ''), ts)"
        return f"DATE({date_value})", date_value, date_value, chb_cols
    if "ts" in chb_cols:
        return "DATE(ts)", "ts", "ts", chb_cols
    if "production_date" in chb_cols:
        date_value = "NULLIF(production_date, '')"
        return f"DATE({date_value})", date_value, date_value, chb_cols
    return None, None, None, chb_cols


def _safe_float(value):
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _first_positive(row, columns):
    for column in columns:
        value = _safe_float(row.get(column, 0))
        if value > 0:
            return value, column
    return 0.0, ""


def _fetch_material_cost_basis(cursor):
    """Return CHB material unit costs from inventory item cost fields."""
    cursor.execute("PRAGMA table_info(items)")
    item_cols = {col[1] for col in cursor.fetchall()}
    if not item_cols:
        return {
            "cement_unit_cost": 0.0,
            "cement_cost_source": "not configured",
            "fine_sand_bag_cost": 0.0,
            "fine_sand_cost_source": "not configured",
        }

    selectable_cols = [
        col for col in ("price", "raw_price", "fine_sand_bag_price")
        if col in item_cols
    ]
    select_sql = ", ".join(f"COALESCE({col}, 0) AS {col}" for col in selectable_cols)

    def material_row(item_name):
        if not selectable_cols:
            return {}
        cursor.execute(f"""
            SELECT {select_sql}
            FROM items
            WHERE LOWER(TRIM(name)) = LOWER(TRIM(?))
            ORDER BY id ASC
            LIMIT 1
        """, (item_name,))
        row = cursor.fetchone()
        return dict(zip(selectable_cols, row)) if row else {}

    cement = material_row("Cement")
    fine_sand = material_row("Fine Sand")

    cement_unit_cost, cement_source = _first_positive(cement, ("raw_price", "price"))
    fine_sand_bag_cost, fine_sand_source = _first_positive(fine_sand, ("fine_sand_bag_price",))
    if fine_sand_bag_cost <= 0:
        cubic_cost, cubic_source = _first_positive(fine_sand, ("raw_price", "price"))
        if cubic_cost > 0:
            fine_sand_bag_cost = cubic_cost / FINE_SAND_BAGS_PER_CUBIC_METER
            fine_sand_source = f"{cubic_source} / {FINE_SAND_BAGS_PER_CUBIC_METER} bags"

    return {
        "cement_unit_cost": cement_unit_cost,
        "cement_cost_source": f"Cement {cement_source}" if cement_source else "not configured",
        "fine_sand_bag_cost": fine_sand_bag_cost,
        "fine_sand_cost_source": f"Fine Sand {fine_sand_source}" if fine_sand_source else "not configured",
    }


def generate_sales_report(start_date, end_date):
    """Generate transaction-level sales report rows for completed sales."""
    start_date, end_date, error = get_report_date_range("Custom", custom_start=start_date, custom_end=end_date)
    if error:
        return None, error

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            ts,
            COALESCE(NULLIF(transaction_id, ''), 'TXN-' || printf('%05d', id)) AS txn_ref,
            item_name,
            qty,
            total,
            COALESCE(payment_received, 0),
            COALESCE(change_amount, 0)
        FROM sales
        WHERE ts IS NOT NULL
          AND qty > 0
          AND total >= 0
          AND COALESCE(payment_status, 'Paid') <> 'Void'
          AND DATE(ts) BETWEEN ? AND ?
        ORDER BY DATE(ts) ASC, ts ASC, id ASC
    """, (start_date, end_date))
    rows = cursor.fetchall()
    conn.close()

    grouped = {}
    order = []
    for ts, txn_ref, item_name, qty, total, payment_received, change_amount in rows:
        key = txn_ref or f"TXN-{len(order) + 1:05d}"
        if key not in grouped:
            grouped[key] = {
                "transaction_date": ts,
                "transaction_id": key,
                "items_sold": [],
                "quantities": [],
                "total_amount": 0,
                "payment_received": float(payment_received or 0),
                "change_amount": float(change_amount or 0),
            }
            order.append(key)
        grouped[key]["items_sold"].append(str(item_name or "-"))
        grouped[key]["quantities"].append(_format_report_quantity(qty))
        grouped[key]["total_amount"] += float(total or 0)
        grouped[key]["payment_received"] = max(grouped[key]["payment_received"], float(payment_received or 0))
        grouped[key]["change_amount"] = max(grouped[key]["change_amount"], float(change_amount or 0))

    transactions = [
        {
            **grouped[key],
            "items_sold": ", ".join(grouped[key]["items_sold"]),
            "quantities": ", ".join(grouped[key]["quantities"]),
        }
        for key in order
    ]

    return {
        "start_date": start_date,
        "end_date": end_date,
        "transactions": transactions,
        "transaction_count": len(transactions),
        "total_sales": sum(row["total_amount"] for row in transactions),
        "has_period_data": bool(transactions),
    }, None


def generate_financial_summary(start_date, end_date):
    """REQ-REP-01: Generate Financial Summary Report."""
    start_date, end_date, error = get_report_date_range("Custom", custom_start=start_date, custom_end=end_date)
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

    # Worker payouts are sourced from CHB production records.
    worker_payouts = 0
    worker_payout_transactions = []
    date_expr, date_select, date_order, chb_cols = _resolve_chb_date_fields(cursor)
    if date_expr:
        if "pay" in chb_cols:
            if "pay_rate" in chb_cols and "cement_bags" in chb_cols:
                pay_expr = "COALESCE(pay, COALESCE(cement_bags, 0) * COALESCE(pay_rate, 0), 0)"
            else:
                pay_expr = "COALESCE(pay, 0)"
        elif "pay_rate" in chb_cols and "cement_bags" in chb_cols:
            pay_expr = "COALESCE(cement_bags, 0) * COALESCE(pay_rate, 0)"
        else:
            pay_expr = "0"

        cursor.execute(f"""
            SELECT COALESCE(SUM({pay_expr}), 0)
            FROM chb_production
            WHERE {pay_expr} > 0
              AND {date_expr} BETWEEN ? AND ?
        """, (start_date, end_date))
        worker_payouts = cursor.fetchone()[0] or 0

        cursor.execute(f"""
            SELECT {date_select}, COALESCE(worker_name, ''), {pay_expr}
            FROM chb_production
            WHERE {pay_expr} > 0
              AND {date_expr} BETWEEN ? AND ?
            ORDER BY {date_order} ASC, id ASC
        """, (start_date, end_date))
        worker_payout_transactions = cursor.fetchall()

    # Material expenses are computed from CHB production quantities and stored
    # inventory material costs.
    material_expenses = 0
    expense_transactions = []
    expense_summary_by_date = {}
    material_cost_basis = _fetch_material_cost_basis(cursor)
    chb_material_records = []
    if date_expr:
        if "cement_bags" in chb_cols:
            cement_col = "cement_bags"
        elif "cement_consumed" in chb_cols:
            cement_col = "cement_consumed"
        else:
            cement_col = None

        fine_sand_expr = "COALESCE(fine_sand, 0)" if "fine_sand" in chb_cols else "0"
        if cement_col:
            cursor.execute(f"""
                SELECT {date_select},
                       COALESCE({cement_col}, 0) AS cement_bags,
                       {fine_sand_expr} AS fine_sand_bags
                FROM chb_production
                WHERE {date_expr} BETWEEN ? AND ?
                  AND (COALESCE({cement_col}, 0) > 0 OR {fine_sand_expr} > 0)
                ORDER BY {date_order} ASC, id ASC
            """, (start_date, end_date))
            chb_material_records = cursor.fetchall()

    for production_date, cement_bags, fine_sand_bags in chb_material_records:
        cement_qty = _safe_float(cement_bags)
        fine_sand_qty = _safe_float(fine_sand_bags)
        cement_cost = cement_qty * material_cost_basis["cement_unit_cost"]
        fine_sand_cost = fine_sand_qty * material_cost_basis["fine_sand_bag_cost"]
        row_total = cement_cost + fine_sand_cost
        material_expenses += row_total

        date_key = str(production_date or "")[:10]
        remarks = (
            f"Cement {_format_report_quantity(cement_qty)} bag/s; "
            f"Fine Sand {_format_report_quantity(fine_sand_qty)} bag/s"
        )
        if row_total <= 0:
            remarks += "; material costs not configured"

        expense_transactions.append((
            production_date,
            "CHB Material Expense",
            remarks,
            row_total,
        ))

        summary = expense_summary_by_date.setdefault(date_key, {
            "cement": 0.0,
            "fine_sand": 0.0,
            "amount": 0.0,
        })
        summary["cement"] += cement_qty
        summary["fine_sand"] += fine_sand_qty
        summary["amount"] += row_total

    expense_summary_rows = [
        (
            date_key,
            "CHB Material Expense",
            values["amount"],
            (
                f"Cement {_format_report_quantity(values['cement'])} bag/s; "
                f"Fine Sand {_format_report_quantity(values['fine_sand'])} bag/s"
            ),
        )
        for date_key, values in sorted(expense_summary_by_date.items())
    ]

    # SRS formula:
    # Revenue = Total Sales - (Material Expenses + Worker Payouts)
    total_expenses = material_expenses + worker_payouts
    total_revenue = total_sales - total_expenses

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

    has_period_data = bool(sales_transactions or chb_material_records or worker_payout_transactions)

    conn.close()

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_sales": total_sales,
        "material_expenses": material_expenses,
        "worker_payouts": worker_payouts,
        "total_expenses": total_expenses,
        "total_revenue": total_revenue,
        # Legacy aliases kept for compatibility with old callers.
        "chb_payouts": worker_payouts,
        "cash_on_hand": cash_on_hand,
        "sales_transactions": sales_transactions,
        "sales_by_product": sales_by_product,
        "expense_transactions": expense_transactions,
        "expense_summary_rows": expense_summary_rows,
        "worker_payout_transactions": worker_payout_transactions,
        "material_cost_basis": material_cost_basis,
        "material_expense_source": "Option B: CHB production usage multiplied by inventory material costs",
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
    start_date, end_date, error = get_report_date_range("Custom", custom_start=start_date, custom_end=end_date)
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

    worker_expr = "COALESCE(worker_name, '')" if "worker_name" in col_names else "''"
    fine_sand_expr = "COALESCE(fine_sand, 0)" if "fine_sand" in col_names else "0"
    if "pay" in col_names:
        if "pay_rate" in col_names:
            pay_expr = f"COALESCE(pay, COALESCE({cement_col}, 0) * COALESCE(pay_rate, 0), 0)"
        else:
            pay_expr = "COALESCE(pay, 0)"
    elif "pay_rate" in col_names:
        pay_expr = f"COALESCE({cement_col}, 0) * COALESCE(pay_rate, 0)"
    else:
        pay_expr = "0"

    cursor.execute(f"""
        SELECT
            COALESCE(SUM({cement_col}), 0) as total_cement,
            COALESCE(SUM({fine_sand_expr}), 0) as total_fine_sand,
            COALESCE(SUM({blocks_col}), 0) as total_blocks,
            COALESCE(SUM({pay_expr}), 0) as total_worker_pay
        FROM chb_production
        WHERE {date_expr} BETWEEN ? AND ?
    """, (start_date, end_date))
    result = cursor.fetchone()
    total_cement = result[0] or 0
    total_fine_sand = result[1] or 0
    total_blocks = result[2] or 0
    total_worker_pay = result[3] or 0

    cursor.execute(f"""
        SELECT
            {date_select} AS production_date,
            {worker_expr} AS worker_name,
            COALESCE({cement_col}, 0) AS cement_bags,
            {fine_sand_expr} AS fine_sand,
            COALESCE({blocks_col}, 0) AS total_blocks,
            {pay_expr} AS worker_pay
        FROM chb_production
        WHERE {date_expr} BETWEEN ? AND ?
        ORDER BY {date_order} DESC, id DESC
    """, (start_date, end_date))
    entries = [
        {
            "production_date": production_date,
            "worker_name": worker_name or "N/A",
            "cement_bags": cement_bags or 0,
            "fine_sand": fine_sand or 0,
            "total_blocks": total_blocks_row or 0,
            "worker_pay": worker_pay or 0,
        }
        for production_date, worker_name, cement_bags, fine_sand, total_blocks_row, worker_pay in cursor.fetchall()
    ]

    conn.close()

    # Calculate efficiency metrics
    efficiency = (total_blocks / total_cement * 100) if total_cement > 0 else 0

    return {
        "start_date": start_date,
        "end_date": end_date,
        "total_cement": total_cement,
        "total_fine_sand": total_fine_sand,
        "total_blocks": total_blocks,
        "total_worker_pay": total_worker_pay,
        "efficiency": efficiency,
        "entries": entries,
        "has_period_data": bool(entries),
    }, None


def generate_inventory_status():
    """REQ-REP-04: Generate Inventory Status Report."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("PRAGMA table_info(items)")
    item_cols = {col[1] for col in cursor.fetchall()}
    if "category" in item_cols:
        category_expr = "COALESCE(NULLIF(category, ''), 'N/A')"
        category_source = "category"
    elif "product_type" in item_cols:
        category_expr = "COALESCE(NULLIF(product_type, ''), 'N/A')"
        category_source = "product_type"
    elif "classification" in item_cols:
        category_expr = "COALESCE(NULLIF(classification, ''), 'N/A')"
        category_source = "classification"
    elif "unit" in item_cols:
        category_expr = "COALESCE(NULLIF(unit, ''), 'N/A')"
        category_source = "unit"
    else:
        category_expr = "'N/A'"
        category_source = "fallback"

    cursor.execute(f"""
        SELECT
            COALESCE(name, '') AS product_name,
            {category_expr} AS category,
            COALESCE(quantity, 0) AS current_stock
        FROM items
        ORDER BY quantity ASC, LOWER(name) ASC
    """)
    all_items = []
    for name, category, qty in cursor.fetchall():
        stock_status = "Low Stock" if is_low_stock_item(name, qty) else "Normal Stock"
        all_items.append({
            "product_name": name or "N/A",
            "category": category or "N/A",
            "current_stock": qty or 0,
            "stock_status": stock_status,
        })

    low_stock = [row for row in all_items if row["stock_status"] == "Low Stock"]

    conn.close()

    return {
        "all_items": all_items,
        "low_stock": low_stock,
        "total_items": len(all_items),
        "category_source": category_source,
        "has_inventory_data": bool(all_items),
    }, None


def php_money(value):
    return f"PHP {float(value or 0):,.2f}"


def _pdf_styles():
    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "ReportTitle",
        parent=styles["Heading1"],
        fontName="Helvetica-Bold",
        fontSize=19,
        leading=23,
        textColor=colors.HexColor("#111827"),
        spaceAfter=6,
    ))
    styles.add(ParagraphStyle(
        "ReportSubtitle",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#4b5563"),
    ))
    styles.add(ParagraphStyle(
        "SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=16,
        textColor=colors.HexColor("#111827"),
        spaceBefore=8,
        spaceAfter=4,
    ))
    return styles


def _pdf_report_title(report_type):
    return report_type if str(report_type).strip().lower().endswith("report") else f"{report_type} Report"


def _build_pdf_header(story, report_type, styles):
    report_title = _pdf_report_title(report_type)
    logo_cell = Paragraph("JASP", ParagraphStyle(
        "LogoFallback",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=14,
        textColor=colors.white,
        alignment=1,
    ))
    path = logo_path()
    try:
        logo_cell = Image(path, width=0.55 * inch, height=0.55 * inch)
    except Exception:
        pass

    header_data = [[
        logo_cell,
        Paragraph("JASP Hardware Management System", ParagraphStyle(
            "HeaderBrand",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=13,
            textColor=colors.white,
            leading=16,
        )),
        Paragraph(report_title, ParagraphStyle(
            "HeaderReport",
            parent=styles["Normal"],
            fontName="Helvetica-Bold",
            fontSize=12,
            textColor=colors.white,
            alignment=2,
        )),
    ]]
    header = Table(header_data, colWidths=[0.85 * inch, 3.25 * inch, 2.4 * inch])
    header.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor(PDF_HEADER_BG)),
        ("BACKGROUND", (0, 0), (0, 0), colors.HexColor(PDF_LOGO_CONTAINER_BG)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("ALIGN", (0, 0), (0, 0), "CENTER"),
        ("LEFTPADDING", (0, 0), (-1, -1), 10),
        ("RIGHTPADDING", (0, 0), (-1, -1), 10),
        ("TOPPADDING", (0, 0), (-1, -1), 10),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 10),
        ("LINEBELOW", (0, 0), (-1, -1), 1, colors.HexColor(PDF_BORDER)),
    ]))
    story.append(header)
    story.append(Spacer(1, 0.22 * inch))
    story.append(Paragraph(report_title, styles["ReportTitle"]))


def _table_style(row_backgrounds=True):
    commands = [
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor(PDF_TABLE_HEADER_BG)),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, 0), 10),
        ("BOTTOMPADDING", (0, 0), (-1, 0), 8),
        ("TOPPADDING", (0, 0), (-1, 0), 8),
        ("LEFTPADDING", (0, 0), (-1, -1), 7),
        ("RIGHTPADDING", (0, 0), (-1, -1), 7),
        ("TOPPADDING", (0, 1), (-1, -1), 5),
        ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor(PDF_BORDER)),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]
    if row_backgrounds:
        commands.append(("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor(PDF_ROW_ALT)]))
    return TableStyle(commands)


def _append_signature_footer(story, styles):
    story.append(Spacer(1, 0.32 * inch))
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["ReportSubtitle"]))
    story.append(Spacer(1, 0.3 * inch))

    signature = Table(
        [
            ["Prepared by", "Checked by", "Approved by"],
            ["", "", ""],
            ["Signature over printed name", "Signature over printed name", "Signature over printed name"],
        ],
        colWidths=[2.05 * inch, 2.05 * inch, 2.05 * inch],
    )
    signature.setStyle(TableStyle([
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#111827")),
        ("ALIGN", (0, 0), (-1, -1), "CENTER"),
        ("LINEABOVE", (0, 1), (-1, 1), 0.8, colors.HexColor(PDF_BORDER)),
        ("TOPPADDING", (0, 0), (-1, 0), 4),
        ("TOPPADDING", (0, 1), (-1, 1), 26),
        ("BOTTOMPADDING", (0, 1), (-1, 1), 4),
        ("FONTSIZE", (0, 2), (-1, 2), 8),
        ("TEXTCOLOR", (0, 2), (-1, 2), colors.HexColor("#6b7280")),
    ]))
    story.append(signature)


def _append_no_data_message(story, styles):
    story.append(Spacer(1, 0.15 * inch))
    story.append(Paragraph(NO_DATA_PERIOD_MESSAGE, styles["ReportSubtitle"]))


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

        pdf = SimpleDocTemplate(file_path, pagesize=letter,
                               rightMargin=0.5*inch, leftMargin=0.5*inch,
                               topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = _pdf_styles()

        _build_pdf_header(story, report_type, styles)

        # Build content based on report type
        if report_type == "Financial Summary":
            _build_financial_pdf(story, report_data, styles)
        elif report_type == "Sales Report":
            _build_sales_report_pdf(story, report_data, styles)
        elif report_type == "Weekly Sales Statistics":
            _build_weekly_sales_pdf(story, report_data, styles)
        elif report_type == "CHB Production":
            _build_chb_production_pdf(story, report_data, styles)
        elif report_type == "Inventory Status":
            _build_inventory_pdf(story, report_data, styles)

        _append_signature_footer(story, styles)

        pdf.build(story)
        if not os.path.isfile(file_path) or os.path.getsize(file_path) == 0:
            return False, f"PDF export failed: the file was not created.\n\nExpected path:\n{file_path}"
        return True, file_path
    except Exception as e:
        return False, f"PDF export failed: {str(e)}"


def _build_financial_pdf(story, data, styles):
    """Build financial summary PDF content."""
    story.append(Paragraph(f"Period: {data['start_date']} to {data['end_date']}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    if not data.get("has_period_data"):
        _append_no_data_message(story, styles)
        return

    total_expenses = data.get('total_expenses', data.get('material_expenses', 0) + data.get('worker_payouts', 0))
    summary_data = [
        ["Metric", "Amount"],
        ["Total Sales", php_money(data['total_sales'])],
        ["Cash on Hand (Completed Sales)", php_money(data['cash_on_hand'])],
        ["Material Expenses", php_money(data['material_expenses'])],
        ["Worker Payouts (CHB)", php_money(data['worker_payouts'])],
        ["Total Expenses", php_money(total_expenses)],
        ["Total Revenue", php_money(data['total_revenue'])],
    ]

    table = Table(summary_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle(_table_style().getCommands() + [
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(table)

    sales_transactions = data.get('sales_transactions', [])
    if sales_transactions:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Items Sold", styles['SectionHeading']))
        story.append(Spacer(1, 0.1*inch))

        sales_rows = [["Date", "Product", "Unit", "Purchased", "JASP", "Qty", "Total Purchased", "Total JASP", "Markup"]]
        for ts, item_name, qty, _price, _raw_price, total in sales_transactions:
            qty_val = _safe_float(qty)
            purchased_unit = _safe_float(_raw_price)
            jasp_unit = _safe_float(_price)
            jasp_total = _safe_float(total)
            purchased_total = purchased_unit * qty_val
            markup = jasp_total - purchased_total
            sales_rows.append([
                str(ts)[:10],
                item_name or "-",
                "pc",
                php_money(purchased_unit),
                php_money(jasp_unit),
                _format_report_quantity(qty_val),
                php_money(purchased_total),
                php_money(jasp_total),
                php_money(markup),
            ])

        sales_table = Table(
            sales_rows,
            colWidths=[0.65*inch, 1.15*inch, 0.35*inch, 0.72*inch, 0.65*inch, 0.45*inch, 0.9*inch, 0.75*inch, 0.75*inch],
        )
        sales_table.setStyle(TableStyle(_table_style(row_backgrounds=False).getCommands() + [
            ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (2, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 6),
        ]))
        story.append(sales_table)

    expense_summary_rows = data.get('expense_summary_rows', [])
    if expense_summary_rows:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Material Expenses", styles['SectionHeading']))
        story.append(Spacer(1, 0.1*inch))

        expense_rows = [["Date", "Expense Name", "Total", "Remarks"]]
        for expense_date, expense_name, total_amount, remarks in expense_summary_rows:
            expense_rows.append([
                str(expense_date)[:10],
                expense_name or "-",
                php_money(total_amount),
                remarks or "-",
            ])

        expense_table = Table(expense_rows, colWidths=[0.85*inch, 1.55*inch, 1.1*inch, 2.7*inch])
        expense_table.setStyle(TableStyle(_table_style(row_backgrounds=False).getCommands() + [
            ('ALIGN', (2, 1), (2, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 8),
        ]))
        story.append(expense_table)


def _build_sales_report_pdf(story, data, styles):
    """Build transaction-level sales report PDF content."""
    story.append(Paragraph(f"Period: {data['start_date']} to {data['end_date']}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    if not data.get("has_period_data"):
        _append_no_data_message(story, styles)
        return

    sales_rows = [["Date", "Transaction ID", "Items Sold", "Qty", "Total", "Payment", "Change"]]
    for row in data.get("transactions", []):
        sales_rows.append([
            str(row["transaction_date"])[:19],
            row["transaction_id"],
            row["items_sold"],
            row["quantities"],
            php_money(row["total_amount"]),
            php_money(row["payment_received"]),
            php_money(row["change_amount"]),
        ])

    table = Table(sales_rows, colWidths=[1.0*inch, 1.15*inch, 1.6*inch, 0.7*inch, 0.95*inch, 0.95*inch, 0.85*inch])
    table.setStyle(TableStyle(_table_style(row_backgrounds=False).getCommands() + [
        ('ALIGN', (3, 1), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (2, -1), 'LEFT'),
        ('FONTSIZE', (0, 0), (-1, -1), 7),
    ]))
    story.append(table)


def _build_weekly_sales_pdf(story, data, styles):
    """Build weekly sales PDF content."""
    story.append(Paragraph(f"Period: {data['start_date']} to {data['end_date']}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    sales_data = [["Day", "Date", "Revenue"]]
    for day, date, revenue in data['daily_data']:
        sales_data.append([day, date, php_money(revenue)])

    table = Table(sales_data, colWidths=[1.5*inch, 1.5*inch, 2*inch])
    table.setStyle(TableStyle(_table_style().getCommands() + [
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(table)


def _build_chb_production_pdf(story, data, styles):
    """Build CHB production PDF content."""
    story.append(Paragraph(f"Period: {data['start_date']} to {data['end_date']}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    if not data.get("has_period_data"):
        _append_no_data_message(story, styles)
        return

    summary_data = [
        ["Metric", "Value"],
        ["Total Cement Bags", _format_report_quantity(data['total_cement'])],
        ["Total Fine Sand", _format_report_quantity(data.get('total_fine_sand', 0))],
        ["Total Blocks Produced (pcs)", f"{data['total_blocks']:,}"],
        ["Worker Pay", php_money(data.get('total_worker_pay', 0))],
    ]

    table = Table(summary_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle(_table_style().getCommands() + [
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(table)

    if data['entries']:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Detailed Entries", styles['SectionHeading']))
        story.append(Spacer(1, 0.1*inch))

        entries_data = [["Production Date", "Worker", "Cement Bags", "Fine Sand", "Blocks", "Worker Pay"]]
        for row in data['entries']:
            entries_data.append([
                str(row.get("production_date") or "")[:10],
                row.get("worker_name") or "N/A",
                _format_report_quantity(row.get("cement_bags")),
                _format_report_quantity(row.get("fine_sand")),
                f"{int(float(row.get('total_blocks') or 0)):,}",
                php_money(row.get("worker_pay")),
            ])

        entries_table = Table(entries_data, colWidths=[1.0*inch, 1.2*inch, 0.9*inch, 0.9*inch, 0.9*inch, 1.0*inch])
        entries_table.setStyle(TableStyle(_table_style(row_backgrounds=False).getCommands() + [
            ('ALIGN', (2, 1), (-1, -1), 'RIGHT'),
            ('ALIGN', (0, 0), (1, -1), 'LEFT'),
            ('FONTSIZE', (0, 0), (-1, -1), 7),
        ]))
        story.append(entries_table)


def _build_inventory_pdf(story, data, styles):
    """Build inventory status PDF content."""
    story.append(Paragraph(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
    story.append(Spacer(1, 0.2*inch))

    if not data.get("has_inventory_data"):
        _append_no_data_message(story, styles)
        return

    summary_data = [
        ["Metric", "Value"],
        ["Total Items", str(data['total_items'])],
        ["Low Stock Items", str(len(data['low_stock']))],
    ]

    table = Table(summary_data, colWidths=[3*inch, 2*inch])
    table.setStyle(TableStyle(_table_style().getCommands() + [
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
    ]))
    story.append(table)

    if data['low_stock']:
        story.append(Spacer(1, 0.2*inch))
        story.append(Paragraph("Low Stock Items", styles['SectionHeading']))
        story.append(Spacer(1, 0.1*inch))

        items_data = [["Product Name", "Category", "Current Stock", "Stock Status"]]
        for row in data['low_stock']:
            items_data.append([
                row.get("product_name") or "N/A",
                row.get("category") or "N/A",
                _format_report_quantity(row.get("current_stock")),
                row.get("stock_status") or "Low Stock",
            ])

        items_table = Table(items_data, colWidths=[2.0*inch, 1.3*inch, 1.1*inch, 1.2*inch])
        items_table.setStyle(TableStyle(_table_style().getCommands() + [
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ]))
        story.append(items_table)

    story.append(Spacer(1, 0.2*inch))
    story.append(Paragraph("All Inventory Items", styles['SectionHeading']))
    story.append(Spacer(1, 0.1*inch))

    all_items_data = [["Product Name", "Category", "Current Stock", "Stock Status"]]
    for row in data['all_items']:
        all_items_data.append([
            row.get("product_name") or "N/A",
            row.get("category") or "N/A",
            _format_report_quantity(row.get("current_stock")),
            row.get("stock_status") or "Normal Stock",
        ])

    all_items_table = Table(all_items_data, colWidths=[2.0*inch, 1.3*inch, 1.1*inch, 1.2*inch])
    all_items_table.setStyle(TableStyle(_table_style(row_backgrounds=False).getCommands() + [
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
    ]))
    story.append(all_items_table)
