from .main_functions import ACCENT, LINE, PRIMARY, TEXT_MUTED, TEXT_PRIMARY, money


AMOUNT_TEXT = "#020617"


def format_hour_label(hour):
    try:
        hour_num = int(str(hour)[:2])
    except (TypeError, ValueError):
        return str(hour or "")
    suffix = "AM" if hour_num < 12 else "PM"
    display_hour = hour_num % 12 or 12
    return f"{display_hour} {suffix}"


def draw_empty_chart(canvas, text="No data available"):
    canvas.delete("all")
    canvas.update_idletasks()
    width = max(canvas.winfo_width(), 180)
    height = max(canvas.winfo_height(), 120)
    canvas.create_text(width / 2, height / 2, text=text, fill=TEXT_MUTED, font=("Arial", 12, "italic"))


def bind_chart(canvas, draw_callback):
    canvas.bind("<Configure>", lambda _event: draw_callback())
    draw_callback()


def draw_revenue_by_hour(canvas, rows):
    def draw():
        canvas.delete("all")
        if not rows:
            draw_empty_chart(canvas)
            return
        width = max(canvas.winfo_width(), 220)
        height = max(canvas.winfo_height(), 70)
        left, right, top, bottom = 34, 12, 24, 12
        chart_w = width - left - right
        chart_h = height - top - bottom
        max_val = max(float(total or 0) for _hour, total in rows)
        if max_val <= 0:
            draw_empty_chart(canvas)
            return
        canvas.create_line(left, top, left, top + chart_h, fill=LINE)
        canvas.create_line(left, top + chart_h, left + chart_w, top + chart_h, fill=LINE)
        bar_gap = 5
        bar_w = max(10, (chart_w - (len(rows) - 1) * bar_gap) / max(len(rows), 1))
        for index, (hour, total) in enumerate(rows):
            value = float(total or 0)
            x1 = left + index * (bar_w + bar_gap)
            x2 = x1 + bar_w
            y1 = top + chart_h - (value / max_val * chart_h)
            canvas.create_rectangle(x1, y1, x2, top + chart_h, fill=ACCENT, outline=PRIMARY)
            label_x = (x1 + x2) / 2
            amount_y = y1 - 10 if y1 > top + 18 else y1 + 10
            canvas.create_text(label_x, amount_y, text=money(value), fill=AMOUNT_TEXT, font=("Arial", 9, "bold"))
            canvas.create_text(label_x, height - 5, text=format_hour_label(hour), fill=TEXT_PRIMARY, font=("Arial", 9, "bold"))
    bind_chart(canvas, draw)


def draw_profit_breakdown(canvas, breakdown):
    def draw():
        canvas.delete("all")
        values = [
            ("Revenue", float(breakdown.get("revenue") or 0), PRIMARY),
            ("Cost", float(breakdown.get("cost") or 0), "#f59e0b"),
            ("Profit", float(breakdown.get("profit") or 0), "#16a34a"),
        ]
        if not any(value != 0 for _label, value, _color in values):
            draw_empty_chart(canvas)
            return
        width = max(canvas.winfo_width(), 220)
        height = max(canvas.winfo_height(), 70)
        left, right, top, bottom = 20, 16, 22, 12
        chart_w = width - left - right
        chart_h = height - top - bottom
        min_val = min(0, min(value for _label, value, _color in values))
        max_val = max(0, max(value for _label, value, _color in values))
        span = max(max_val - min_val, 1)
        baseline = top + chart_h - ((0 - min_val) / span * chart_h)
        canvas.create_line(left, baseline, left + chart_w, baseline, fill=LINE)
        bar_w = chart_w / 5
        for index, (label, value, color) in enumerate(values):
            bar_color = "#dc2626" if value < 0 else color
            x1 = left + (index * 1.65 + 0.35) * bar_w
            x2 = x1 + bar_w
            y_value = top + chart_h - ((value - min_val) / span * chart_h)
            y1, y2 = sorted((baseline, y_value))
            canvas.create_rectangle(x1, y1, x2, y2, fill=bar_color, outline=bar_color)
            canvas.create_text(
                (x1 + x2) / 2,
                height - 5,
                text=label,
                fill=TEXT_PRIMARY,
                font=("Arial", 10, "bold"),
            )
            label_y = max(top + 8, y1 - 8) if value >= 0 else min(height - 18, y2 + 8)
            canvas.create_text((x1 + x2) / 2, label_y, text=money(value), fill=AMOUNT_TEXT, font=("Arial", 10, "bold"))
    bind_chart(canvas, draw)


def draw_chb_stock(canvas, chb_state):
    def draw():
        canvas.delete("all")
        produced = int(chb_state.get("total_produced") or 0)
        sold = int(chb_state.get("total_sold") or 0)
        available = int(chb_state.get("available") or 0)
        total = max(produced, sold + available)
        if total <= 0:
            draw_empty_chart(canvas)
            return
        width = max(canvas.winfo_width(), 220)
        labels = [("Produced", produced, PRIMARY), ("Sold", sold, "#f59e0b"), ("Available", available, "#16a34a")]
        y = 8
        label_x = 8
        bar_x = 82
        value_x = width - 8
        max_bar_w = max(70, width - 132)
        for label, value, color in labels:
            canvas.create_text(label_x, y + 7, text=label, fill=TEXT_PRIMARY, anchor="w", font=("Arial", 9, "bold"))
            canvas.create_rectangle(bar_x, y, bar_x + max_bar_w, y + 14, fill="#e5e7eb", outline=LINE)
            fill_w = max_bar_w * (value / total)
            canvas.create_rectangle(bar_x, y, bar_x + fill_w, y + 14, fill=color, outline=color)
            canvas.create_text(value_x, y + 7, text=f"{value:,} pcs", fill=AMOUNT_TEXT, anchor="e", font=("Arial", 10, "bold"))
            y += 21
    bind_chart(canvas, draw)


def draw_top_items(canvas, rows, empty_text="No items sold yet"):
    def draw():
        canvas.delete("all")
        if not rows:
            canvas.configure(scrollregion=(0, 0, canvas.winfo_width(), canvas.winfo_height()))
            draw_empty_chart(canvas, empty_text)
            return
        width = max(canvas.winfo_width(), 220)
        height = max(canvas.winfo_height(), (len(rows) * 30) + 18)
        canvas.configure(scrollregion=(0, 0, width, height))
        max_qty = max(float(qty or 0) for _name, qty in rows)
        if max_qty <= 0:
            canvas.configure(scrollregion=(0, 0, width, height))
            draw_empty_chart(canvas, empty_text)
            return
        y = 12
        label_w = 140
        bar_w = width - label_w - 52
        for name, qty in rows:
            short_name = str(name)[:16]
            value = float(qty or 0)
            canvas.create_text(8, y + 8, text=short_name, fill=AMOUNT_TEXT, anchor="w", font=("Arial", 12, "bold"))
            canvas.create_rectangle(label_w, y, label_w + bar_w, y + 16, fill="#e5e7eb", outline=LINE)
            fill_w = bar_w * (value / max_qty)
            canvas.create_rectangle(label_w, y, label_w + fill_w, y + 16, fill=ACCENT, outline=PRIMARY)
            canvas.create_text(label_w + bar_w + 40, y + 8, text=f"{int(value):,}", fill=AMOUNT_TEXT, anchor="e", font=("Arial", 12, "bold"))
            y += 30
    bind_chart(canvas, draw)
