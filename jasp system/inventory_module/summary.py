import calendar
import os
import sqlite3
import tkinter as tk
from tkinter import font as tkfont
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from .inventory_database import DB_NAME
from .inventory_functions import show_inventory_error, show_inventory_success
from jasp_theme import DASHBOARD_CONTENT_BG

# Text shown when no inventory records exist for the selected period.
NO_INVENTORY_ACTIVITY_TEXT = "No inventory activity for this period"


def center_window(window, width=None, height=None, parent=None):
    # Center a popup over its parent window or the screen.
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
    # Create summary-related tables and backfill columns used by reports.
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
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS inventory_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER,
            item_name TEXT NOT NULL,
            qty INTEGER NOT NULL DEFAULT 0,
            action_status TEXT NOT NULL,
            ts TEXT NOT NULL,
            responsible_user TEXT DEFAULT ''
        )
    """)
    cursor.execute("PRAGMA table_info(inventory_logs)")
    log_columns = [col[1] for col in cursor.fetchall()]
    if "responsible_user" not in log_columns:
        # Backfill responsible user tracking for older inventory log tables.
        cursor.execute("ALTER TABLE inventory_logs ADD COLUMN responsible_user TEXT DEFAULT ''")
    cursor.execute("PRAGMA table_info(items)")
    item_columns = [col[1] for col in cursor.fetchall()]
    if "status" not in item_columns:
        # Backfill status values for older item tables.
        cursor.execute("ALTER TABLE items ADD COLUMN status TEXT DEFAULT 'Active'")
        cursor.execute("UPDATE items SET status='Active' WHERE status IS NULL OR status=''")
    if "date_added" not in item_columns:
        # Backfill date_added for older item tables.
        cursor.execute("ALTER TABLE items ADD COLUMN date_added TEXT DEFAULT ''")
        cursor.execute(
            "UPDATE items SET date_added=? WHERE date_added IS NULL OR date_added=''",
            (datetime.now().strftime("%Y-%m-%d %H:%M:%S"),)
        )
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS pdf_downloads (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            module TEXT NOT NULL,
            downloaded_at TEXT NOT NULL,
            location TEXT NOT NULL
        )
    """)


def save_pdf_download(cursor, module, location):
    # Store one exported PDF location with its download timestamp.
    downloaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO pdf_downloads (module, downloaded_at, location) VALUES (?, ?, ?)",
        (module, downloaded_at, location),
    )
    return downloaded_at


def fetch_pdf_downloads(cursor, module, start_date=None, end_date=None):
    # Load exported PDF history, optionally filtered by a date range.
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


