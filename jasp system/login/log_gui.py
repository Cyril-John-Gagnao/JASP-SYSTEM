import tkinter as tk
from tkinter import messagebox

from window_utils import enable_centered_toplevels

from .database import (
    get_authenticated_user,
    get_contact_number,
    reset_user_password_with_contact,
)

enable_centered_toplevels()
from .functions import (
    is_valid_contact_number,
    is_valid_password,
    is_valid_username,
    validate_common_inputs,
)

BG_BLUE = "#1950a3"
CARD_BG = "#ffffff"
TEXT_DARK = "#1f2933"
TEXT_MUTED = "#6b7280"
GREEN = "#28a745"
GREEN_HOVER = "#218838"
RED = "#dc3545"

root = None
main_frame = None
login_frame = None
username_entry = None
password_entry = None
login_btn = None


def open_main_in_place(user_role):
    try:
        if user_role == "Admin":
            import main_dashboard
            main_dashboard.open_main(root, show_login_screen)
        elif user_role == "Cashier":
            open_cashier_dashboard()
        else:
            messagebox.showerror("Error", "Access denied. Unauthorized role.")
    except Exception as e:
        messagebox.showerror(
            "Error Loading Dashboard",
            f"Failed to load dashboard:\n\n{str(e)}\n\nCheck console for details."
        )
        import traceback
        traceback.print_exc()


def open_pos_for_cashier():
    try:
        from pos_module import open_pos
        open_pos()
    except Exception as e:
        messagebox.showerror("Error Loading POS", f"Failed to load POS:\n\n{str(e)}")


def open_cashier_dashboard():
    root.title("JASP Cashier")
    try:
        root.state("zoomed")
    except Exception:
        pass
    root.configure(bg="#f4f6f9")

    for child in root.winfo_children():
        child.destroy()

    header = tk.Frame(root, bg="#273142", height=68)
    header.pack(fill="x")
    header.pack_propagate(False)

    tk.Label(
        header,
        text="JASP Hardware - Cashier",
        bg="#273142",
        fg="white",
        font=("Arial", 18, "bold")
    ).pack(side="left", padx=24)

    tk.Button(
        header,
        text="Logout",
        command=show_login_screen,
        bg=RED,
        fg="white",
        activebackground="#b91c1c",
        font=("Arial", 10, "bold"),
        relief="flat",
        padx=16,
        pady=8
    ).pack(side="right", padx=24)

    content = tk.Frame(root, bg="#f4f6f9")
    content.pack(expand=True)

    tk.Label(
        content,
        text="Point of Sale",
        bg="#f4f6f9",
        fg=TEXT_DARK,
        font=("Arial", 28, "bold")
    ).pack(pady=(0, 8))

    tk.Label(
        content,
        text="Cashier access is limited to POS transactions only.",
        bg="#f4f6f9",
        fg=TEXT_MUTED,
        font=("Arial", 12)
    ).pack(pady=(0, 24))

    tk.Button(
        content,
        text="Open POS",
        command=open_pos_for_cashier,
        bg=GREEN,
        fg="white",
        activebackground=GREEN_HOVER,
        font=("Arial", 14, "bold"),
        relief="flat",
        width=22,
        pady=10
    ).pack()


