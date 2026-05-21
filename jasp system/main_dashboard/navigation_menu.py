import tkinter as tk

from jasp_theme import DASHBOARD_CONTENT_BG, DASHBOARD_HEADER_BG


MENU_BG = "#ffffff"
MENU_BORDER = "#0f172a"
MENU_TITLE_BG = "#072a4e"
MENU_ITEM_BG = "#eff6ff"
MENU_ITEM_HOVER = "#bfdbfe"
MENU_TEXT = "#0f172a"


def create_hamburger_menu(header_parent, current_window, parent_window=None, close_callback=None, pack_side=tk.RIGHT, pack_padx=6, dashboard_callback=None):
    # Add a reusable hamburger navigation dropdown to module headers.
    dropdown = {"window": None}

    def close_dropdown():
        # Close the active dropdown if it is open.
        menu_win = dropdown.get("window")
        if menu_win and menu_win.winfo_exists():
            menu_win.destroy()
        dropdown["window"] = None

    def close_current_window():
        # Release focus locks and close the current module before navigation.
        try:
            current_window.grab_release()
        except tk.TclError:
            pass
        if callable(close_callback):
            close_callback()
            return
        try:
            current_window.destroy()
        except tk.TclError:
            pass

    def open_after_close(callback):
        # Close this module, then open the selected destination from the dashboard.
        close_dropdown()
        target_parent = parent_window if parent_window and parent_window.winfo_exists() else None
        if callable(dashboard_callback) and target_parent is current_window:
            dashboard_callback()
        else:
            close_current_window()
        if target_parent and target_parent.winfo_exists():
            target_parent.after(80, lambda: callback(target_parent))

    def open_pos(parent):
        # Open Point of Sale.
        from pos_module import open_pos
        open_pos(parent)

    def open_inventory(parent):
        # Open Inventory Management.
        from inventory_module import open_inventory
        open_inventory(parent)

    def open_chb(parent):
        # Open CHB Production Management.
        from chb_module import open_chb_dashboard
        open_chb_dashboard(parent)

    def open_delivery(parent):
        # Open Delivery Management directly.
        from delivery_section import open_delivery_window
        open_delivery_window(parent, DASHBOARD_CONTENT_BG, "#ffffff", "#2563eb")

    def open_reports(parent):
        # Open Reports and Analytics.
        from reports_module import open_reports
        open_reports(parent)

    def open_users(parent):
        # Open User Management.
        from user_management.user_gui import open_user_management
        open_user_management(parent)

    def menu_item(parent, text, command, bg=MENU_ITEM_BG):
        # Create one polished item in the navigation popup.
        button = tk.Button(
            parent,
            text=text,
            command=command,
            bg=bg,
            fg=MENU_TEXT,
            activebackground=MENU_ITEM_HOVER,
            activeforeground=MENU_TEXT,
            font=("Arial", 12, "bold"),
            anchor="w",
            bd=0,
            relief="flat",
            padx=14,
            pady=10,
            cursor="hand2",
        )
        button.pack(fill="x", padx=8, pady=3)
        button.bind("<Enter>", lambda _event: button.config(bg=MENU_ITEM_HOVER))
        button.bind("<Leave>", lambda _event: button.config(bg=bg))
        return button

    def show_dropdown():
        # Show or hide the hamburger dropdown below its header button.
        if dropdown.get("window") and dropdown["window"].winfo_exists():
            close_dropdown()
            return

        menu_win = tk.Toplevel(current_window)
        dropdown["window"] = menu_win
        # Prevent the shared centered-Toplevel hook from moving this dropdown.
        if hasattr(menu_win, "_centered_once"):
            menu_win._centered_once = True
        menu_win.overrideredirect(True)
        menu_win.configure(bg=MENU_BORDER)
        menu_win.transient(current_window)

        outer = tk.Frame(menu_win, bg=MENU_BORDER, padx=2, pady=2)
        outer.pack(fill="both", expand=True)
        body = tk.Frame(outer, bg=MENU_BG)
        body.pack(fill="both", expand=True)

        tk.Label(
            body,
            text="Navigate",
            bg=MENU_TITLE_BG,
            fg="white",
            font=("Arial", 13, "bold"),
            anchor="w",
            padx=14,
            pady=9,
        ).pack(fill="x")

        menu_item(body, "Point of Sale (POS)", lambda: open_after_close(open_pos))
        menu_item(body, "Inventory Management", lambda: open_after_close(open_inventory))
        menu_item(body, "CHB Management", lambda: open_after_close(open_chb))
        menu_item(body, "Delivery Section", lambda: open_after_close(open_delivery))
        menu_item(body, "Reports", lambda: open_after_close(open_reports))
        menu_item(body, "User Management", lambda: open_after_close(open_users))
        menu_win.update_idletasks()
        menu_width = 300
        menu_height = body.winfo_reqheight() + 4

        def position_dropdown():
            # Pin the dropdown directly below the hamburger button.
            current_window.update_idletasks()
            header_parent.update_idletasks()
            menu_button.update_idletasks()
            x_pos = menu_button.winfo_rootx()
            y_pos = menu_button.winfo_rooty() + menu_button.winfo_height() + 2
            menu_win.geometry(f"{menu_width}x{menu_height}+{x_pos}+{y_pos}")

        position_dropdown()
        menu_win.after_idle(position_dropdown)
        menu_win.lift()
        menu_win.bind("<FocusOut>", lambda _event: close_dropdown())
        menu_win.focus_force()

    menu_button = tk.Button(
        header_parent,
        text="\u2630 Menu",
        command=show_dropdown,
        bg="#f59e0b",
        fg="#111827",
        activebackground="#fbbf24",
        activeforeground="#111827",
        font=("Arial", 13, "bold"),
        relief="solid",
        bd=2,
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black",
        padx=12,
        pady=8,
        cursor="hand2",
    )
    menu_button.pack(side=pack_side, padx=pack_padx)
    current_window.bind("<Escape>", lambda _event: close_dropdown(), add="+")
    return menu_button