def fetch_summary_rows(cursor, start_date, end_date):
    # Fetch inventory activity rows for logs, restocks, and inactive item records.
    ensure_summary_tables(cursor)
    cursor.execute(
        """
        SELECT
            l.item_name,
            COALESCE(i.unit, '') AS unit,
            l.qty,
            l.ts AS date_added,
            l.action_status AS status,
            COALESCE(NULLIF(l.responsible_user, ''), 'Admin') AS responsible_user
        FROM inventory_logs l
        LEFT JOIN items i ON LOWER(i.name) = LOWER(l.item_name)
        WHERE DATE(l.ts) BETWEEN ? AND ?
        UNION ALL
        SELECT
            r.item_name,
            COALESCE(i.unit, '') AS unit,
            r.qty,
            r.ts AS date_added,
            'Restock' AS status,
            'Admin' AS responsible_user
        FROM restocks r
        LEFT JOIN items i ON LOWER(i.name) = LOWER(r.item_name)
        WHERE DATE(r.ts) BETWEEN ? AND ?
          AND NOT EXISTS (
              SELECT 1
              FROM inventory_logs l2
              WHERE LOWER(l2.item_name) = LOWER(r.item_name)
                AND l2.qty = r.qty
                AND l2.ts = r.ts
          )
        UNION ALL
        SELECT
            i.name,
            COALESCE(i.unit, '') AS unit,
            COALESCE(i.quantity, 0),
            COALESCE(NULLIF(i.date_added, ''), '') AS date_added,
            COALESCE(i.status, 'Active') AS status,
            'Admin' AS responsible_user
        FROM items i
        WHERE COALESCE(i.status, 'Active') = 'Inactive'
          AND DATE(COALESCE(NULLIF(i.date_added, ''), '1970-01-01')) BETWEEN ? AND ?
          AND NOT EXISTS (
              SELECT 1
              FROM restocks r2
              WHERE LOWER(r2.item_name) = LOWER(i.name)
                AND DATE(r2.ts) BETWEEN ? AND ?
          )
          AND NOT EXISTS (
              SELECT 1
              FROM inventory_logs l3
              WHERE LOWER(l3.item_name) = LOWER(i.name)
                AND DATE(l3.ts) BETWEEN ? AND ?
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
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
            start_date.strftime("%Y-%m-%d"),
            end_date.strftime("%Y-%m-%d"),
        )
    )
    return cursor.fetchall()


def open_date_calendar(parent, date_var, on_select=None):
    # Open a small calendar popup for selecting a YYYY-MM-DD date.
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
        # Apply the selected day and run the optional callback.
        date_var.set(f"{year_var.get():04d}-{month_var.get():02d}-{day:02d}")
        if callable(on_select):
            on_select()
        cal_win.destroy()

    def change_month(delta):
        # Move the calendar view backward or forward by one month.
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
        # Redraw the calendar grid for the selected month and year.
        for child in grid_frame.winfo_children():
            child.destroy()

        title_var.set(f"{calendar.month_name[month_var.get()]} {year_var.get()}")
        for col, day_name in enumerate(["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]):
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
    center_window(cal_win, 470, 390, parent=parent)


def open_inventory_summary(parent, anchor_parent=None):
    # Open the inventory activity summary window.
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    ensure_summary_tables(cursor)
    conn.commit()

    summary_win = tk.Toplevel(parent)
    summary_win.title("Inventory Summary")
    summary_win.configure(bg=DASHBOARD_CONTENT_BG)
    summary_win.transient(parent)

    # Store selected period, date, and PDF history module key.
    period_var = tk.StringVar(value="Day")
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))
    summary_title_var = tk.StringVar()
    pdf_download_module = "inventory_summary"

    def compute_range():
        # Convert selected day/week/month controls into start and end dates.
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
        # Build the summary title from the selected period.
        start, end = compute_range()
        if period_var.get() == "Day":
            return f"Inventory Summary - {start.strftime('%B %d, %Y')}"
        if period_var.get() == "Week":
            return f"Inventory Summary - {start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
        return f"Inventory Summary - {start.strftime('%B %Y')}"

    def get_tree_rows():
        # Return the currently visible summary table rows.
        rows = []
        for item in summary_tree.get_children():
            rows.append(summary_tree.item(item, "values"))
        return rows

    def load_summary():
        # Reload summary rows for the selected date range.
        for row in summary_tree.get_children():
            summary_tree.delete(row)

        start, end = compute_range()
        summary_title_var.set(title_text())
        rows = fetch_summary_rows(cursor, start, end)
        if not rows:
            # Show a friendly empty row when there is no inventory activity.
            summary_tree.insert("", "end", values=(NO_INVENTORY_ACTIVITY_TEXT, "", "", "", "", ""), tags=("blue_row",))
            auto_adjust_summary_columns()
            return

        for index, (item_name, unit, qty, ts, status, responsible_user) in enumerate(rows):
            tag = "blue_row" if index % 2 == 0 else "white_row"
            summary_tree.insert("", "end", values=(item_name, unit, qty, ts, status, responsible_user), tags=(tag,))
        auto_adjust_summary_columns()

    def export_pdf(file_path, rows, title):
        # Render the current inventory summary into a PDF file.
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

        # Build the PDF table with header and alternating row colors.
        table_data = [["Item Name", "Unit", "Quantity Added", "Date Added", "Status", "User"]]
        table_data.extend(rows if rows else [[NO_INVENTORY_ACTIVITY_TEXT, "", "", "", "", ""]])

        table = Table(table_data, colWidths=[1.55*inch, 1.0*inch, 1.05*inch, 1.55*inch, 0.9*inch, 0.95*inch])
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

        # Build the PDF story with title, table, and generated timestamp.
        story = [
            Paragraph(title, title_style),
            Spacer(1, 0.18*inch),
            table,
            Spacer(1, 0.18*inch),
            Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles["Normal"]),
        ]
        doc.build(story)

    def open_preview():
        # Open a preview window before exporting the summary PDF.
        load_summary()
        rows = get_tree_rows()
        title = title_text()

        # Build the preview header and table frame.
        preview = tk.Toplevel(summary_win)
        preview.title("Summary Preview")
        preview.configure(bg=DASHBOARD_CONTENT_BG)
        preview.transient(summary_win)

        tk.Label(preview, text=title, bg=DASHBOARD_CONTENT_BG, fg="#1e40af", font=("Arial", 18, "bold")).pack(anchor="w", padx=16, pady=(14, 6))

        preview_frame = tk.Frame(preview, bg="#ffffff")
        preview_frame.pack(fill="both", expand=True, padx=16, pady=8)

        # Build the preview table and scrollbar.
        cols = ("Item Name", "Unit", "Quantity Added", "Date Added", "Status", "User")
        preview_tree = ttk.Treeview(preview_frame, columns=cols, show="headings")
        preview_style = ttk.Style()
        preview_style.configure("InventorySummaryPreview.Treeview", font=("Arial", 13), rowheight=36)
        preview_style.configure("InventorySummaryPreview.Treeview.Heading", font=("Arial", 13, "bold"))
        preview_tree.configure(style="InventorySummaryPreview.Treeview")
        preview_tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=preview_tree.yview)
        scroll.pack(side="right", fill="y")
        preview_tree.configure(yscrollcommand=scroll.set)
        for col, width in (("Item Name", 200), ("Unit", 120), ("Quantity Added", 130), ("Date Added", 170), ("Status", 100), ("User", 130)):
            preview_tree.heading(col, text=col)
            preview_tree.column(col, width=width, anchor="center")
        preview_tree.tag_configure("blue_row", background="#dbeafe", foreground="#000000")
        preview_tree.tag_configure("white_row", background="#ffffff", foreground="#000000")

        # Fill the preview table with current summary rows.
        for index, row in enumerate(rows):
            tag = "blue_row" if index % 2 == 0 else "white_row"
            preview_tree.insert("", "end", values=row, tags=(tag,))

        button_frame = tk.Frame(preview, bg=DASHBOARD_CONTENT_BG)
        button_frame.pack(fill="x", padx=16, pady=(4, 14))

        def choose_file_and_export():
            # Ask where to save the PDF, export it, and record the download path.
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
                save_pdf_download(cursor, pdf_download_module, file_path)
                conn.commit()
                show_inventory_success(
                    preview,
                    "PDF Downloaded Successfully",
                    f"The PDF has been downloaded successfully.\n\nSaved to:\n{file_path}",
                )
                preview.destroy()
            except Exception as exc:
                show_inventory_error(preview, "Error", f"Failed to export PDF:\n{exc}")

        tk.Button(button_frame, text="Convert to PDF", bg="#00c853", fg="white", font=("Arial", 10, "bold"), bd=2, relief="solid", command=choose_file_and_export, padx=10, pady=5).pack(side="right", padx=5)
        tk.Button(button_frame, text="Close", bg="#ff5252", fg="white", font=("Arial", 10, "bold"), bd=2, relief="solid", command=preview.destroy, padx=10, pady=5).pack(side="right", padx=5)

        center_window(preview, 760, 520, summary_win)

    # Build the summary filter controls.
    top_frame = tk.Frame(summary_win, bg=DASHBOARD_CONTENT_BG)
    top_frame.pack(fill="x", padx=16, pady=(14, 4))

    tk.Label(top_frame, text="Period:", bg=DASHBOARD_CONTENT_BG, font=("Arial", 16, "bold")).pack(side="left", padx=(0, 10))
    for period in ("Day", "Week", "Month"):
        tk.Radiobutton(top_frame, text=period, variable=period_var, value=period, bg=DASHBOARD_CONTENT_BG, font=("Arial", 15), command=load_summary).pack(side="left", padx=8)

    tk.Label(top_frame, text="Date:", bg=DASHBOARD_CONTENT_BG, font=("Arial", 16, "bold")).pack(side="left", padx=(28, 10))
    date_entry = tk.Entry(top_frame, textvariable=date_var, width=14, font=("Arial", 15), relief="solid", bd=1)
    date_entry.pack(side="left", padx=5)
    # Reuse button styling for filter actions.
    filter_button_options = {
        "width": 8,
        "font": ("Arial", 12, "bold"),
        "fg": "white",
        "relief": "solid",
        "bd": 2,
        "highlightbackground": "black",
        "highlightcolor": "black",
        "highlightthickness": 1,
        "padx": 4,
        "pady": 6,
    }
    tk.Button(top_frame, text="Calendar", bg="#2196f3", command=lambda: open_date_calendar(summary_win, date_var, load_summary), **filter_button_options).pack(side="left", padx=4)
    tk.Button(top_frame, text="Apply", bg="#1e3a8a", command=load_summary, **filter_button_options).pack(side="left", padx=4)
    tk.Button(top_frame, text="Close", bg="#dc2626", command=lambda: on_close(), **filter_button_options).pack(side="right", padx=4)

    # Show the active summary date range above the PDF action buttons.
    tk.Label(
        summary_win,
        textvariable=summary_title_var,
        bg=DASHBOARD_CONTENT_BG,
        fg="#2563eb",
        font=("Arial", 16, "bold"),
    ).pack(anchor="w", padx=16, pady=(0, 8))

    # Build PDF action buttons.
    pdf_button_frame = tk.Frame(summary_win, bg=DASHBOARD_CONTENT_BG)
    pdf_button_frame.pack(fill="x", padx=16, pady=(0, 8))
    tk.Button(pdf_button_frame, text="Convert to PDF", bg="#00c853", fg="white", font=("Arial", 13, "bold"), bd=2, relief="solid", command=open_preview, padx=14, pady=7).pack(side="left")
    tk.Button(pdf_button_frame, text="View Downloaded PDF", bg="#2563eb", fg="white", font=("Arial", 13, "bold"), bd=2, relief="solid", command=lambda: open_downloaded_pdf_window(), padx=14, pady=7).pack(side="left", padx=8)

    # Build the main summary table area.
    table_frame = tk.Frame(summary_win, bg=DASHBOARD_CONTENT_BG)
    table_frame.pack(fill="both", expand=True, padx=16, pady=(0, 14))

    # Configure the inventory summary table columns and style.
    columns = ("Item Name", "Unit", "Quantity Added", "Date Added", "Status", "User")
    summary_tree = ttk.Treeview(table_frame, columns=columns, show="headings")
    style = ttk.Style()
    style.configure("InventorySummary.Treeview", font=("Arial", 13), rowheight=36)
    style.configure("InventorySummary.Treeview.Heading", font=("Arial", 13, "bold"))
    summary_tree.configure(style="InventorySummary.Treeview")
    summary_tree.pack(side="left", fill="both", expand=True)
    table_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=summary_tree.yview)
    table_scroll.pack(side="right", fill="y")
    summary_tree.configure(yscrollcommand=table_scroll.set)

    for col, width in (("Item Name", 220), ("Unit", 130), ("Quantity Added", 140), ("Date Added", 180), ("Status", 110), ("User", 140)):
        summary_tree.heading(col, text=col)
        summary_tree.column(col, width=width, anchor="center")
    summary_tree.tag_configure("blue_row", background="#93c5fd", foreground="#000000")
    summary_tree.tag_configure("white_row", background="#ffffff", foreground="#000000")

    def auto_adjust_summary_columns():
        # Resize summary columns based on visible heading and row text lengths.
        body_font = tkfont.Font(font=("Arial", 13))
        heading_font = tkfont.Font(font=("Arial", 13, "bold"))
        max_widths = {
            "Item Name": 360,
            "Unit": 220,
            "Quantity Added": 190,
            "Date Added": 240,
            "Status": 360,
            "User": 240,
        }
        min_widths = {
            "Item Name": 180,
            "Unit": 100,
            "Quantity Added": 130,
            "Date Added": 170,
            "Status": 110,
            "User": 120,
        }
        column_ids = list(summary_tree["columns"])
        for col in column_ids:
            col_index = column_ids.index(col)
            width = max(min_widths[col], heading_font.measure(col) + 36)
            for item_id in summary_tree.get_children():
                values = summary_tree.item(item_id, "values")
                if col_index < len(values):
                    width = max(width, body_font.measure(str(values[col_index])) + 42)
            summary_tree.column(col, width=min(width, max_widths[col]), minwidth=min_widths[col], anchor="center", stretch=False)

    def open_pdf_location(path):
        # Open a saved PDF path when it still exists on disk.
        if not path or path == "Not downloaded":
            messagebox.showinfo("PDF Location", "This summary has not been downloaded yet.", parent=summary_win)
            return
        if not os.path.exists(path):
            messagebox.showwarning("PDF Missing", f"The PDF file was not found:\n{path}", parent=summary_win)
            return
        try:
            os.startfile(path)
        except OSError as exc:
            messagebox.showerror("Open Failed", f"Unable to open PDF:\n{exc}", parent=summary_win)

    def open_downloaded_pdf_window():
        # Open a window listing previously exported inventory summary PDFs.
        pdf_win = tk.Toplevel(summary_win)
        pdf_win.title("Downloaded Inventory PDFs")
        pdf_win.configure(bg=DASHBOARD_CONTENT_BG)
        pdf_win.transient(summary_win)

        header_frame = tk.Frame(pdf_win, bg=DASHBOARD_CONTENT_BG)
        header_frame.pack(fill="x", padx=14, pady=(14, 8))
        tk.Label(header_frame, text="Downloaded PDF Files", bg=DASHBOARD_CONTENT_BG, fg="#1e40af", font=("Arial", 22, "bold")).pack(side="left")
        tk.Button(header_frame, text="Close", bg="#dc2626", fg="white", font=("Arial", 12, "bold"), bd=2, relief="solid", command=pdf_win.destroy, padx=14, pady=6).pack(side="right")
        tk.Label(
            pdf_win,
            text="Click the PDF location to open or view the downloaded PDF.",
            bg=DASHBOARD_CONTENT_BG,
            fg="#334155",
            font=("Arial", 15, "bold"),
        ).pack(anchor="w", padx=14, pady=(0, 8))

        pdf_period_var = tk.StringVar(value="Day")
        pdf_date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

        def compute_pdf_range():
            # Convert downloaded-PDF filters into a date range.
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
            # Return a friendly message when no PDFs match the selected period.
            period = pdf_period_var.get()
            if period == "Day":
                if pdf_date_var.get() == datetime.now().strftime("%Y-%m-%d"):
                    return "No PDFs downloaded today."
                return "No PDFs downloaded on this date."
            if period == "Week":
                return "No PDFs downloaded this week."
            return "No PDFs downloaded this month."

        # Build the downloaded-PDF filter controls.
        filter_frame = tk.Frame(pdf_win, bg=DASHBOARD_CONTENT_BG)
        filter_frame.pack(fill="x", padx=14, pady=(0, 10))
        tk.Label(filter_frame, text="Period:", bg=DASHBOARD_CONTENT_BG, font=("Arial", 14, "bold")).pack(side="left", padx=(0, 8))
        for period in ("Day", "Week", "Month"):
            tk.Radiobutton(filter_frame, text=period, variable=pdf_period_var, value=period, bg=DASHBOARD_CONTENT_BG, font=("Arial", 13)).pack(side="left", padx=4)
        tk.Label(filter_frame, text="Date:", bg=DASHBOARD_CONTENT_BG, font=("Arial", 14, "bold")).pack(side="left", padx=(18, 6))
        tk.Entry(filter_frame, textvariable=pdf_date_var, width=13, font=("Arial", 13), relief="solid", bd=1).pack(side="left", padx=4)
        tk.Button(filter_frame, text="Calendar", bg="#2563eb", fg="white", font=("Arial", 12, "bold"), bd=2, relief="solid", command=lambda: open_date_calendar(pdf_win, pdf_date_var, load_pdf_records), padx=8, pady=4).pack(side="left", padx=4)
        tk.Button(filter_frame, text="Apply", bg="#059669", fg="white", font=("Arial", 12, "bold"), bd=2, relief="solid", command=lambda: load_pdf_records(), padx=8, pady=4).pack(side="left", padx=4)

        # Build the downloaded-PDF table and scrollbar.
        pdf_frame = tk.Frame(pdf_win, bg=DASHBOARD_CONTENT_BG)
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
            # Reload downloaded PDF records for the selected filter range.
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
            # Open the clicked PDF location when the location column is selected.
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
        center_window(pdf_win, 980, 540, summary_win)

    # Load initial data and center the summary window.
    load_summary()
    center_window(summary_win, 900, 560, anchor_parent or parent)

    def on_close():
        # Close the summary database connection before destroying the window.
        conn.close()
        summary_win.destroy()

    summary_win.protocol("WM_DELETE_WINDOW", on_close)
