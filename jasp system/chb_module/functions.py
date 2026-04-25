import sys
import calendar
import re
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from datetime import datetime, timedelta
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib import colors

from .chb_dashboard import CHB_STATE_ID, ensure_chb_inventory, adjust_chb_inventory, fetch_production_summary, fetch_latest_production_date


def notify_inventory_views():
    """Refresh open inventory/POS windows if they registered callbacks."""
    for module_name, callback_name in (("inventory", "inventory_refresh_callback"), ("pos", "pos_refresh_callback")):
        module = sys.modules.get(module_name)
        callback = getattr(module, callback_name, None) if module else None
        if callable(callback):
            try:
                callback()
            except Exception:
                pass


def go_back(win):
    win.destroy()
    import main_dashboard
    main_dashboard.open_main()


def refresh_data(load_data, update_total_blocks):
    load_data()
    update_total_blocks()


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
                m = months.index(month_var.get()) + 1
                y = int(year_var.get())
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
        else:  # month
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
            preview_win.geometry('900x560')
            preview_win.configure(bg=BG_MAIN)
            preview_win.transient(summary_win)

            preview_win.update_idletasks()
            x = (preview_win.winfo_screenwidth() // 2) - (900 // 2)
            y = (preview_win.winfo_screenheight() // 2) - (560 // 2)
            preview_win.geometry(f'900x560+{x}+{y}')

            header_frame = tk.Frame(preview_win, bg=BG_MAIN)
            header_frame.pack(fill='x', padx=16, pady=(14, 8))

            tk.Label(
                header_frame,
                text=title_text,
                bg=BG_MAIN,
                fg='#1e40af',
                font=('Arial', 16, 'bold')
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
            preview_tree.tag_configure('oddrow', background='#ffffff', font=('Arial', 12))
            preview_tree.tag_configure('evenrow', background='#93c5fd', font=('Arial', 12))

            for index, row in enumerate(table_data[1:-1]):
                tag = 'evenrow' if index % 2 == 0 else 'oddrow'
                preview_tree.insert('', 'end', values=row, tags=(tag,))

            tk.Label(
                preview_win,
                text=f"TOTAL: {total_blocks:,} blocks | ?{total_pay:,.2f}",
                bg=BG_MAIN,
                fg='#1e40af',
                font=('Arial', 13, 'bold')
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
                font=('Arial', 11, 'bold'),
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
                font=('Arial', 11, 'bold'),
                width=16,
                padx=12,
                pady=8,
                relief='flat'
            ).pack(side='right', padx=6)

        except Exception as e:
            messagebox.showerror('Error', f"Failed to preview summary:\n{str(e)}", parent=summary_win)

    # Create window and center it
    summary_win = tk.Toplevel(win)
    summary_win.title('Production Summary')
    summary_win.geometry('950x550')
    summary_win.configure(bg=BG_MAIN)

    # Center window on screen
    summary_win.update_idletasks()
    x = (summary_win.winfo_screenwidth() // 2) - (950 // 2)
    y = (summary_win.winfo_screenheight() // 2) - (550 // 2)
    summary_win.geometry(f'950x550+{x}+{y}')

    # ============ TOP FRAME WITH LARGER FONT ==============
    top_frame = tk.Frame(summary_win, bg=BG_MAIN)
    top_frame.pack(fill='x', pady=12, padx=10)

    period_var = tk.StringVar(value='day')

    # Period selection with larger font
    tk.Label(top_frame, text='Period:', bg=BG_MAIN, font=('Arial', 11, 'bold'), fg=TEXT).pack(side='left', padx=6)
    tk.Radiobutton(top_frame, text='Day', variable=period_var, value='day', bg=BG_MAIN, font=('Arial', 10), command=load_summary).pack(side='left', padx=8)
    tk.Radiobutton(top_frame, text='Week', variable=period_var, value='week', bg=BG_MAIN, font=('Arial', 10), command=load_summary).pack(side='left', padx=8)
    tk.Radiobutton(top_frame, text='Month', variable=period_var, value='month', bg=BG_MAIN, font=('Arial', 10), command=load_summary).pack(side='left', padx=8)

    # Date selection frame
    date_frame = tk.Frame(top_frame, bg=BG_MAIN)
    date_frame.pack(side='left', padx=(30, 10))

    tk.Label(date_frame, text='Date:', bg=BG_MAIN, font=('Arial', 11, 'bold'), fg=TEXT).pack(side='left', padx=(0, 6))
    date_sel = tk.StringVar(value=default_date.strftime('%Y-%m-%d'))
    date_entry2 = tk.Entry(date_frame, textvariable=date_sel, width=15, font=('Arial', 11), relief='solid', bd=1)
    date_entry2.pack(side='left', padx=4)
    tk.Button(date_frame, text='📅', command=lambda: open_date_calendar(summary_win, date_sel, load_summary), bg='#3b82f6', fg='white', font=('Arial', 10, 'bold'), relief='flat', padx=8, pady=3).pack(side='left', padx=4)

    # Month/Year selection frame
    month_year_frame = tk.Frame(top_frame, bg=BG_MAIN)
    month_year_frame.pack(side='left', padx=10)

    months = ["January", "February", "March", "April", "May", "June",
              "July", "August", "September", "October", "November", "December"]
    month_var = tk.StringVar(value=default_date.strftime('%B'))
    month_cb = ttk.Combobox(month_year_frame, values=months, textvariable=month_var, width=12, state='readonly', font=('Arial', 10))
    month_cb.pack(side='left', padx=4)

    year_var = tk.StringVar(value=str(default_date.year))
    years = [str(y) for y in range(datetime.now().year - 5, datetime.now().year + 1)]
    if str(default_date.year) not in years:
        years.append(str(default_date.year))
        years.sort(key=int)
    year_cb = ttk.Combobox(month_year_frame, values=years, textvariable=year_var, width=8, state='readonly', font=('Arial', 10))
    year_cb.pack(side='left', padx=4)
    tk.Button(month_year_frame, text='Apply', command=load_summary, bg='#3b82f6', fg='white', font=('Arial', 10, 'bold'), width=10, padx=8, pady=5, relief='flat').pack(side='left', padx=4)

    # Buttons frame
    btn_frame = tk.Frame(summary_win, bg=BG_MAIN)
    btn_frame.pack(fill='x', padx=12, pady=(0, 8))

    tk.Button(btn_frame, text='Preview / Convert PDF', command=open_pdf_preview, bg='#059669', fg='white', font=('Arial', 10, 'bold'), width=22, padx=14, pady=6, relief='flat').pack(side='left', padx=4)

    # ============ SUMMARY TREE WITH LARGER FONT ==============
    cols = ('date', 'worker', 'blocks', 'pay')

    style = ttk.Style()
    style.configure('Summary.Treeview', font=('Arial', 12), rowheight=32)
    style.configure('Summary.Treeview.Heading', font=('Arial', 13, 'bold'))

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
    summary_tree.tag_configure('oddrow', background='#ffffff', font=('Arial', 12))
    summary_tree.tag_configure('evenrow', background='#93c5fd', font=('Arial', 12))

    # ============ TOTALS DISPLAY WITH LARGER FONT ==============
    totals_var = tk.StringVar(value='')
    totals_lbl = tk.Label(summary_win, textvariable=totals_var, bg=BG_MAIN, font=('Arial', 13, 'bold'), fg='#1e40af')
    totals_lbl.pack(fill='x', padx=12, pady=(0, 12))

    load_summary()



def update_pay(event, cement_entry, pay_rate_var, result_label):
    try:
        cement = int(cement_entry.get() or 0)
        pay = cement * float(pay_rate_var.get() or 0)
        result_label.config(text=f"| Pay: ₱{pay:,.2f}")
    except:
        result_label.config(text="| Pay: ₱0")


def auto_sand(event, cement_entry, sand_entry, pay_rate_var, blocks_entry, result_label):
    try:
        cement = int(cement_entry.get() or 0)
        sand = cement * 15
        sand_entry.delete(0, tk.END)
        sand_entry.insert(0, str(sand))

        blocks = cement * 75
        blocks_entry.delete(0, tk.END)
        blocks_entry.insert(0, str(blocks))

        update_pay(event, cement_entry, pay_rate_var, result_label)

    except:
        sand_entry.delete(0, tk.END)
        blocks_entry.delete(0, tk.END)
        blocks_entry.insert(0, "0")
        result_label.config(text="| Pay: ₱0")


def clear_form(worker_entry, cement_entry, sand_entry, blocks_entry, result_label, selected_id):
    worker_entry.delete(0, tk.END)
    cement_entry.delete(0, tk.END)
    sand_entry.delete(0, tk.END)
    blocks_entry.delete(0, tk.END)
    blocks_entry.insert(0, "0")
    result_label.config(text="| Pay: ₱0")
    selected_id.set("")


def save(conn, cursor, win, worker_entry, date_var, cement_entry, blocks_entry, pay_rate_var, load_data, update_total_blocks, clear_form):
    try:
        cement = int(cement_entry.get())
        sand = cement * 15
        blocks = int(blocks_entry.get())
        pay_rate = float(pay_rate_var.get())
        pay = cement * pay_rate
    except:
        messagebox.showerror("Error", "Invalid input", parent=win)
        return

    worker = worker_entry.get()
    date = date_var.get()

    if not worker:
        messagebox.showerror("Error", "Fill all fields", parent=win)
        return

    # Confirmation dialog
    if not messagebox.askyesno("Confirm Save", f"Save production record for {worker}?", parent=win):
        return

    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    cursor.execute("""
        INSERT INTO chb_production
        (production_date, worker_name, cement_bags, fine_sand, total_blocks, pay, pay_rate, ts)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """, (date, worker, cement, sand, blocks, pay, pay_rate, ts))

    conn.commit()
    adjust_chb_inventory(conn, cursor, produced_delta=blocks)
    notify_inventory_views()
    load_data()
    update_total_blocks()
    clear_form()
    messagebox.showinfo("Success", "Record saved successfully!", parent=win)


def update(conn, cursor, win, selected_id, worker_entry, date_var, cement_entry, blocks_entry, pay_rate_var, load_data, update_total_blocks, clear_form):
    if not selected_id.get():
        messagebox.showerror("Error", "Select a record", parent=win)
        return

    try:
        cement = int(cement_entry.get())
        sand = cement * 15
        blocks = int(blocks_entry.get())
        pay_rate = float(pay_rate_var.get())
        pay = cement * pay_rate
    except:
        messagebox.showerror("Error", "Invalid input", parent=win)
        return

    # Confirmation dialog
    if not messagebox.askyesno("Confirm Update", f"Update record for {worker_entry.get()}?", parent=win):
        return

    cursor.execute("SELECT COALESCE(total_blocks, 0) FROM chb_production WHERE id=?", (selected_id.get(),))
    old_row = cursor.fetchone()
    old_blocks = old_row[0] if old_row else 0

    cursor.execute("""
        UPDATE chb_production
        SET production_date=?, worker_name=?, cement_bags=?, fine_sand=?, total_blocks=?, pay=?, pay_rate=?
        WHERE id=?
    """, (
        date_var.get(),
        worker_entry.get(),
        cement, sand, blocks, pay, pay_rate,
        selected_id.get()
    ))

    conn.commit()
    adjust_chb_inventory(conn, cursor, produced_delta=(blocks - old_blocks))
    notify_inventory_views()
    load_data()
    update_total_blocks()
    clear_form()
    messagebox.showinfo("Success", "Record updated successfully!", parent=win)


def delete(conn, cursor, win, selected_id, worker_entry, load_data, update_total_blocks, clear_form):
    if not selected_id.get():
        return

    # Confirmation dialog
    if not messagebox.askyesno("Confirm Delete", f"Delete record for {worker_entry.get()}?\n\nThis action cannot be undone.", parent=win):
        return

    cursor.execute("SELECT COALESCE(total_blocks, 0) FROM chb_production WHERE id=?", (selected_id.get(),))
    old_row = cursor.fetchone()
    old_blocks = old_row[0] if old_row else 0

    cursor.execute("DELETE FROM chb_production WHERE id=?", (selected_id.get(),))
    conn.commit()
    adjust_chb_inventory(conn, cursor, produced_delta=-old_blocks)
    notify_inventory_views()
    load_data()
    update_total_blocks()
    clear_form()
    messagebox.showinfo("Success", "Record deleted successfully!", parent=win)


def update_total_blocks(conn, cursor, total_blocks_var):
    ensure_chb_inventory(conn, cursor)
    cursor.execute("""
        SELECT total_produced, total_sold, available
        FROM chb_inventory_state
        WHERE id=?
    """, (CHB_STATE_ID,))
    state = cursor.fetchone()
    if state:
        produced, sold, stock = state
    else:
        produced = sold = stock = 0
    total_blocks_var.set(f"Total Hollow Blocks Available: {stock:,}")


def on_tree_configure(event, tree):
    tree.update_idletasks()


def on_select(event, tree, selected_id, date_var, worker_entry, cement_entry, sand_entry, blocks_entry, cursor, pay_rate_var, update_pay):
    selected = tree.focus()
    values = tree.item(selected, "values")

    if values:
        selected_id.set(values[0])
        date_var.set(values[1])

        worker_entry.delete(0, tk.END)
        worker_entry.insert(0, values[2])

        cement_entry.delete(0, tk.END)
        cement_entry.insert(0, values[3])

        sand_entry.delete(0, tk.END)
        sand_entry.insert(0, values[4])

        blocks_entry.delete(0, tk.END)
        blocks_entry.insert(0, values[5])

        cursor.execute("SELECT pay_rate FROM chb_production WHERE id=?", (values[0],))
        pr = cursor.fetchone()
        pay_rate_var.set(pr[0] if pr and pr[0] is not None else 200)
        update_pay()


def load_data(event, tree, search_var, sort_var, cursor):
    for row in tree.get_children():
        tree.delete(row)

    keyword = search_var.get().lower()
    sort_option = sort_var.get()

    query = """
        SELECT id, production_date, worker_name, cement_bags, fine_sand, total_blocks, pay
        FROM chb_production
    """

    params = []

    if keyword:
        query += " WHERE LOWER(worker_name) LIKE ? OR production_date LIKE ?"
        params.extend([f"%{keyword}%", f"%{keyword}%"])

    if sort_option == "Worker Name":
        query += " ORDER BY worker_name ASC"
    else:
        query += " ORDER BY ts DESC"

    cursor.execute(query, params)

    row_index = 0
    for row in cursor.fetchall():
        tag = 'evenrow' if row_index % 2 == 0 else 'oddrow'
        tree.insert("", "end", values=row, tags=(tag,))
        row_index += 1
