import calendar
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer

from .chb_database import fetch_production_summary, fetch_latest_production_date


def parse_currency(value):
    cleaned = re.sub(r"[^0-9.\-]", "", str(value))
    return float(cleaned or 0)


def open_date_calendar(parent, date_var, on_select=None):
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
        days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
        for col, day_name in enumerate(days):
            tk.Label(
                grid_frame,
                text=day_name,
                bg="#ffffff",
                fg="#1e293b",
                font=("Arial", 9, "bold"),
                width=5
            ).grid(row=0, column=col, padx=1, pady=2)

        today = datetime.now()
        for row_index, week in enumerate(calendar.monthcalendar(year_var.get(), month_var.get()), start=1):
            for col_index, day in enumerate(week):
                if day == 0:
                    tk.Label(grid_frame, text="", bg="#ffffff", width=5).grid(row=row_index, column=col_index, padx=1, pady=1)
                    continue

                is_today = (
                    day == today.day and
                    month_var.get() == today.month and
                    year_var.get() == today.year
                )
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


def open_period_summary(win, cursor, BG_MAIN, TEXT):
    latest_date = fetch_latest_production_date(cursor)
    try:
        default_date = datetime.strptime(latest_date[:10], "%Y-%m-%d") if latest_date else datetime.now()
    except Exception:
        default_date = datetime.now()

    def compute_range():
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
        for r in summary_tree.get_children():
            summary_tree.delete(r)

        start, end = compute_range()
        rows = fetch_production_summary(cursor, start, end)
        total_blocks = 0
        total_pay = 0
        for i, row in enumerate(rows):
            date, worker, blocks, pay = row
            total_blocks += blocks
            total_pay += pay
            tag = 'evenrow' if i % 2 == 0 else 'oddrow'
            summary_tree.insert('', 'end', values=(date, worker, f"{blocks:,}", f"₱{pay:,.2f}"), tags=(tag,))
        totals_var.set(f"TOTAL: {total_blocks:,} blocks | ₱{total_pay:,.2f}")

    def get_summary_title():
        p = period_var.get()
        start, end = compute_range()

        if p == 'day':
            title_text = f"Daily Production Summary - {start.strftime('%B %d, %Y')}"
        elif p == 'week':
            title_text = f"Weekly Production Summary - {start.strftime('%B %d')} to {end.strftime('%B %d, %Y')}"
        else:
            title_text = f"Monthly Production Summary - {start.strftime('%B %Y')}"
        return title_text

    def get_summary_table_data():
        tree_data = []
        for item in summary_tree.get_children():
            values = summary_tree.item(item, 'values')
            tree_data.append(values)

        table_data = [['Production Date', 'Worker Name', 'Total Blocks', 'Total Pay']]
        total_blocks = 0
        total_pay = 0

        for row in tree_data:
            date, worker, blocks, pay = row
            blocks_int = int(str(blocks).replace(',', ''))
            pay_float = parse_currency(pay)

            total_blocks += blocks_int
            total_pay += pay_float
            table_data.append([date, worker, blocks, pay])

        table_data.append(['', 'TOTAL', f"{total_blocks:,}", f"₱{total_pay:,.2f}"])
        return table_data, total_blocks, total_pay

    def save_summary_pdf(file_path, title_text, table_data):
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

        table = Table(table_data, colWidths=[1.8*inch, 2.2*inch, 1.8*inch, 2*inch])
        table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#2563eb')),
            ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
            ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
            ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
            ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, 0), 12),
            ('FONTSIZE', (0, 1), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
            ('TOPPADDING', (0, 0), (-1, 0), 12),
            ('BACKGROUND', (0, -1), (-1, -1), colors.HexColor('#93c5fd')),
            ('FONTNAME', (0, -1), (-1, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, -1), (-1, -1), 11),
            ('GRID', (0, 0), (-1, -1), 1, colors.black),
            ('ROWBACKGROUNDS', (0, 1), (-1, -2), [colors.white, colors.HexColor('#e0f2fe')]),
        ]))

        elements.append(table)
        elements.append(Spacer(1, 0.3*inch))

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
        """Show summary preview before saving to PDF."""
        try:
            load_summary()
            title_text = get_summary_title()
            table_data, total_blocks, total_pay = get_summary_table_data()

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

            cols = ('date', 'worker', 'blocks', 'pay')
            preview_tree = ttk.Treeview(preview_win, columns=cols, show='headings', style='Summary.Treeview')
            preview_tree.heading('date', text='Production Date')
            preview_tree.heading('worker', text='Worker Name')
            preview_tree.heading('blocks', text='Total Blocks')
            preview_tree.heading('pay', text='Total Pay')
            preview_tree.column('date', width=150, anchor='center')
            preview_tree.column('worker', width=310, anchor='w')
            preview_tree.column('blocks', width=170, anchor='center')
            preview_tree.column('pay', width=170, anchor='center')
            preview_tree.pack(fill='both', expand=True, padx=16, pady=8)
            preview_tree.tag_configure('oddrow', background='#ffffff', font=('Arial', 15))
            preview_tree.tag_configure('evenrow', background='#93c5fd', font=('Arial', 15))

            for index, row in enumerate(table_data[1:-1]):
                tag = 'evenrow' if index % 2 == 0 else 'oddrow'
                preview_tree.insert('', 'end', values=row, tags=(tag,))

            tk.Label(
                preview_win,
                text=f"TOTAL: {total_blocks:,} blocks | ₱{total_pay:,.2f}",
                bg=BG_MAIN,
                fg='#1e40af',
                font=('Arial', 17, 'bold')
            ).pack(fill='x', padx=16, pady=(0, 10))

            action_frame = tk.Frame(preview_win, bg=BG_MAIN)
            action_frame.pack(fill='x', padx=16, pady=(0, 14))

            def choose_file_and_save():
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
                    messagebox.showinfo('Success', f"PDF exported successfully!\n{file_path}", parent=preview_win)
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
                relief='flat'
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
                relief='flat'
            ).pack(side='right', padx=6)

        except Exception as e:
            messagebox.showerror('Error', f"Failed to preview summary:\n{str(e)}", parent=summary_win)

    summary_win = tk.Toplevel(win)
    summary_win.title('Production Summary')
    summary_win.geometry('1100x650')
    summary_win.configure(bg=BG_MAIN)

    summary_win.update_idletasks()
    x = (summary_win.winfo_screenwidth() // 2) - (1100 // 2)
    y = (summary_win.winfo_screenheight() // 2) - (650 // 2)
    summary_win.geometry(f'1100x650+{x}+{y}')

    top_frame = tk.Frame(summary_win, bg=BG_MAIN)
    top_frame.pack(fill='x', pady=12, padx=10)

    period_var = tk.StringVar(value='day')

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
    tk.Button(date_frame, text='Calendar', command=lambda: open_date_calendar(summary_win, date_sel, load_summary), bg='#3b82f6', fg='white', font=('Arial', 13, 'bold'), relief='flat', padx=10, pady=5).pack(side='left', padx=4)
    tk.Button(date_frame, text='Apply', command=load_summary, bg='#2563eb', fg='white', font=('Arial', 13, 'bold'), relief='flat', padx=12, pady=5).pack(side='left', padx=4)

    btn_frame = tk.Frame(summary_win, bg=BG_MAIN)
    btn_frame.pack(fill='x', padx=12, pady=(0, 8))

    tk.Button(btn_frame, text='Preview / Convert PDF', command=open_pdf_preview, bg='#059669', fg='white', font=('Arial', 13, 'bold'), width=22, padx=14, pady=8, relief='flat').pack(side='left', padx=4)

    cols = ('date', 'worker', 'blocks', 'pay')

    style = ttk.Style()
    style.configure('Summary.Treeview', font=('Arial', 15), rowheight=40)
    style.configure('Summary.Treeview.Heading', font=('Arial', 16, 'bold'))

    summary_tree = ttk.Treeview(summary_win, columns=cols, show='headings', style='Summary.Treeview')
    summary_tree.heading('date', text='Production Date')
    summary_tree.heading('worker', text='Worker Name')
    summary_tree.heading('blocks', text='Total Blocks')
    summary_tree.heading('pay', text='Total Pay')
    summary_tree.column('date', width=140, anchor='center')
    summary_tree.column('worker', width=280, anchor='w')
    summary_tree.column('blocks', width=180, anchor='center')
    summary_tree.column('pay', width=180, anchor='center')
    summary_tree.pack(fill='both', expand=True, padx=12, pady=12)
    summary_tree.tag_configure('oddrow', background='#ffffff', font=('Arial', 15))
    summary_tree.tag_configure('evenrow', background='#93c5fd', font=('Arial', 15))

    totals_var = tk.StringVar(value='')
    totals_lbl = tk.Label(summary_win, textvariable=totals_var, bg=BG_MAIN, font=('Arial', 17, 'bold'), fg='#1e40af')
    totals_lbl.pack(fill='x', padx=12, pady=(0, 12))

    load_summary()