def show_success_popup(user_role):
    popup = tk.Toplevel(root)
    popup.title("Login Successful")
    popup.configure(bg=CARD_BG)
    popup.resizable(False, False)
    popup.transient(root)
    popup.grab_set()

    width, height = 500, 300
    x = (popup.winfo_screenwidth() // 2) - (width // 2)
    y = (popup.winfo_screenheight() // 2) - (height // 2)
    popup.geometry(f"{width}x{height}+{x}+{y}")

    tk.Frame(popup, bg=GREEN, height=12).pack(fill="x")

    content = tk.Frame(popup, bg=CARD_BG, padx=48, pady=42)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text=f"Welcome {user_role}",
        bg=CARD_BG,
        fg=TEXT_DARK,
        font=("Arial", 32, "bold")
    ).pack(pady=(4, 12))

    tk.Label(
        content,
        text="Login successful. Redirecting to your workspace.",
        bg=CARD_BG,
        fg=TEXT_MUTED,
        font=("Arial", 15),
        wraplength=390,
        justify="center"
    ).pack(pady=(0, 32))

    def close_popup():
        popup.destroy()

    ok_btn = tk.Button(
        content,
        text="Continue",
        command=close_popup,
        bg=GREEN,
        fg="white",
        activebackground=GREEN_HOVER,
        font=("Arial", 15, "bold"),
        relief="flat",
        width=18,
        pady=10
    )
    ok_btn.pack()
    ok_btn.focus_set()

    popup.bind("<Return>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    root.wait_window(popup)


def show_error_popup(title, message):
    popup = tk.Toplevel(root)
    popup.title(title)
    popup.configure(bg=CARD_BG)
    popup.resizable(False, False)
    popup.transient(root)
    popup.grab_set()

    width, height = 500, 260
    x = (popup.winfo_screenwidth() // 2) - (width // 2)
    y = (popup.winfo_screenheight() // 2) - (height // 2)
    popup.geometry(f"{width}x{height}+{x}+{y}")

    tk.Frame(popup, bg=RED, height=12).pack(fill="x")

    content = tk.Frame(popup, bg=CARD_BG, padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text=title,
        bg=CARD_BG,
        fg=RED,
        font=("Arial", 28, "bold")
    ).pack(pady=(0, 14))

    tk.Label(
        content,
        text=message,
        bg=CARD_BG,
        fg=TEXT_DARK,
        font=("Arial", 17),
        wraplength=400,
        justify="center"
    ).pack(pady=(0, 28))

    def close_popup():
        popup.destroy()

    ok_btn = tk.Button(
        content,
        text="OK",
        command=close_popup,
        bg=RED,
        fg="white",
        activebackground="#b91c1c",
        font=("Arial", 15, "bold"),
        relief="flat",
        width=14,
        pady=9
    )
    ok_btn.pack()
    ok_btn.focus_set()

    popup.bind("<Return>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    root.wait_window(popup)


def confirm_exit():
    popup = tk.Toplevel(root)
    popup.title("Confirm Exit")
    popup.configure(bg=CARD_BG)
    popup.resizable(False, False)
    popup.transient(root)
    popup.grab_set()

    width, height = 500, 260
    x = (popup.winfo_screenwidth() // 2) - (width // 2)
    y = (popup.winfo_screenheight() // 2) - (height // 2)
    popup.geometry(f"{width}x{height}+{x}+{y}")

    tk.Frame(popup, bg=RED, height=12).pack(fill="x")

    content = tk.Frame(popup, bg=CARD_BG, padx=48, pady=36)
    content.pack(fill="both", expand=True)

    tk.Label(
        content,
        text="Exit Login",
        bg=CARD_BG,
        fg=TEXT_DARK,
        font=("Arial", 28, "bold")
    ).pack(pady=(0, 14))

    tk.Label(
        content,
        text="Are you sure you want to exit?",
        bg=CARD_BG,
        fg=TEXT_MUTED,
        font=("Arial", 17),
        wraplength=400,
        justify="center"
    ).pack(pady=(0, 28))

    button_row = tk.Frame(content, bg=CARD_BG)
    button_row.pack()

    def close_popup():
        popup.destroy()

    tk.Button(
        button_row,
        text="Cancel",
        command=close_popup,
        bg="#6b7280",
        fg="white",
        activebackground="#4b5563",
        font=("Arial", 15, "bold"),
        relief="flat",
        width=12,
        pady=9
    ).pack(side="left", padx=8)

    tk.Button(
        button_row,
        text="Exit",
        command=root.destroy,
        bg=RED,
        fg="white",
        activebackground="#b91c1c",
        font=("Arial", 15, "bold"),
        relief="flat",
        width=12,
        pady=9
    ).pack(side="left", padx=8)

    popup.bind("<Return>", lambda _event: root.destroy())
    popup.bind("<Escape>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)


def login():
    username = username_entry.get().strip()
    password_input = password_entry.get()

    if username == "" or password_input.strip() == "":
        show_error_popup("Error", "All fields are required.")
        return

    if not validate_common_inputs(username, password_input, error_callback=show_error_popup):
        return

    if not is_valid_username(username) or not is_valid_password(password_input):
        show_error_popup("Error", "Invalid input detected.")
        return

    user = get_authenticated_user(username, password_input)

    if user:
        role = user[2]
        if role not in ("Admin", "Cashier"):
            show_error_popup("Error", "Access denied. Unauthorized role.")
            return
        show_success_popup(role)
        open_main_in_place(role)
    else:
        show_error_popup("Error", "Invalid username or password.")


def forgot_password():
    reset_window = tk.Toplevel(root)
    reset_window.title("Forgot Password")
    reset_window.configure(bg=CARD_BG)
    reset_window.resizable(False, False)
    reset_window.grab_set()

    width, height = 620, 620
    x = (reset_window.winfo_screenwidth() // 2) - (width // 2)
    y = (reset_window.winfo_screenheight() // 2) - (height // 2)
    reset_window.geometry(f"{width}x{height}+{x}+{y}")

    def show_reset_popup(title, message, color):
        popup = tk.Toplevel(reset_window)
        popup.title(title)
        popup.configure(bg=CARD_BG)
        popup.resizable(False, False)
        popup.transient(reset_window)
        popup.grab_set()

        popup_width, popup_height = 500, 260
        popup_x = reset_window.winfo_rootx() + (reset_window.winfo_width() // 2) - (popup_width // 2)
        popup_y = reset_window.winfo_rooty() + (reset_window.winfo_height() // 2) - (popup_height // 2)
        popup.geometry(f"{popup_width}x{popup_height}+{max(popup_x, 0)}+{max(popup_y, 0)}")

        tk.Frame(popup, bg=color, height=12).pack(fill="x")
        content = tk.Frame(popup, bg=CARD_BG, padx=48, pady=36)
        content.pack(fill="both", expand=True)
        tk.Label(content, text=title, bg=CARD_BG, fg=color, font=("Arial", 28, "bold")).pack(pady=(0, 14))
        tk.Label(content, text=message, bg=CARD_BG, fg=TEXT_DARK, font=("Arial", 17), wraplength=400, justify="center").pack(pady=(0, 28))

        def close_popup():
            popup.destroy()

        ok_btn = tk.Button(content, text="OK", command=close_popup, bg=color, fg="white", font=("Arial", 15, "bold"), relief="flat", width=14, pady=9)
        ok_btn.pack()
        ok_btn.focus_set()
        popup.bind("<Return>", lambda _event: close_popup())
        popup.bind("<Escape>", lambda _event: close_popup())
        popup.protocol("WM_DELETE_WINDOW", close_popup)
        reset_window.wait_window(popup)

    def show_reset_error(message):
        show_reset_popup("Error", message, RED)

    def show_reset_success(message):
        show_reset_popup("Success", message, GREEN)

    def ask_reset_confirmation(message):
        popup = tk.Toplevel(reset_window)
        popup.title("Confirm")
        popup.configure(bg=CARD_BG)
        popup.resizable(False, False)
        popup.transient(reset_window)
        popup.grab_set()
        confirmed = {"value": False}

        popup_width, popup_height = 520, 280
        popup_x = reset_window.winfo_rootx() + (reset_window.winfo_width() // 2) - (popup_width // 2)
        popup_y = reset_window.winfo_rooty() + (reset_window.winfo_height() // 2) - (popup_height // 2)
        popup.geometry(f"{popup_width}x{popup_height}+{max(popup_x, 0)}+{max(popup_y, 0)}")

        tk.Frame(popup, bg=BG_BLUE, height=12).pack(fill="x")
        content = tk.Frame(popup, bg=CARD_BG, padx=48, pady=36)
        content.pack(fill="both", expand=True)
        tk.Label(content, text="Confirm", bg=CARD_BG, fg=BG_BLUE, font=("Arial", 28, "bold")).pack(pady=(0, 14))
        tk.Label(content, text=message, bg=CARD_BG, fg=TEXT_DARK, font=("Arial", 17), wraplength=420, justify="center").pack(pady=(0, 28))
        button_row = tk.Frame(content, bg=CARD_BG)
        button_row.pack()

        def yes():
            confirmed["value"] = True
            popup.destroy()

        def no():
            popup.destroy()

        tk.Button(button_row, text="Yes", command=yes, bg=GREEN, fg="white", font=("Arial", 14, "bold"), relief="flat", width=12, pady=8).pack(side="left", padx=8)
        tk.Button(button_row, text="No", command=no, bg=RED, fg="white", font=("Arial", 14, "bold"), relief="flat", width=12, pady=8).pack(side="left", padx=8)
        popup.bind("<Return>", lambda _event: yes())
        popup.bind("<Escape>", lambda _event: no())
        popup.protocol("WM_DELETE_WINDOW", no)
        reset_window.wait_window(popup)
        return confirmed["value"]

    tk.Label(
        reset_window,
        text="Reset Password",
        bg=CARD_BG,
        fg=BG_BLUE,
        font=("Arial", 26, "bold")
    ).pack(pady=(28, 8))

    tk.Label(
        reset_window,
        text="Verify your identity using your registered contact number.",
        bg=CARD_BG,
        fg=TEXT_MUTED,
        font=("Arial", 14)
    ).pack(pady=(0, 22))

    form = tk.Frame(reset_window, bg=CARD_BG)
    form.pack(fill="x", padx=64)

    tk.Label(form, text="Username", bg=CARD_BG, fg=TEXT_DARK,
             font=("Arial", 14, "bold")).pack(anchor="w")
    reset_username_entry = tk.Entry(form, width=42, font=("Arial", 15), bd=1, relief="solid")
    reset_username_entry.pack(pady=(7, 14), ipady=6)

    contact_hint_var = tk.StringVar(value="Enter your username and registered contact number.")
    tk.Label(form, textvariable=contact_hint_var, bg=CARD_BG, fg=TEXT_DARK,
             wraplength=450, justify="left", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 5))

    contact_entry = tk.Entry(form, width=42, font=("Arial", 15), bd=1, relief="solid")
    contact_entry.pack(pady=(7, 14), ipady=6)

    password_frame = tk.Frame(form, bg=CARD_BG)
    password_verified = tk.BooleanVar(value=False)

    tk.Label(password_frame, text="New Password", bg=CARD_BG, fg=TEXT_DARK,
             font=("Arial", 14, "bold")).pack(anchor="w")
    new_password_entry = tk.Entry(password_frame, show="*", width=42, font=("Arial", 15), bd=1, relief="solid")
    new_password_entry.pack(pady=(7, 14), ipady=6)

    tk.Label(password_frame, text="Confirm Password", bg=CARD_BG, fg=TEXT_DARK,
             font=("Arial", 14, "bold")).pack(anchor="w")
    confirm_password_entry = tk.Entry(password_frame, show="*", width=42, font=("Arial", 15), bd=1, relief="solid")
    confirm_password_entry.pack(pady=(7, 14), ipady=6)

    show_password_var = tk.BooleanVar(value=False)

    def toggle_reset_password_visibility():
        show_char = "" if show_password_var.get() else "*"
        new_password_entry.config(show=show_char)
        confirm_password_entry.config(show=show_char)

    tk.Checkbutton(
        password_frame,
        text="Show Password",
        variable=show_password_var,
        command=toggle_reset_password_visibility,
        bg=CARD_BG,
        fg=TEXT_DARK,
        activebackground=CARD_BG,
        font=("Arial", 13, "bold")
    ).pack(anchor="w", pady=(0, 12))

    def load_contact_check():
        reset_username = reset_username_entry.get().strip()
        contact_number = contact_entry.get().strip()

        if reset_username == "" or contact_number == "":
            show_reset_error("All fields are required.")
            return
        if not validate_common_inputs(reset_username, contact_number):
            return
        if not is_valid_username(reset_username) or not is_valid_contact_number(contact_number):
            show_reset_error("Invalid input detected.")
            return

        saved_contact = get_contact_number(reset_username)
        if not saved_contact:
            show_reset_error("The details are incorrect.")
            return

        normalize = lambda value: value.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if normalize(saved_contact) != normalize(contact_number):
            show_reset_error("The details are incorrect.")
            return

        password_verified.set(True)
        contact_hint_var.set("Details verified. Enter your new password.")
        password_frame.pack(fill="x")
        if not reset_password_button.winfo_manager():
            reset_password_button.pack(side="right")
        new_password_entry.focus_set()
        show_reset_success("Details verified successfully.")

    def reset_password():
        reset_username = reset_username_entry.get().strip()
        contact_number = contact_entry.get().strip()
        new_password = new_password_entry.get()
        confirm_password = confirm_password_entry.get()

        if not password_verified.get():
            show_reset_error("Verify username and contact number first.")
            return

        if reset_username == "" or contact_number == "" or new_password.strip() == "" or confirm_password.strip() == "":
            show_reset_error("All fields are required.")
            return
        if not validate_common_inputs(reset_username, contact_number, new_password, confirm_password):
            return
        if (
            not is_valid_username(reset_username)
            or not is_valid_contact_number(contact_number)
            or not is_valid_password(new_password)
        ):
            show_reset_error("Invalid input detected.")
            return
        if new_password != confirm_password:
            show_reset_error("New Password and Confirm Password must match.")
            return

        if not ask_reset_confirmation("Are you sure you want to reset this password?"):
            return

        if not reset_user_password_with_contact(reset_username, contact_number, new_password):
            show_reset_error("The details are incorrect.")
            return

        show_reset_success("Password reset successful.")
        reset_window.destroy()

    button_row = tk.Frame(form, bg=CARD_BG)
    button_row.pack(fill="x")

    tk.Button(
        button_row,
        text="Verify Details",
        command=load_contact_check,
        bg="#2563eb",
        fg="white",
        activebackground="#1d4ed8",
        relief="flat",
        font=("Arial", 13, "bold"),
        padx=16,
        pady=10
    ).pack(side="left")

    reset_password_button = tk.Button(
        button_row,
        text="Reset Password",
        command=reset_password,
        bg=GREEN,
        fg="white",
        activebackground=GREEN_HOVER,
        relief="flat",
        font=("Arial", 13, "bold"),
        padx=16,
        pady=10
    )


def on_enter(e):
    e.widget["background"] = GREEN_HOVER


def on_leave(e):
    e.widget["background"] = GREEN


def show_login_screen():
    global main_frame, login_frame, username_entry, password_entry, login_btn

    root.title("Login")
    try:
        root.state("zoomed")
    except Exception:
        pass
    root.configure(bg=BG_BLUE)

    for child in root.winfo_children():
        child.destroy()

    main_frame = tk.Frame(root, bg=BG_BLUE)
    main_frame.pack(expand=True)

    tk.Label(
        main_frame,
        text="JASP Hardware System",
        font=("Arial", 34, "bold"),
        bg=BG_BLUE,
        fg="white"
    ).pack(pady=(0, 6))

    tk.Label(
        main_frame,
        text="Inventory and sales management",
        font=("Arial", 15),
        bg=BG_BLUE,
        fg="#dbeafe"
    ).pack(pady=(0, 24))

    login_frame = tk.Frame(main_frame, bg=CARD_BG, padx=50, pady=38)
    login_frame.pack()

    tk.Label(
        login_frame,
        text="Login to continue",
        font=("Arial", 22, "bold"),
        bg=CARD_BG,
        fg=TEXT_DARK
    ).pack(pady=(0, 6))

    tk.Label(
        login_frame,
        text="Enter your account credentials",
        font=("Arial", 13),
        bg=CARD_BG,
        fg=TEXT_MUTED
    ).pack(pady=(0, 20))

    tk.Label(login_frame, text="Username",
             font=("Arial", 13, "bold"), bg=CARD_BG, fg=TEXT_DARK).pack(anchor="w")

    username_entry = tk.Entry(login_frame, width=32, font=("Arial", 14), bd=1, relief="solid")
    username_entry.pack(pady=(8, 14), ipady=6)

    tk.Label(login_frame, text="Password",
             font=("Arial", 13, "bold"), bg=CARD_BG, fg=TEXT_DARK).pack(anchor="w")

    password_entry = tk.Entry(login_frame, show="*", width=32, font=("Arial", 14), bd=1, relief="solid")
    password_entry.pack(pady=(8, 8), ipady=6)

    show_password_var = tk.BooleanVar(value=False)

    def toggle_password_visibility():
        password_entry.config(show="" if show_password_var.get() else "*")

    tk.Checkbutton(
        login_frame,
        text="Show password",
        variable=show_password_var,
        command=toggle_password_visibility,
        bg=CARD_BG,
        fg=TEXT_DARK,
        activebackground=CARD_BG,
        activeforeground=TEXT_DARK,
        selectcolor=CARD_BG,
        font=("Arial", 14),
        padx=6,
        pady=4
    ).pack(anchor="w", pady=(0, 10))

    forgot_btn = tk.Button(
        login_frame,
        text="Forgot Password?",
        command=forgot_password,
        bg=CARD_BG,
        fg=BG_BLUE,
        activebackground=CARD_BG,
        activeforeground="#123a78",
        bd=0,
        relief="flat",
        cursor="hand2",
        font=("Arial", 12, "bold")
    )
    forgot_btn.pack(anchor="e", pady=(0, 14))

    login_btn = tk.Button(
        login_frame,
        text="Login",
        font=("Arial", 14, "bold"),
        width=26,
        bg=GREEN,
        fg="white",
        activebackground=GREEN_HOVER,
        relief="flat",
        command=login
    )
    login_btn.pack(pady=(0, 4), ipady=6)

    login_btn.bind("<Enter>", on_enter)
    login_btn.bind("<Leave>", on_leave)
    root.bind("<Return>", lambda _event: login())

    tk.Button(
        root,
        text="Exit",
        command=confirm_exit,
        bg=RED,
        fg="white",
        activebackground="#b91c1c",
        font=("Arial", 14, "bold"),
        relief="flat",
        padx=18,
        pady=8
    ).place(x=24, y=24)


def run_app():
    global root

    root = tk.Tk()
    show_login_screen()
    root.mainloop()
