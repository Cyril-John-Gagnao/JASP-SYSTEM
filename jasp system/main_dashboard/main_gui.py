import os
import tkinter as tk
from datetime import datetime
from tkinter import messagebox

from user_management.user_gui import open_user_management
from chb_module import open_chb_dashboard
from help_module import render_help_dashboard
from inventory_module import open_inventory
from pos_module import open_pos
from reports_module import open_reports
from window_utils import enable_centered_toplevels

from .main_database import fetch_dashboard_data
from .graphs import (
    draw_chb_stock,
    draw_profit_breakdown,
    draw_revenue_by_hour,
    draw_top_items,
)
from .main_functions import (
    ACCENT,
    BG_CARD,
    BG_PAGE,
    BG_SIDEBAR,
    LINE,
    PRIMARY,
    TEXT_MUTED,
    TEXT_PRIMARY,
    money,
    render_recent_transactions,
    spacer,
    stat_card,
)
from .summary import open_most_items_summary, open_recent_transactions_summary

enable_centered_toplevels()

# Store a callback that other modules can use to refresh the dashboard.
dashboard_refresh_callback = None


def logout_to_login(root, logout_callback=None):
    # Clear the dashboard session and return to the login screen.
    global dashboard_refresh_callback
    dashboard_refresh_callback = None
    try:
        from main_dashboard import session
        session.clear_current_user()
    except Exception:
        pass
    if callable(logout_callback):
        logout_callback()
    else:
        try:
            from login.log_gui import show_login_screen
            show_login_screen()
        except Exception:
            root.destroy()


