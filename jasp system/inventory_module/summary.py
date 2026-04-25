import calendar
import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from .inventory_database import DB_NAME


def center_window(window, width=None, height=None, parent=None):
    window.update_idletasks()
    width = width or window.winfo_width()
    height = height or window.winfo_height()
    if parent and parent.winfo_exists():
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    else:
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def ensure_summary_tables(cursor):
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restocks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_name TEXT NOT NULL,
            qty INTEGER NOT NULL,
            price REAL NOT NULL,
            raw_price REAL DEFAULT 0,
            total_cost REAL NOT NULL,
            ts TEXT NOT NULL
        )
    """)
    cursor.execute("PRAGMA table_info(items)")
    item_columns = [col[1] for col in cursor.fetchall()]
    if "status" not in item_columns:
        cursor.execute("ALTER TABLE items ADD COLUMN status TEXT DEFAULT 'Active'")
        cursor.execute("UPDATE items SET status='Active' WHERE status IS NULL OR status=''")
    if "date_added" not in item_columns:
        cursor.execute("ALTER TABLE items ADD COLUMN date_added TEXT DEFAULT ''")
        cursor.execute(
            "UPDATE items SET date_added=? WHERE date_added IS NULL OR date_added=''",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
        )


def fetch_summary_rows(cursor, start_date, end_date):
    ensure_summary_tables(cursor)
    cursor.execute(
        """
        SELECT
            r.item_name,
            r.qty,
            r.ts AS date_added,
            COALESCE((
                SELECT i.status
                FROM items i
                WHERE LOWER(i.name) = LOWER(r.item_name)
                ORDER BY i.id ASC
                LIMIT 1
            ), 'Removed') AS status
        FROM restocks r
        WHERE DATE(r.ts) BETWEEN ? AND ?
        UNION ALL
        SELECT
            i.name,
            COALESCE(i.quantity, 0),
            COALESCE(NULLIF(i.date_added, ''), '') AS date_added,
            COALESCE(i.status, 'Active') AS status
        FROM items i
        WHERE COALESCE(i.status, 'Active') = 'Inactive'
          AND DATE(COALESCE(NULLIF(i.date_added, ''), '1970-01-01')) BETWEEN ? AND ?
          AND NOT EXISTS (
              SELECT 1
              FROM restocks r2
              WHERE LOWER(r2.item_name) = LOWER(i.name)
                AND DATE(r2.ts) BETWEEN ? AND ?
          )
        ORDER BY date_added DESC
        """,
        (
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )
    )
    return cursor.fetchall()


def open_date_calendar(parent, date_var, on_select=None):
    try:
        selected_date = datetime.strptime(date_var.get(), "%Y-%m-%d")
    except Exception:
        selected_date = datetime.now()

    cal_win = tk.Toplevel(parent)
    cal_win.title("Select Date")
    cal_win.configure(bg="#ffffff")
    cal_win.resizable(False, False)
    cal_win.transient(parent)
    cal_win.grab_set()

    year_var = tk.IntVar(value=selected_date.year)
    month_var = tk.IntVar(value=selected_date.month)
    title_var = tk.StringVar()

    header = tk.Frame(cal_win, bg="#ffffff")
    header.pack(fill="x", padx=10, pady=(10, 4))

    grid_frame = tk.Frame(cal_win, bg="#ffffff")
    grid_frame.pack(padx=10, pady=(0, 10))

    def select_date(day):
        date_var.set(f"{year_var.get():04d}-{month_var.get():02d}-{day:02d}")
        if callable(on_select):
            on_select()
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
        for col, day_name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
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
    center_window(cal_win, parent=parent)


def open_inventory_summary(parent):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    ensure_summary_tables(cursor)
    conn.commit()

    summary_win = tk.Toplevel(parent)
    summary_win.title("Inventory Summary")
    summary_win.configure(bg="#f4f6f9")
    summary_win.transient(parent)

    period_var = tk.StringVar(value="Day")
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

    def compute_range():
        try:
            selected = datetime.strptime(date_var.get(), "%Y-%m-%d")
        except Exception:
            selected = datetime.now()
            date_var.set(selected.strftime("%Y-%m-%d"))

        period = period_var.get()
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

    def title_text():
        start, end = compute_range()
        if period_var.get() == "Day":
            return f"Inventory Summary - {start.strftime('%B %d, %Y')}"
        if period_var.get() == "Week":
            return f"Inventory Summary - {start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
        return f"Inventory Summary - {start.strftime('%B %Y')}"

    def get_tree_rows():
        rows = []
        for item in summary_tree.get_children():
            rows.append(summary_tree.item(item, "values"))
        return rows

    def load_summary():
        for row in summary_tree.get_children():
            summary_tree.delete(row)

        start, end = compute_range()
        rows = fetch_summary_rows(cursor, start, end)
        for index, (item_name, qty, ts, status) in enumerate(rows):
            tag = "blue_row" if index % 2 == 0 else "white_row"
            summary_tree.insert("", "end", values=(item_name, qty, ts, status), tags=(tag,))

    def export_pdf(file_path, rows, title):
        doc = SimpleDocTemplate(file_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "SummaryTitle",
            parent=styles["Heading1"],
            fontSize=17,
            textColor=colors.HexColor("#2563eb"),
            alignment=1,
            spaceAfter=12,
        )

        table_data = [["Item Name", "Quantity Added", "Date Added", "Status"]]
        table_data.extend(rows if rows else [["No records", "", "", ""]])

        table = Table(table_data, colWidths=[2.2*inch, 1.35*inch, 2.0*inch, 1.1*inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#2563eb")),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("GRID", (0, 0), (-1, -1), 0.75, colors.black),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.HexColor("#dbeafe"), colors.white]),
        ]))

        story = [
            Paragraph(title, title_style),
            Spacer(1, 0.18*inch),
            table,
            Spacer(1, 0.18*inch),
            Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]),
        ]
        doc.build(story)

    def open_preview():
        load_summary()
        rows = get_tree_rows()
        title = title_text()

        preview = tk.Toplevel(summary_win)
        preview.title("Summary Preview")
        preview.configure(bg="#ffffff")
        preview.transient(summary_win)

        tk.Label(preview, text=title, bg="#ffffff", fg="#1e40af", font=("Arial", 18, "bold")).pack(anchor="w", padx=16, pady=(14, 6))

        preview_frame = tk.Frame(preview, bg="#ffffff")
        preview_frame.pack(fill="both", expand=True, padx=16, pady=8)

        cols = ("Item Name", "Quantity Added", "Date Added", "Status")
        preview_tree = ttk.Treeview(preview_frame, columns=cols, show="headings")
        preview_style = ttk.Style()
        preview_style.configure("InventorySummaryPreview.Treeview", font=("Arial", 13), rowheight=36)
        preview_style.configure("InventorySummaryPreview.Treeview.Heading", font=("Arial", 13, "bold"))
        preview_tree.configure(style="InventorySummaryPreview.Treeview")
        preview_tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=preview_tree.yview)
        scroll.pack(side="right", fill="y")
        preview_tree.configure(yscrollcommand=scroll.set)
        for col, width in (("Item Name", 250), ("Quantity Added", 140), ("Date Added", 180), ("Status", 110)):
            preview_tree.heading(col, text=col)
            preview_tree.column(col, width=width, anchor="center")
        preview_tree.tag_configure("blue_row", background="#dbeafe", foreground="#000000")
        preview_tree.tag_configure("white_row", background="#ffffff", foreground="#000000")

        for index, row in enumerate(rows):
            tag = "blue_row" if index % 2 == 0 else "white_row"
            preview_tree.insert("", "end", values=row, tags=(tag,))

        button_frame = tk.Frame(preview, bg="#ffffff")
        button_frame.pack(fill="x", padx=16, pady=(4, 14))

        def choose_file_and_export():
            file_path = filedialog.asksaveasfilename(
                parent=preview,
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
                initialfile=f"inventory_summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
            )
            if not file_path:
                return
            try:
                export_pdf(file_path, rows, title)
                messagebox.showinfo("Success", f"PDF exported successfully!\n{file_path}", parent=preview)
                preview.destroy()
            except Exception as exc:
                messagebox.showerror("Error", f"Failed to export PDF:\n{exc}", parent=preview)

        tk.Button(button_frame, text="Convert to PDF", bg="#00c853", fg="white", font=("Arial", 10, "bold"), bd=2, relief="solid", command=choose_file_and_export, padx=10, pady=5).pack(side="right", padx=5)
        tk.Button(button_frame, text="Close", bg="#ff5252", fg="white", font=("Arial", 10, "bold"), bd=2, relief="solid", command=preview.destroy, padx=10, pady=5).pack(side="right", padx=5)

        center_window(preview, 760, 520, summary_win)

    top_frame = tk.Frame(summary_win, bg="#f4f6f9")
    top_frame.pack(fill="x", padx=16, pady=(14, 4))

    tk.Label(top_frame, text="Period:", bg="#f4f6f9", font=("Arial", 13, "bold")).pack(side="left", padx=(0, 8))
    for period in ("Day", "Week", "Month"):
        tk.Radiobutton(top_frame, text=period, variable=period_var, value=period, bg="#f4f6f9", font=("Arial", 12), command=load_summary).pack(side="left", padx=6)

    tk.Label(top_frame, text="Date:", bg="#f4f6f9", font=("Arial", 13, "bold")).pack(side="left", padx=(24, 8))
    date_entry = tk.Entry(top_frame, textvariable=date_var, width=14, font=("Arial", 12), relief="solid", bd=1)
    date_entry.pack(side="left", padx=4)
    tk.Button(top_frame, text="Cal", bg="#2196f3", fg="white", font=("Arial", 10, "bold"), relief="flat", command=lambda: open_date_calendar(summary_win, date_var, load_summary), padx=8, pady=4).pack(side="left", padx=4)
    tk.Button(top_frame, text="Apply", bg="#2563eb", fg="white", font=("Arial", 10, "bold"), relief="flat", command=load_summary, padx=10, pady=4).pack(side="left", padx=8)

    pdf_button_frame = tk.Frame(summary_win, bg="#f4f6f9")
    pdf_button_frame.pack(fill="x", padx=16, pady=(0, 8))
    tk.Button(pdf_button_frame, text="Convert to PDF", bg="#00c853", fg="white", font=("Arial", 10, "bold"), bd=2, relief="solid", command=open_preview, padx=10, pady=4).pack(side="left")

    table_frame = tk.Frame(summary_win, bg="#f4f6f9")
    table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    columns = ("Item Name", "Quantity Added", "Date Added", "Status")
    summary_tree = ttk.Treeview(table_frame, columns=columns, show="headings")
    style = ttk.Style()
    style.configure("InventorySummary.Treeview", font=("Arial", 13), rowheight=36)
    style.configure("InventorySummary.Treeview.Heading", font=("Arial", 13, "bold"))
    summary_tree.configure(style="InventorySummary.Treeview")
    summary_tree.pack(side="left", fill="both", expand=True)
    table_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=summary_tree.yview)
    table_scroll.pack(side="right", fill="y")
    summary_tree.configure(yscrollcommand=table_scroll.set)

    for col, width in (("Item Name", 260), ("Quantity Added", 150), ("Date Added", 190), ("Status", 120)):
        summary_tree.heading(col, text=col)
        summary_tree.column(col, width=width, anchor="center")
    summary_tree.tag_configure("blue_row", background="#93c5fd", foreground="#000000")
    summary_tree.tag_configure("white_row", background="#ffffff", foreground="#000000")

    load_summary()
    center_window(summary_win, 860, 560, parent)

    def on_close():
        conn.close()
        summary_win.destroy()

    summary_win.protocol("WM_DELETE_WINDOW", on_close)
