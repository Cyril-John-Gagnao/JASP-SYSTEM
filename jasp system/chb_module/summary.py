import calendar
import os
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from .chb_database import fetch_production_summary, fetch_chb_adjustment_summary, fetch_latest_production_date

# Reuse a bordered button style for summary and PDF windows.
SUMMARY_BUTTON_BORDER = {
    'bd': 2,
    'relief': 'solid',
    'highlightthickness': 1,
    'highlightbackground': 'black',
    'highlightcolor': 'black',
}
SUCCESS_GREEN = "#16a34a"


def parse_currency(value):
    # Convert a displayed currency string into a numeric value for totals.
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    return float(cleaned or 0)


def center_popup(window, width, height, parent=None):
    # Center a popup over its parent window or the screen.
    window.update_idletasks()
    if parent and parent.winfo_exists():
        parent.update_idletasks()
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    else:
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{x}+{y}")


def show_chb_summary_success(parent, title, message):
    # Show a modal success popup after exporting a summary PDF.
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)

    tk.Frame(popup, bg=SUCCESS_GREEN, height=12).pack(fill="x")

    content = tk.Frame(popup, bg="#ffffff", padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text=title,
        bg="#ffffff",
        fg=SUCCESS_GREEN,
        font=("Arial", 28, "bold")
    ).pack(pady=(0, 14))

    tk.Label(
        content,
        text=message,
        bg="#ffffff",
        fg="#111827",
        font=("Arial", 17),
        wraplength=440,
        justify="center"
    ).pack(pady=(0, 28))

    def close_popup():
        # Close the success popup.
        popup.destroy()

    # Build the confirmation button for the success popup.
    ok_btn = tk.Button(
        content,
        text="OK",
        command=close_popup,
        bg=SUCCESS_GREEN,
        fg="white",
        activebackground=SUCCESS_GREEN,
        font=("Arial", 15, "bold"),
        relief="flat",
        width=14,
        pady=9
    )
    ok_btn.pack()
    ok_btn.focus_set()

    popup.bind("<Return>", lambda _event: close_popup())
    popup.bind("<Escape>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    center_popup(popup, 540, 290, parent)
    parent.wait_window(popup)


def ensure_pdf_download_table(cursor):
    # Create the table that stores exported PDF download history.
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
    ensure_pdf_download_table(cursor)
    downloaded_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute(
        "INSERT INTO pdf_downloads (module, downloaded_at, location) VALUES (?, ?, ?)",
        (module, downloaded_at, location),
    )
    cursor.connection.commit()
    return downloaded_at


def fetch_pdf_downloads(cursor, module, start_date=None, end_date=None):
    # Load exported PDF history, optionally filtered by a date range.
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


def open_date_calendar(parent, date_var, on_select=None):
    # Open a small calendar popup for selecting a YYYY-MM-DD date.
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
        # Apply the chosen day to the bound date variable.
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
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, day_name in enumerate(days):
            tk.Label(
                grid_frame,
                text=day_name,
                bg="#ffffff",
                fg="#1e293b",
                font=("Arial", 12, "bold"),
                width=6
            ).grid(row=0, column=col, padx=2, pady=3)

        today = datetime.now()
        for row_index, week in enumerate(calendar.monthcalendar(year_var.get(), month_var.get()), start=1):
            for col_index, day in enumerate(week):
                if day == 0:
                    tk.Label(grid_frame, text="", bg="#ffffff", width=6).grid(row=row_index, column=col_index, padx=2, pady=2)
                    continue

                is_today = (
                    day == today.day and
                    month_var.get() == today.month and
                    year_var.get() == today.year
                )
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

    tk.Button(header, text="Close", command=cal_win.destroy, bg="#dc2626", fg="white", activebackground="#b91c1c", activeforeground="white", relief="solid", bd=1, font=("Arial", 12, "bold"), padx=10, pady=4).pack(side="right", padx=(8, 0))
    tk.Button(header, text=">", command=lambda: change_month(1), bg="#e0f2fe", relief="solid", bd=1, width=5, font=("Arial", 13, "bold")).pack(side="right")
    tk.Button(header, text="<", command=lambda: change_month(-1), bg="#e0f2fe", relief="solid", bd=1, width=5, font=("Arial", 13, "bold")).pack(side="left")
    tk.Label(header, textvariable=title_var, bg="#ffffff", fg="#1e293b", font=("Arial", 15, "bold"), width=20).pack(side="left", padx=10)

    render_calendar()

    # Position the calendar near the center of the parent window.
    cal_win.update_idletasks()
    x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (cal_win.winfo_width() // 2)
    y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (cal_win.winfo_height() // 2)
    cal_win.geometry(f"470x390+{x}+{y}")


def open_period_summary(win, cursor, BG_MAIN, TEXT):
    # Open the CHB production or adjustment summary window.
    default_date = datetime.now()
    ensure_pdf_download_table(cursor)
    cursor.connection.commit()

    def compute_range():
        # Convert the selected day/week/month controls into start and end dates.
        p = period_var.get()
        if p == 'day':
            d = datetime.strptime(date_sel.get(), "%Y-%m-%d")
            start = d
            end = d
        elif p == 'week':
            d = datetime.strptime(date_sel.get(), "%Y-%m-%d")
            start = d - timedelta(days=d.weekday())
            end = start + timedelta(days=6)
        elif p == 'month':
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
        # Reload summary rows for the selected period and summary type.
        for r in summary_tree.get_children():
            summary_tree.delete(r)

        start, end = compute_range()
        configure_summary_columns()
        summary_title_var.set(get_summary_title())
        summary_type = summary_type_var.get()
        rows = fetch_chb_adjustment_summary(cursor, start, end) if summary_type == "adjustment" else fetch_production_summary(cursor, start, end)
        total_blocks = 0
        total_pay = 0
        total_added = 0
        total_subtracted = 0
        if not rows:
            # Show a period-specific empty row when there are no summary records.
            if summary_type == "adjustment":
                empty_text = "No stock adjustments today" if period_var.get() == "day" else "No stock adjustments in this period"
            else:
                empty_text = "No production today" if period_var.get() == "day" else "No production in this period"
            summary_tree.insert('', 'end', values=(start.strftime("%Y-%m-%d"), empty_text, "", "", ""), tags=('oddrow',))
        for i, row in enumerate(rows):
            # Insert each production or adjustment row and accumulate totals.
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            if summary_type == "adjustment":
                date, adjustment_type, quantity, reason, responsible_user = row
                if adjustment_type == "Add":
                    total_added += quantity
                else:
                    total_subtracted += quantity
                summary_tree.insert('', 'end', values=(date, adjustment_type, f"{quantity:,}", reason, responsible_user), tags=(tag,))
            else:
                date, worker, responsible_user, blocks, pay = row
                total_blocks += blocks
                total_pay += pay
                summary_tree.insert('', 'end', values=(date, worker, f"{blocks:,}", f"{chr(8369)}{pay:,.2f}", responsible_user), tags=(tag,))
        if summary_type == "adjustment":
            # Display adjustment totals as added, subtracted, and net movement.
            net_adjustment = total_added - total_subtracted
            totals_var.set(f"TOTAL ADDED: {total_added:,} | TOTAL SUBTRACTED: {total_subtracted:,} | NET: {net_adjustment:,}")
        else:
            # Display production totals as total blocks and total pay.
            totals_var.set(f"TOTAL BLOCKS: {total_blocks:,} | TOTAL WORKER PAY: {chr(8369)}{total_pay:,.2f}")
    def get_summary_title():
        # Build a PDF/window title from the selected period and summary type.
        p = period_var.get()
        start, end = compute_range()
        summary_name = "CHB Stock Adjustment Summary" if summary_type_var.get() == "adjustment" else "CHB Production Summary"

        if p == 'day':
            title_text = f"Daily {summary_name} - {start.strftime('%B %d, %Y')}"
        elif p == 'week':
            title_text = f"Weekly {summary_name} - {start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
        else:
            title_text = f"Monthly {summary_name} - {start.strftime('%B %Y')}"
        return title_text

    def get_summary_table_data():
        # Convert visible summary table rows into ReportLab table data and totals.
        tree_data = []
        for item in summary_tree.get_children():
            values = summary_tree.item(item, 'values')
            tree_data.append(values)

        if summary_type_var.get() == "adjustment":
            # Build adjustment export rows and calculate add/subtract totals.
            table_data = [['Adjustment Date', 'Type', 'Quantity', 'Reason', 'User']]
            total_added = 0
            total_subtracted = 0
            for row in tree_data:
                date, adjustment_type, quantity, reason, responsible_user = row[:5]
                if not quantity:
                    continue
                quantity_int = int(str(quantity).replace(',', ''))
                if adjustment_type == "Add":
                    total_added += quantity_int
                else:
                    total_subtracted += quantity_int
                table_data.append([date, adjustment_type, quantity, reason, responsible_user])
            net_adjustment = total_added - total_subtracted
            table_data.append(['', 'NET', f"{net_adjustment:,}", f"Added: {total_added:,} | Subtracted: {total_subtracted:,}", ''])
            return table_data, total_added, total_subtracted, net_adjustment

        # Build production export rows and calculate block/pay totals.
        table_data = [['Production Date', 'Worker Name', 'Total Blocks', 'Total Pay', 'User']]
        total_blocks = 0
        total_pay = 0

        for row in tree_data:
            date, worker, blocks, pay, responsible_user = row[:5]
            if not blocks or not pay:
                continue
            blocks_int = int(str(blocks).replace(',', ''))
            pay_float = parse_currency(pay)

            total_blocks += blocks_int
            total_pay += pay_float
            table_data.append([date, worker, blocks, pay, responsible_user])

        table_data.append(['', 'TOTAL', f"{total_blocks:,}", f"{chr(8369)}{total_pay:,.2f}", ''])
        return table_data, total_blocks, total_pay, None

    def save_summary_pdf(file_path, title_text, table_data):
        # Render the current CHB summary into a PDF file.
        pdf = SimpleDocTemplate(file_path, pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        elements = []

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=18,
            textColor=colors.HexColor('#2563eb'),
            spaceAfter=12,
            alignment=1
        )

        elements.append(Paragraph(title_text, title_style))

        # Build the PDF table with header, alternating rows, and total styling.
        table = Table(table_data, colWidths=[1.35*inch, 1.35*inch, 1.25*inch, 2.2*inch, 1.25*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#93c5fd')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#e0f2fe')]),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))

        # Add the generated timestamp footer to the PDF.
        footer_style = ParagraphStyle(
            'Footer',
            parent=styles['Normal'],
            fontSize=9,
            textColor=colors.grey,
            alignment=1
        )
        elements.append(Paragraph(f"Generated on {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", footer_style))

        pdf.build(elements)

    def open_pdf_preview():
        # Open a preview window before saving the summary as a PDF.
        try:
            load_summary()
            title_text = get_summary_title()
            table_data, first_total, second_total, net_total = get_summary_table_data()

            # Build the preview window header and summary table.
            preview_win = tk.Toplevel(summary_win)
            preview_win.title('Summary Preview')
            preview_win.geometry('980x620')
            preview_win.configure(bg=BG_MAIN)
            preview_win.transient(summary_win)

            preview_win.update_idletasks()
            x = (preview_win.winfo_screenwidth() // 2) - (980 // 2)
            y = (preview_win.winfo_screenheight() // 2) - (620 // 2)
            preview_win.geometry(f'980x620+{x}+{y}')

            header_frame = tk.Frame(preview_win, bg=BG_MAIN)
            header_frame.pack(fill='x', padx=16, pady=(14, 8))

            tk.Label(
                header_frame,
                text=title_text,
                bg=BG_MAIN,
                fg='#1e40af',
                font=('Arial', 22, 'bold')
            ).pack(anchor='w')

            preview_cols = ('date', 'second', 'third', 'fourth', 'user')
            preview_tree = ttk.Treeview(preview_win, columns=preview_cols, show='headings', style='Summary.Treeview')
            headings = table_data[0]
            widths = [150, 190, 150, 300, 170] if summary_type_var.get() == "adjustment" else [150, 250, 150, 150, 190]
            anchors = ['center', 'w', 'center', 'w' if summary_type_var.get() == "adjustment" else 'center', 'w']
            for col, heading, width, anchor in zip(preview_cols, headings, widths, anchors):
                preview_tree.heading(col, text=heading)
                preview_tree.column(col, width=width, anchor=anchor)
            preview_tree.pack(fill='both', expand=True, padx=16, pady=8)
            preview_tree.tag_configure('oddrow', background='#ffffff', font=('Arial', 15))
            preview_tree.tag_configure('evenrow', background='#93c5fd', font=('Arial', 15))

            # Fill the preview table with export rows excluding the final total row.
            for index, row in enumerate(table_data[1:-1]):
                tag = 'evenrow' if index % 2 == 0 else 'oddrow'
                preview_tree.insert('', 'end', values=row, tags=(tag,))

            if summary_type_var.get() == "adjustment":
                # Display adjustment totals below the preview table.
                total_text = f"TOTAL ADDED: {first_total:,} | TOTAL SUBTRACTED: {second_total:,} | NET: {net_total:,}"
            else:
                # Display production totals below the preview table.
                total_text = f"TOTAL BLOCKS: {first_total:,} | TOTAL WORKER PAY: {chr(8369)}{second_total:,.2f}"
            tk.Label(
                preview_win,
                text=total_text,
                bg=BG_MAIN,
                fg='#1e40af',
                font=('Arial', 17, 'bold')
            ).pack(fill='x', padx=16, pady=(0, 10))

            action_frame = tk.Frame(preview_win, bg=BG_MAIN)
            action_frame.pack(fill='x', padx=16, pady=(0, 14))

            def choose_file_and_save():
                # Ask where to save the PDF, export it, and record the download path.
                try:
                    file_path = filedialog.asksaveasfilename(
                        parent=preview_win,
                        defaultextension='.pdf',
                        filetypes=[('PDF files', '*.pdf'), ('All files', '*.*')],
                        initialfile=f"summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
                    )

                    if not file_path:
                        return

                    save_summary_pdf(file_path, title_text, table_data)
                    save_pdf_download(cursor, pdf_download_module, file_path)
                    show_chb_summary_success(
                        preview_win,
                        'PDF Downloaded Successfully',
                        f"The PDF has been downloaded successfully.\n\nSaved to:\n{file_path}"
                    )
                    preview_win.destroy()

                except Exception as e:
                    messagebox.showerror('Error', f"Failed to export PDF:\n{str(e)}", parent=preview_win)

            tk.Button(
                action_frame,
                text='Save as PDF',
                command=choose_file_and_save,
                bg='#059669',
                fg='white',
                font=('Arial', 14, 'bold'),
                width=16,
                padx=12,
                pady=8,
                **SUMMARY_BUTTON_BORDER
            ).pack(side='right', padx=6)

            tk.Button(
                action_frame,
                text='Close Preview',
                command=preview_win.destroy,
                bg='#64748b',
                fg='white',
                font=('Arial', 14, 'bold'),
                width=16,
                padx=12,
                pady=8,
                **SUMMARY_BUTTON_BORDER
            ).pack(side='right', padx=6)

        except Exception as e:
            messagebox.showerror('Error', f"Failed to preview summary:\n{str(e)}", parent=summary_win)

    # Create the main summary window and center it on screen.
    summary_win = tk.Toplevel(win)
    summary_win.title('Production Summary')
    summary_win.geometry('1100x650')
    summary_win.configure(bg=BG_MAIN)

    summary_win.update_idletasks()
    x = (summary_win.winfo_screenwidth() // 2) - (1100 // 2)
    y = (summary_win.winfo_screenheight() // 2) - (650 // 2)
    summary_win.geometry(f'1100x650+{x}+{y}')

    # Build the period filter controls at the top of the summary window.
    top_frame = tk.Frame(summary_win, bg=BG_MAIN)
    top_frame.pack(fill='x', pady=12, padx=10)

    # Store selected period, summary type, and PDF history module key.
    period_var = tk.StringVar(value='day')
    summary_type_var = tk.StringVar(value='production')
    summary_title_var = tk.StringVar()
    pdf_download_module = 'chb_summary'

    # Build the date selector and close button row.
    tk.Label(top_frame, text='Period:', bg=BG_MAIN, font=('Arial', 15, 'bold'), fg=TEXT).pack(side='left', padx=6)
    tk.Radiobutton(top_frame, text='Day', variable=period_var, value='day', bg=BG_MAIN, font=('Arial', 13), command=load_summary).pack(side='left', padx=8)
    tk.Radiobutton(top_frame, text='Week', variable=period_var, value='week', bg=BG_MAIN, font=('Arial', 13), command=load_summary).pack(side='left', padx=8)
    tk.Radiobutton(top_frame, text='Month', variable=period_var, value='month', bg=BG_MAIN, font=('Arial', 13), command=load_summary).pack(side='left', padx=8)

    date_frame = tk.Frame(top_frame, bg=BG_MAIN)
    date_frame.pack(side='left', padx=(30, 10))

    tk.Label(date_frame, text='Date:', bg=BG_MAIN, font=('Arial', 15, 'bold'), fg=TEXT).pack(side='left', padx=(0, 6))
    date_sel = tk.StringVar(value=default_date.strftime('%Y-%m-%d'))
    date_entry2 = tk.Entry(date_frame, textvariable=date_sel, width=15, font=('Arial', 14), relief='solid', bd=1)
    date_entry2.pack(side='left', padx=4)
    tk.Button(date_frame, text='Calendar', command=lambda: open_date_calendar(summary_win, date_sel, load_summary), bg='#3b82f6', fg='white', font=('Arial', 13, 'bold'), padx=10, pady=5, **SUMMARY_BUTTON_BORDER).pack(side='left', padx=4)
    tk.Button(date_frame, text='Apply', command=load_summary, bg='#2563eb', fg='white', font=('Arial', 13, 'bold'), padx=12, pady=5, **SUMMARY_BUTTON_BORDER).pack(side='left', padx=4)
    tk.Button(top_frame, text='Close', command=summary_win.destroy, bg='#dc2626', fg='white', font=('Arial', 13, 'bold'), padx=18, pady=5, **SUMMARY_BUTTON_BORDER).pack(side='right', padx=4)

    # Show the active CHB summary date range above the action buttons.
    tk.Label(
        summary_win,
        textvariable=summary_title_var,
        bg=BG_MAIN,
        fg='#2563eb',
        font=('Arial', 16, 'bold')
    ).pack(anchor='w', padx=12, pady=(0, 8))

    # Build the summary export and downloaded-PDF action buttons.
    btn_frame = tk.Frame(summary_win, bg=BG_MAIN)
    btn_frame.pack(fill='x', padx=12, pady=(0, 6))

    tk.Button(btn_frame, text='Preview / Convert PDF', command=open_pdf_preview, bg='#059669', fg='white', font=('Arial', 13, 'bold'), width=22, padx=14, pady=8, **SUMMARY_BUTTON_BORDER).pack(side='left', padx=4)
    tk.Button(btn_frame, text='View Downloaded PDF', command=lambda: open_downloaded_pdf_window(), bg='#2563eb', fg='white', font=('Arial', 13, 'bold'), width=22, padx=14, pady=8, **SUMMARY_BUTTON_BORDER).pack(side='left', padx=4)

    # Build the selector for production summary versus stock adjustment summary.
    summary_option_frame = tk.Frame(summary_win, bg=BG_MAIN)
    summary_option_frame.pack(fill='x', padx=12, pady=(0, 8))

    summary_option_fg = '#0f172a'
    tk.Label(summary_option_frame, text='Summary:', bg=BG_MAIN, font=('Arial', 16, 'bold'), fg=summary_option_fg).pack(side='left', padx=(4, 8))
    tk.Radiobutton(summary_option_frame, text='CHB Production', variable=summary_type_var, value='production', bg=BG_MAIN, fg=summary_option_fg, selectcolor=BG_MAIN, font=('Arial', 14, 'bold'), command=load_summary).pack(side='left', padx=8)
    tk.Radiobutton(summary_option_frame, text='CHB Stock Adjustment', variable=summary_type_var, value='adjustment', bg=BG_MAIN, fg=summary_option_fg, selectcolor=BG_MAIN, font=('Arial', 14, 'bold'), command=load_summary).pack(side='left', padx=8)

    cols = ('date', 'second', 'third', 'fourth', 'user')

    # Configure the summary table style.
    style = ttk.Style()
    style.configure('Summary.Treeview', font=('Arial', 15), rowheight=40)
    style.configure('Summary.Treeview.Heading', font=('Arial', 16, 'bold'))

    # Create the main summary table.
    summary_tree = ttk.Treeview(summary_win, columns=cols, show='headings', style='Summary.Treeview')
    summary_tree.pack(fill='both', expand=True, padx=12, pady=12)
    summary_tree.tag_configure('oddrow', background='#ffffff', font=('Arial', 15))
    summary_tree.tag_configure('evenrow', background='#93c5fd', font=('Arial', 15))

    def configure_summary_columns():
        # Change table headings based on the selected summary type.
        if summary_type_var.get() == "adjustment":
            headings = {
                'date': ('Adjustment Date', 150, 'center'),
                'second': ('Type', 150, 'center'),
                'third': ('Quantity', 150, 'center'),
                'fourth': ('Reason', 360, 'w'),
                'user': ('User', 180, 'w'),
            }
        else:
            headings = {
                'date': ('Production Date', 140, 'center'),
                'second': ('Worker Name', 260, 'w'),
                'third': ('Total Blocks', 160, 'center'),
                'fourth': ('Total Pay', 160, 'center'),
                'user': ('User', 180, 'w'),
            }
        for col, (heading, width, anchor) in headings.items():
            summary_tree.heading(col, text=heading)
            summary_tree.column(col, width=width, anchor=anchor)

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
        # Open a window listing previously exported CHB summary PDFs.
        pdf_win = tk.Toplevel(summary_win)
        pdf_win.title('Downloaded CHB PDFs')
        pdf_win.geometry('980x540')
        pdf_win.configure(bg=BG_MAIN)
        pdf_win.transient(summary_win)

        pdf_header = tk.Frame(pdf_win, bg=BG_MAIN)
        pdf_header.pack(fill='x', padx=14, pady=(14, 8))
        tk.Label(pdf_header, text='Downloaded PDF Files', bg=BG_MAIN, fg='#1e40af', font=('Arial', 22, 'bold')).pack(side='left')
        tk.Button(pdf_header, text='Close', command=pdf_win.destroy, bg='#dc2626', fg='white', font=('Arial', 12, 'bold'), padx=14, pady=6, **SUMMARY_BUTTON_BORDER).pack(side='right')
        tk.Label(
            pdf_win,
            text='Click the PDF location to open or view the downloaded PDF.',
            bg=BG_MAIN,
            fg='#334155',
            font=('Arial', 15, 'bold')
        ).pack(anchor='w', padx=14, pady=(0, 8))

        pdf_period_var = tk.StringVar(value='Day')
        pdf_date_var = tk.StringVar(value=datetime.now().strftime('%Y-%m-%d'))

        def compute_pdf_range():
            # Convert downloaded-PDF filters into a date range.
            try:
                selected = datetime.strptime(pdf_date_var.get(), '%Y-%m-%d')
            except Exception:
                selected = datetime.now()
                pdf_date_var.set(selected.strftime('%Y-%m-%d'))
            if pdf_period_var.get() == 'Week':
                start_date = selected - timedelta(days=selected.weekday())
                end_date = start_date + timedelta(days=6)
            elif pdf_period_var.get() == 'Month':
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
            if period == 'Day':
                if pdf_date_var.get() == datetime.now().strftime('%Y-%m-%d'):
                    return 'No PDFs downloaded today.'
                return 'No PDFs downloaded on this date.'
            if period == 'Week':
                return 'No PDFs downloaded this week.'
            return 'No PDFs downloaded this month.'

        # Build the downloaded-PDF filter controls.
        filter_frame = tk.Frame(pdf_win, bg=BG_MAIN)
        filter_frame.pack(fill='x', padx=14, pady=(0, 10))
        tk.Label(filter_frame, text='Period:', bg=BG_MAIN, font=('Arial', 14, 'bold')).pack(side='left', padx=(0, 8))
        for period in ('Day', 'Week', 'Month'):
            tk.Radiobutton(filter_frame, text=period, variable=pdf_period_var, value=period, bg=BG_MAIN, font=('Arial', 13)).pack(side='left', padx=4)
        tk.Label(filter_frame, text='Date:', bg=BG_MAIN, font=('Arial', 14, 'bold')).pack(side='left', padx=(18, 6))
        tk.Entry(filter_frame, textvariable=pdf_date_var, width=13, font=('Arial', 13), relief='solid', bd=1).pack(side='left', padx=4)
        tk.Button(filter_frame, text='Calendar', command=lambda: open_date_calendar(pdf_win, pdf_date_var, load_pdf_records), bg='#2563eb', fg='white', font=('Arial', 12, 'bold'), padx=8, pady=4, **SUMMARY_BUTTON_BORDER).pack(side='left', padx=4)
        tk.Button(filter_frame, text='Apply', command=lambda: load_pdf_records(), bg='#059669', fg='white', font=('Arial', 12, 'bold'), padx=8, pady=4, **SUMMARY_BUTTON_BORDER).pack(side='left', padx=4)

        # Build the downloaded-PDF table and scrollbar.
        pdf_frame = tk.Frame(pdf_win, bg=BG_MAIN)
        pdf_frame.pack(fill='both', expand=True, padx=14, pady=(0, 10))
        pdf_style = ttk.Style()
        pdf_style.configure('DownloadedPDF.Treeview', font=('Arial', 14), rowheight=40)
        pdf_style.configure('DownloadedPDF.Treeview.Heading', font=('Arial', 15, 'bold'), padding=(6, 8, 6, 8))
        pdf_tree = ttk.Treeview(pdf_frame, columns=('date', 'location'), show='headings')
        pdf_tree.configure(style='DownloadedPDF.Treeview')
        pdf_tree.heading('date', text='Date Downloaded')
        pdf_tree.heading('location', text='PDF Location')
        pdf_tree.column('date', width=220, anchor='center')
        pdf_tree.column('location', width=620, anchor='w')
        pdf_tree.pack(side='left', fill='both', expand=True)
        pdf_scroll = ttk.Scrollbar(pdf_frame, orient='vertical', command=pdf_tree.yview)
        pdf_scroll.pack(side='right', fill='y')
        pdf_tree.configure(yscrollcommand=pdf_scroll.set)

        def load_pdf_records():
            # Reload downloaded PDF records for the selected filter range.
            for item in pdf_tree.get_children():
                pdf_tree.delete(item)
            start_date, end_date = compute_pdf_range()
            downloaded_pdf_records = fetch_pdf_downloads(cursor, pdf_download_module, start_date, end_date)
            if downloaded_pdf_records:
                for downloaded_at, location in downloaded_pdf_records:
                    pdf_tree.insert('', 'end', values=(downloaded_at, location))
            else:
                pdf_tree.insert('', 'end', values=('', empty_pdf_message()))

        def on_pdf_click(event):
            # Open the clicked PDF location when the location column is selected.
            if pdf_tree.identify_column(event.x) != '#2':
                return
            item_id = pdf_tree.identify_row(event.y)
            if not item_id:
                return
            values = pdf_tree.item(item_id, 'values')
            if values and len(values) > 1:
                open_pdf_location(values[1])

        pdf_tree.bind('<ButtonRelease-1>', on_pdf_click)
        load_pdf_records()

    # Show summary totals below the table.
    totals_var = tk.StringVar(value='')
    totals_lbl = tk.Label(summary_win, textvariable=totals_var, bg=BG_MAIN, font=('Arial', 17, 'bold'), fg='#1e40af')
    totals_lbl.pack(fill='x', padx=12, pady=(0, 12))

    # Load the initial summary data when the window opens.
    load_summary()