def open_main(root, logout_callback=None, view="dashboard"):
    # Render the main dashboard or help view inside the root window.
    global dashboard_refresh_callback
    # Fetch dashboard data only when showing the dashboard view.
    data = fetch_dashboard_data() if view == "dashboard" else None
    dashboard_refresh_callback = lambda: root.after(0, lambda: open_main(root, logout_callback, view)) if root.winfo_exists() else None

    # Prepare the root window for the selected dashboard view.
    root.title("JASP Dashboard" if view == "dashboard" else "JASP Help")
    try:
        root.state("zoomed")
    except Exception:
        pass
    root.configure(bg=BG_PAGE)

    # Clear any previous screen before drawing dashboard chrome.
    for child in list(root.winfo_children()):
        try:
            if child.winfo_exists():
                child.destroy()
        except tk.TclError:
            pass

    # Define local dashboard colors for cards, headers, and navigation.
    dashboard_chrome_bg = "#072a4e"
    dashboard_chrome_border = "#041d36"
    nav_button_bg = "#dbeafe"
    nav_button_active_bg = "#bfdbfe"
    section_border = "black"
    today_label = datetime.now().strftime("%B %d, %Y")
    revenue_bg = "#dbeafe"
    profit_bg = "#dcfce7"
    chb_bg = "#fef3c7"
    recent_bg = "#e2e8f0"
    low_stock_bg = "#fee2e2"
    low_stock_header_bg = "#991b1b"
    low_stock_row_bg = "#fff1f2"
    top_items_bg = "#ddd6fe"
    revenue_header_bg = "#1d4ed8"
    profit_header_bg = "#15803d"
    chb_header_bg = "#b45309"
    recent_header_bg = "#334155"
    top_items_header_bg = "#6d28d9"
    sidebar_bg = dashboard_chrome_bg

    # Build the left sidebar navigation shell.
    sidebar = tk.Frame(root, bg=sidebar_bg, width=270, highlightthickness=1, highlightbackground=dashboard_chrome_border)
    sidebar.pack(side="left", fill="y")
    sidebar.pack_propagate(False)

    # Load the sidebar logo with Pillow when available and Tk fallback otherwise.
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "images", "logo1.png"))
    try:
        from PIL import Image, ImageDraw, ImageTk

        logo_size = 140
        logo_source = Image.open(logo_path).convert("RGBA")
        logo_source.thumbnail((logo_size, logo_size), Image.LANCZOS)
        rounded_logo = Image.new("RGBA", (logo_size, logo_size), (0, 0, 0, 0))
        x_pos = (logo_size - logo_source.width) // 2
        y_pos = (logo_size - logo_source.height) // 2
        rounded_logo.paste(logo_source, (x_pos, y_pos), logo_source)
        mask = Image.new("L", (logo_size, logo_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, logo_size - 1, logo_size - 1), fill=255)
        rounded_logo.putalpha(mask)
        logo_image = ImageTk.PhotoImage(rounded_logo)
    except (ImportError, tk.TclError, OSError, AttributeError):
        try:
            logo_image = tk.PhotoImage(file=logo_path)
            logo_image = logo_image.subsample(max(1, logo_image.width() // 140), max(1, logo_image.height() // 140))
        except tk.TclError:
            logo_image = None
    if logo_image:
        # Show the loaded logo image in the sidebar.
        sidebar.logo_image = logo_image
        tk.Label(sidebar, image=logo_image, bg=sidebar_bg).pack(pady=(18, 8))
    else:
        # Fall back to a text logo when the image cannot be loaded.
        tk.Label(sidebar, text="JASP", bg=sidebar_bg, fg="white",
                 font=("Arial", 18, "bold")).pack(pady=(20, 8))

    nav_frame = tk.Frame(sidebar, bg=sidebar_bg)
    nav_frame.pack(fill="x", padx=14, pady=(18, 0))

    def sidebar_btn(text, command=None):
        # Create a consistent sidebar navigation button.
        return tk.Button(
            nav_frame,
            text=text,
            command=command,
            font=("Arial", 12, "bold"),
            bg=nav_button_bg,
            fg=TEXT_PRIMARY,
            activebackground=nav_button_active_bg,
            activeforeground=TEXT_PRIMARY,
            bd=2,
            relief="solid",
            highlightthickness=1,
            highlightbackground="black",
            highlightcolor="black",
            anchor="center",
            justify="center",
            wraplength=205,
            padx=12,
            pady=12,
        )

    def launch_user_management():
        # Open User Management and restore the dashboard if the page fails to draw.
        try:
            open_user_management(root)
        except Exception as exc:
            messagebox.showerror("User Management Error", f"Unable to open User Management:\n\n{exc}")
            open_main(root, logout_callback, "dashboard")

    # Add navigation buttons for each major system module.
    sidebar_btn("Point of Sale (POS)", lambda: open_pos(root)).pack(fill="x", pady=4)
    sidebar_btn("Inventory Management", lambda: open_inventory(root)).pack(fill="x", pady=4)
    sidebar_btn("CHB and Delivery Production", lambda: open_chb_dashboard(root)).pack(fill="x", pady=4)
    sidebar_btn("User Management", launch_user_management).pack(fill="x", pady=4)
    sidebar_btn("Reports & Analytics", lambda: open_reports(root)).pack(fill="x", pady=4)
    sidebar_btn("Help?", lambda: open_main(root, logout_callback, "help")).pack(fill="x", pady=4)

    tk.Label(sidebar, bg=sidebar_bg).pack(expand=True, fill="both")

    # Add the logout button at the bottom of the sidebar.
    tk.Button(sidebar, text="Logout", bg="#dc2626", fg="white",
              font=("Arial", 13, "bold"), relief="solid", bd=2,
              highlightthickness=1, highlightbackground="black", highlightcolor="black",
              command=lambda: logout_to_login(root, logout_callback), padx=16, pady=10,
              activebackground="#b91c1c").pack(fill="x", padx=18, pady=(16, 52))

    # Build the main content shell to the right of the sidebar.
    main_area = tk.Frame(root, bg=BG_PAGE)
    main_area.pack(side="right", fill="both", expand=True)

    # Build the top dashboard header with title and refresh/back action.
    header_bg = dashboard_chrome_bg
    header = tk.Frame(main_area, bg=header_bg, height=78, highlightthickness=1,
                      highlightbackground=dashboard_chrome_border)
    header.pack(fill="x")
    header.pack_propagate(False)

    title_block = tk.Frame(header, bg=header_bg)
    title_block.pack(side="left", padx=22, pady=10)
    tk.Label(title_block, text="JASP Hardware Management System", bg=header_bg, fg="white",
             font=("Arial", 20, "bold")).pack(anchor="w")
    tk.Label(title_block, text="Dashboard Overview" if view == "dashboard" else "Help Guide", bg=header_bg,
             fg="#eff6ff", font=("Arial", 11, "bold")).pack(anchor="w", pady=(2, 0))

    tk.Button(
        header,
        text="Refresh Data" if view == "dashboard" else "Back to Dashboard",
        bg="#16a34a" if view == "dashboard" else "#2563eb",
        fg="white",
        activebackground="#15803d" if view == "dashboard" else "#1d4ed8",
        activeforeground="white",
        font=("Arial", 11, "bold"),
        relief="solid",
        bd=2,
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black",
        padx=14,
        pady=8,
        command=lambda: open_main(root, logout_callback, "dashboard"),
    ).pack(side="right", padx=18, pady=14)

    # Create the main content frame below the header.
    content_bg = "#fff3e6"
    main_area.configure(bg=content_bg)
    content = tk.Frame(main_area, bg=content_bg)
    content.pack(fill="both", expand=True, padx=18, pady=18)

    if view == "help":
        # Render the help guide instead of dashboard analytics.
        render_help_dashboard(content)
        return

    # Build the top stat cards for revenue, profit, and CHB stock.
    stats_row = tk.Frame(content, bg=content_bg)
    stats_row.pack(fill="x")
    revenue_card = stat_card(stats_row, f"Today's Revenue - {today_label}", money(data["revenue"]), "", bg=revenue_bg, header_bg=revenue_header_bg)
    profit_card = stat_card(stats_row, f"Today's Profit - {today_label}", money(data["profit"]), "", bg=profit_bg, header_bg=profit_header_bg)
    chb_card = stat_card(stats_row, "CHB Stock Available", f"{data['chb_stock']:,}", "pcs", bg=chb_bg, header_bg=chb_header_bg)

    analytics = data.get("analytics", {})
    # Attach mini analytics charts to the top stat cards.
    revenue_canvas = tk.Canvas(revenue_card, bg=revenue_bg, highlightthickness=0, height=70)
    revenue_canvas.pack(fill="x", padx=14, pady=(2, 10))
    draw_revenue_by_hour(revenue_canvas, analytics.get("revenue_by_hour", []))

    profit_canvas = tk.Canvas(profit_card, bg=profit_bg, highlightthickness=0, height=70)
    profit_canvas.pack(fill="x", padx=14, pady=(2, 10))
    draw_profit_breakdown(profit_canvas, analytics.get("profit_breakdown", {}))

    chb_canvas = tk.Canvas(chb_card, bg=chb_bg, highlightthickness=0, height=70)
    chb_canvas.pack(fill="x", padx=14, pady=(2, 10))
    draw_chb_stock(chb_canvas, analytics.get("chb_state", {}))

    # Build the middle row containing recent transactions and low-stock alerts.
    spacer(content, 14)

    mid_row = tk.Frame(content, bg=content_bg)
    mid_row.pack(fill="both", expand=True)

    # Build the recent transactions card and summary button.
    recent_card = tk.Frame(mid_row, bg=recent_bg, highlightthickness=1,
                           highlightbackground=section_border, height=260)
    recent_card.pack(side="left", fill="both", expand=True, padx=(0, 12))
    recent_card.pack_propagate(False)
    recent_header = tk.Frame(recent_card, bg=recent_header_bg)
    recent_header.pack(fill="x")
    tk.Label(recent_header, text="Recent Transactions", bg=recent_header_bg, fg="white",
             font=("Arial", 14, "bold")).pack(side="left", padx=16, pady=12)
    tk.Button(
        recent_header,
        text="Summary",
        command=lambda: open_recent_transactions_summary(root),
        bg="#8b5cf6",
        fg="white",
        activebackground="#7c3aed",
        activeforeground="white",
        font=("Arial", 13, "bold"),
        padx=12,
        pady=6,
        bd=2,
        relief="solid",
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black",
    ).pack(side="right", padx=12, pady=8)
    latest_day_text = data["recent_day_label"] or "No sales yet"
    tk.Label(
        recent_card,
        text=f"Total transactions on latest day ({latest_day_text}): {data['recent_day_count']:,}",
        bg=recent_bg,
        fg=TEXT_MUTED,
        font=("Arial", 13, "bold"),
    ).pack(anchor="w", padx=16, pady=(8, 6))

    # Render the recent transactions preview table.
    table_container = tk.Frame(recent_card, bg=recent_bg, padx=12, pady=6)
    table_container.pack(fill="both", expand=True)
    render_recent_transactions(table_container, data["recent"], "No transactions for today.")

    # Build the low-stock preview card with a scrollable alert list.
    low_card = tk.Frame(mid_row, bg=low_stock_bg, width=260, highlightthickness=1,
                        highlightbackground=section_border, height=260)
    low_card.pack(side="left", fill="y", padx=(12, 0))
    low_card.pack_propagate(False)
    low_header = tk.Frame(low_card, bg=low_stock_header_bg)
    low_header.pack(fill="x")
    tk.Label(low_header, text="Low Stock Alerts (Preview)", bg=low_stock_header_bg, fg="white",
             font=("Arial", 12, "bold")).pack(anchor="w", padx=16, pady=10)

    alert_container = tk.Frame(low_card, bg=low_stock_bg)
    alert_container.pack(fill="both", expand=True, padx=10, pady=(10, 12))
    low_stock_canvas = tk.Canvas(alert_container, bg=low_stock_bg, highlightthickness=0)
    low_stock_scrollbar = tk.Scrollbar(
        alert_container,
        orient="vertical",
        command=low_stock_canvas.yview,
        width=16,
        bg=low_stock_header_bg,
        troughcolor="#e7d2bd",
        activebackground="#6f451f",
    )
    low_stock_canvas.configure(yscrollcommand=low_stock_scrollbar.set)
    low_stock_canvas.grid(row=0, column=0, sticky="nsew")
    low_stock_scrollbar.grid(row=0, column=1, sticky="ns")
    alert_container.grid_rowconfigure(0, weight=1)
    alert_container.grid_columnconfigure(0, weight=1)

    low_stock_list = tk.Frame(low_stock_canvas, bg=low_stock_bg)
    low_stock_window = low_stock_canvas.create_window((0, 0), window=low_stock_list, anchor="nw")
    low_stock_list.bind(
        "<Configure>",
        lambda _event: low_stock_canvas.configure(scrollregion=low_stock_canvas.bbox("all")),
    )
    low_stock_canvas.bind(
        "<Configure>",
        lambda event: low_stock_canvas.itemconfigure(low_stock_window, width=event.width),
    )
    if data["low_stock"]:
        # Render one low-stock alert row per item below threshold.
        for item, qty in data["low_stock"]:
            row = tk.Frame(low_stock_list, bg=low_stock_row_bg)
            row.pack(fill="x", pady=4)
            tk.Label(row, text=item, bg=low_stock_row_bg, fg=TEXT_PRIMARY, font=("Arial", 10, "bold")).pack(
                side="left", padx=6, pady=4)
            tk.Label(row, text=f"{qty} pcs", bg=low_stock_header_bg, fg="white", font=("Arial", 10, "bold"),
                     padx=10, pady=4).pack(side="right", padx=6)
    else:
        # Show a friendly message when there are no low-stock alerts.
        tk.Label(low_stock_list, text="No items below threshold.", bg=low_stock_bg,
                 fg=TEXT_MUTED, font=("Arial", 11, "italic")).pack(anchor="w", padx=6, pady=12)

    # Build the bottom row for most-sold items.
    spacer(content, 14)

    bottom_row = tk.Frame(content, bg=content_bg)
    bottom_row.pack(fill="both", expand=True)

    # Build the most-sold items card and summary button.
    top_sell_card = tk.Frame(bottom_row, bg=top_items_bg, highlightthickness=1,
                             highlightbackground=section_border, height=235)
    top_sell_card.pack(fill="both", expand=True)
    top_sell_card.pack_propagate(False)
    top_items_header = tk.Frame(top_sell_card, bg=top_items_header_bg)
    top_items_header.pack(fill="x")
    tk.Label(top_items_header, text=f"Most Items Sold Today - {today_label} (Preview)", bg=top_items_header_bg,
             fg="white", font=("Arial", 14, "bold")).pack(side="left", padx=16, pady=10)
    tk.Button(
        top_items_header,
        text="Summary",
        command=lambda: open_most_items_summary(root),
        bg="#f97316",
        fg="white",
        activebackground="#ea580c",
        activeforeground="white",
        font=("Arial", 13, "bold"),
        padx=12,
        pady=6,
        bd=2,
        relief="solid",
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black",
    ).pack(side="right", padx=12, pady=8)

    # Render the top-items chart in a scrollable canvas.
    top_items_scroll_area = tk.Frame(top_sell_card, bg=top_items_bg)
    top_items_scroll_area.pack(fill="both", expand=True, padx=16, pady=(0, 10))
    top_items_canvas = tk.Canvas(top_items_scroll_area, bg=top_items_bg, highlightthickness=0)
    top_items_scrollbar = tk.Scrollbar(top_items_scroll_area, orient="vertical", command=top_items_canvas.yview)
    top_items_canvas.configure(yscrollcommand=top_items_scrollbar.set)
    top_items_canvas.pack(side="left", fill="both", expand=True)
    top_items_scrollbar.pack(side="right", fill="y")
    draw_top_items(top_items_canvas, analytics.get("top_items", []), empty_text="No items sold today.")


if __name__ == "__main__":
    # Allow this module to be run directly for manual dashboard testing.
    root = tk.Tk()
    open_main(root)
    root.mainloop()
