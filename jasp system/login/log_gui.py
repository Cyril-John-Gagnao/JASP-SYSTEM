import os
import tkinter as tk
from tkinter import messagebox
from main_dashboard import session
from window_utils import enable_centered_toplevels
from jasp_theme import (
    DASHBOARD_CONTENT_BG,
    DASHBOARD_HEADER_BG,
    DASHBOARD_HEADER_BORDER,
    DASHBOARD_HEADER_FG,
    DASHBOARD_HEADER_SUBTLE_FG,
    add_header_logo,
)

from .database import (
    get_authenticated_user,
    get_contact_number,
    reset_user_password_with_contact,
)
from .functions import (
    is_valid_contact_number,
    is_valid_password,
    is_valid_username,
    validate_common_inputs,
)

enable_centered_toplevels()

# Define login page colors and shared UI state references.
BG_BLUE = "#1950a3"
LOGIN_HEADER_BG = "#072a4e"
LOGIN_PAGE_BG = "#fff3e6"
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
    # Route authenticated users to the correct workspace by role.
    try:
        if user_role == "Admin":
            from main_dashboard.main_gui import open_main
            open_main(root, show_login_screen)
        elif user_role == "Cashier":
            open_cashier_dashboard()
        else:
            # Reject accounts with unsupported roles.
            messagebox.showerror("Error", "Access denied. Unauthorized role.")
    except Exception as e:
        messagebox.showerror(
            "Error Loading Dashboard",
            f"Failed to load dashboard:\n\n{str(e)}\n\nCheck console for details."
        )
        import traceback
        traceback.print_exc()


def open_pos_for_cashier():
    # Open the POS module for cashier-only access.
    try:
        from pos_module import open_pos
        open_pos()
    except Exception as e:
        messagebox.showerror("Error Loading POS", f"Failed to load POS:\n\n{str(e)}")


def open_cashier_dashboard():
    # Replace the login screen with the cashier workspace.
    root.title("JASP Cashier")
    try:
        root.state("zoomed")
    except Exception:
        pass
    root.configure(bg=DASHBOARD_CONTENT_BG)

    # Clear the current root contents before drawing the cashier dashboard.
    for child in root.winfo_children():
        child.destroy()

    # Build the cashier dashboard header.
    header = tk.Frame(
        root,
        bg=DASHBOARD_HEADER_BG,
        height=96,
        padx=20,
        pady=12,
        highlightthickness=1,
        highlightbackground=DASHBOARD_HEADER_BORDER,
    )
    header.pack(fill="x", padx=20, pady=(12, 8))
    header.pack_propagate(False)

    header_left = tk.Frame(header, bg=DASHBOARD_HEADER_BG)
    header_left.pack(side="left")
    add_header_logo(header_left, DASHBOARD_HEADER_BG, size=62)
    title_block = tk.Frame(header_left, bg=DASHBOARD_HEADER_BG)
    title_block.pack(side="left")
    tk.Label(
        title_block,
        text="JASP Hardware System",
        bg=DASHBOARD_HEADER_BG,
        fg=DASHBOARD_HEADER_FG,
        font=("Arial", 22, "bold")
    ).pack(anchor="w")
    tk.Label(
        title_block,
        text="Cashier Workspace",
        bg=DASHBOARD_HEADER_BG,
        fg=DASHBOARD_HEADER_SUBTLE_FG,
        font=("Arial", 12, "bold")
    ).pack(anchor="w", pady=(3, 0))

    tk.Button(
        header,
        text="Logout",
        command=show_login_screen,
        bg=RED,
        fg="white",
        activebackground="#b91c1c",
        activeforeground="white",
        font=("Arial", 13, "bold"),
        relief="solid",
        bd=2,
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black",
        padx=18,
        pady=8
    ).pack(side="right")

    # Build the central cashier POS access card.
    content = tk.Frame(root, bg=DASHBOARD_CONTENT_BG)
    content.pack(expand=True)

    card = tk.Frame(
        content,
        bg=CARD_BG,
        padx=56,
        pady=42,
        highlightthickness=2,
        highlightbackground=DASHBOARD_HEADER_BG,
    )
    card.pack()

    tk.Label(
        card,
        text="Point of Sale",
        bg=CARD_BG,
        fg=TEXT_DARK,
        font=("Arial", 30, "bold")
    ).pack(pady=(0, 8))

    tk.Label(
        card,
        text="Cashier access is limited to POS transactions only.",
        bg=CARD_BG,
        fg=TEXT_MUTED,
        font=("Arial", 14)
    ).pack(pady=(0, 24))

    tk.Button(
        card,
        text="Open POS",
        command=open_pos_for_cashier,
        bg=GREEN,
        fg="white",
        activebackground=GREEN_HOVER,
        activeforeground="white",
        font=("Arial", 16, "bold"),
        relief="solid",
        bd=2,
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black",
        width=24,
        pady=12
    ).pack()


def show_success_popup(user_role):
    # Show a modal login success popup before opening the workspace.
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
        # Close the success popup.
        popup.destroy()

    # Build the continue button for the success popup.
    ok_btn = tk.Button(
        content,
        text="Continue",
        command=close_popup,
        bg=GREEN,
        fg="white",
        activebackground=GREEN_HOVER,
        font=("Arial", 15, "bold"),
        relief="solid",
        bd=2,
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black",
        width=18,
        pady=10
    )
    ok_btn.pack()
    ok_btn.focus_set()

    popup.bind("<Return>", lambda _event: close_popup())
    popup.protocol("WM_DELETE_WINDOW", close_popup)
    root.wait_window(popup)


def show_error_popup(title, message):
    # Show a modal login error popup.
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
        # Close the error popup.
        popup.destroy()

    # Build the OK button for the error popup.
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
    # Ask the user to confirm exiting the login screen.
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
        # Close the exit confirmation dialog.
        popup.destroy()

    # Build cancel and exit action buttons.
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
    # Read login fields and validate credentials before opening a workspace.
    username = username_entry.get().strip()
    password_input = password_entry.get()

    if username == "" or password_input.strip() == "":
        # Require both username and password.
        show_error_popup("Error", "All fields are required.")
        return

    if not validate_common_inputs(username, password_input, error_callback=show_error_popup):
        # Block suspicious or unsafe text input.
        return

    if not is_valid_username(username) or not is_valid_password(password_input):
        # Enforce username/password format rules.
        show_error_popup("Error", "Invalid input detected.")
        return

    user = get_authenticated_user(username, password_input)

    if user:
        # Store the authenticated session and continue to the correct workspace.
        role = user[2]
        if role not in ("Admin", "Cashier"):
            show_error_popup("Error", "Access denied. Unauthorized role.")
            return
        session.set_current_user(user[0], user[1], role)
        show_success_popup(role)
        open_main_in_place(role)
    else:
        # Show a generic login failure message for invalid credentials.
        show_error_popup("Error", "Invalid username or password.")


def forgot_password():
    # Open the password reset flow using username and registered contact number.
    reset_window = tk.Toplevel(root)
    reset_window.title("Forgot Password")
    reset_window.configure(bg=CARD_BG)
    reset_window.resizable(False, False)
    reset_window.grab_set()

    width, height = 620, 760
    x = (reset_window.winfo_screenwidth() // 2) - (width // 2)
    y = (reset_window.winfo_screenheight() // 2) - (height // 2)
    reset_window.geometry(f"{width}x{height}+{x}+{y}")

    def show_reset_popup(title, message, color):
        # Show a modal popup inside the reset password window.
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
            # Close the reset popup.
            popup.destroy()

        # Build the OK button for reset popups.
        ok_btn = tk.Button(content, text="OK", command=close_popup, bg=color, fg="white", font=("Arial", 15, "bold"), relief="flat", width=14, pady=9)
        ok_btn.pack()
        ok_btn.focus_set()
        popup.bind("<Return>", lambda _event: close_popup())
        popup.bind("<Escape>", lambda _event: close_popup())
        popup.protocol("WM_DELETE_WINDOW", close_popup)
        reset_window.wait_window(popup)

    def show_reset_error(message):
        # Display a reset-password error popup.
        show_reset_popup("Error", message, RED)

    def show_invalid_reset_input(_title="Error", message="Invalid input detected."):
        # Adapter used by shared validation to show reset errors.
        show_reset_error(message)

    def show_reset_success(message):
        # Display a reset-password success popup.
        show_reset_popup("Success", message, GREEN)

    def ask_reset_confirmation(message):
        # Ask for confirmation before changing a password.
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
            # Mark the reset confirmation as accepted.
            confirmed["value"] = True
            popup.destroy()

        def no():
            # Close the reset confirmation without accepting.
            popup.destroy()

        # Build yes/no buttons for reset confirmation.
        tk.Button(button_row, text="Yes", command=yes, bg=GREEN, fg="white", font=("Arial", 14, "bold"), relief="flat", width=12, pady=8).pack(side="left", padx=8)
        tk.Button(button_row, text="No", command=no, bg=RED, fg="white", font=("Arial", 14, "bold"), relief="flat", width=12, pady=8).pack(side="left", padx=8)
        popup.bind("<Return>", lambda _event: yes())
        popup.bind("<Escape>", lambda _event: no())
        popup.protocol("WM_DELETE_WINDOW", no)
        reset_window.wait_window(popup)
        return confirmed["value"]

    # Build the reset window close button and title area.
    top_bar = tk.Frame(reset_window, bg=CARD_BG)
    top_bar.pack(fill="x", padx=12, pady=(10, 0))
    tk.Button(
        top_bar,
        text="X",
        command=reset_window.destroy,
        bg=RED,
        fg="white",
        activebackground="#b91c1c",
        activeforeground="white",
        relief="flat",
        font=("Arial", 11, "bold"),
        width=3,
    ).pack(side="right")

    tk.Label(
        reset_window,
        text="Reset Password",
        bg=CARD_BG,
        fg=BG_BLUE,
        font=("Arial", 26, "bold")
    ).pack(pady=(8, 8))

    tk.Label(
        reset_window,
        text="Verify your identity using your registered contact number.",
        bg=CARD_BG,
        fg=TEXT_MUTED,
        font=("Arial", 14)
    ).pack(pady=(0, 22))

    # Build the reset verification form fields.
    form = tk.Frame(reset_window, bg=CARD_BG)
    form.pack(fill="x", padx=64)

    tk.Label(form, text="Username", bg=CARD_BG, fg=TEXT_DARK,
             font=("Arial", 14, "bold")).pack(anchor="w")
    reset_username_entry = tk.Entry(form, width=42, font=("Arial", 15), bd=1, relief="solid")
    reset_username_entry.pack(pady=(7, 14), ipady=6)

    contact_hint_var = tk.StringVar(value="Enter your registered contact number.")
    tk.Label(form, textvariable=contact_hint_var, bg=CARD_BG, fg=TEXT_DARK,
             wraplength=450, justify="left", font=("Arial", 13, "bold")).pack(anchor="w", pady=(0, 5))

    contact_entry = tk.Entry(form, width=42, font=("Arial", 15), bd=1, relief="solid")
    contact_entry.pack(pady=(7, 14), ipady=6)

    # Keep new-password fields hidden until contact details are verified.
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
        # Toggle visibility for both new password fields.
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

    reset_password_button = tk.Button(
        password_frame,
        text="Reset Password",
        command=lambda: reset_password(),
        bg=GREEN,
        fg="white",
        activebackground=GREEN_HOVER,
        relief="flat",
        font=("Arial", 13, "bold"),
        height=2,
        padx=16,
        pady=12
    )

    def load_contact_check():
        # Verify username and registered contact number before showing password fields.
        reset_username = reset_username_entry.get().strip()
        contact_number = contact_entry.get().strip()

        if reset_username == "" or contact_number == "":
            # Require username and contact number for verification.
            show_reset_error("All fields are required.")
            return
        if not validate_common_inputs(reset_username, contact_number, error_callback=show_invalid_reset_input):
            # Block suspicious verification input.
            return
        if not is_valid_username(reset_username) or not is_valid_contact_number(contact_number):
            # Enforce username and contact-number formats.
            show_reset_error("Invalid input detected.")
            return

        saved_contact = get_contact_number(reset_username)
        if not saved_contact:
            # Hide whether the username or contact number was wrong.
            show_reset_error("The details are incorrect.")
            return
        normalize = lambda value: value.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
        if normalize(saved_contact) != normalize(contact_number):
            # Reject reset flow when contact numbers do not match.
            show_reset_error("The details are incorrect.")
            return

        password_verified.set(True)
        contact_hint_var.set("Details verified. Enter your new password.")
        password_frame.pack(fill="x")
        if not reset_password_button.winfo_manager():
            reset_password_button.pack(anchor="center", fill="x", pady=(4, 10), ipady=6)
        new_password_entry.focus_set()
        show_reset_success("Details verified successfully.")

    def reset_password():
        # Validate and apply the new password after contact verification.
        reset_username = reset_username_entry.get().strip()
        contact_number = contact_entry.get().strip()
        new_password = new_password_entry.get()
        confirm_password = confirm_password_entry.get()

        if not password_verified.get():
            # Require successful contact verification first.
            show_reset_error("Verify username and contact number first.")
            return

        if reset_username == "" or contact_number == "" or new_password.strip() == "" or confirm_password.strip() == "":
            # Require all reset fields before changing the password.
            show_reset_error("All fields are required.")
            return
        if not validate_common_inputs(
            reset_username,
            contact_number,
            new_password,
            confirm_password,
            error_callback=show_invalid_reset_input,
        ):
            # Block suspicious reset-password input.
            return
        if (
            not is_valid_username(reset_username)
            or not is_valid_contact_number(contact_number)
            or not is_valid_password(new_password)
        ):
            # Enforce username, contact number, and password format rules.
            show_reset_error("Invalid input detected.")
            return
        if new_password != confirm_password:
            # Require both new password entries to match.
            show_reset_error("New Password and Confirm Password must match.")
            return

        if not ask_reset_confirmation("Are you sure you want to reset this password?"):
            # Stop when the user cancels the reset confirmation.
            return

        if not reset_user_password_with_contact(reset_username, contact_number, new_password):
            show_reset_error("The details are incorrect.")
            return

        show_reset_success("Password reset successful.")
        reset_window.destroy()

    # Build the verify button row.
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


def on_enter(e):
    # Apply the login button hover color.
    e.widget["background"] = GREEN_HOVER


def on_leave(e):
    # Restore the login button normal color.
    e.widget["background"] = GREEN


def load_login_logo(size=82):
    # Load the transparent login logo image when available.
    logo_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "images", "logo1.png"))
    try:
        from PIL import Image, ImageTk

        source = Image.open(logo_path).convert("RGBA")
        source.thumbnail((size, size), Image.LANCZOS)
        logo = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        x_pos = (size - source.width) // 2
        y_pos = (size - source.height) // 2
        logo.paste(source, (x_pos, y_pos), source)
        return ImageTk.PhotoImage(logo)
    except (ImportError, OSError, AttributeError, tk.TclError):
        # Fall back to Tk PhotoImage if Pillow is unavailable.
        try:
            image = tk.PhotoImage(file=logo_path)
            image = image.subsample(max(1, image.width() // size), max(1, image.height() // size))
            return image
        except tk.TclError:
            return None


def show_login_screen():
    # Draw the main login screen and clear any active session.
    global main_frame, login_frame, username_entry, password_entry, login_btn

    session.clear_current_user()

    root.title("Login")
    try:
        root.state("zoomed")
    except Exception:
        pass
    root.configure(bg=LOGIN_PAGE_BG)

    # Clear current root contents before drawing the login page.
    for child in root.winfo_children():
        child.destroy()

    # Build the login header with logo and exit button.
    header = tk.Frame(root, bg=LOGIN_HEADER_BG, height=112, highlightthickness=1, highlightbackground="#041d36")
    header.pack(fill="x")
    header.pack_propagate(False)

    header_left = tk.Frame(header, bg=LOGIN_HEADER_BG)
    header_left.pack(side="left", padx=24, pady=12)
    logo_image = load_login_logo(86)
    if logo_image:
        header.logo_image = logo_image
        tk.Label(header_left, image=logo_image, bg=LOGIN_HEADER_BG).pack(side="left", padx=(0, 16))
    tk.Label(
        header_left,
        text="JASP Hardware System",
        font=("Arial", 22, "bold"),
        bg=LOGIN_HEADER_BG,
        fg="white",
    ).pack(side="left")

    tk.Button(
        header,
        text="Exit",
        command=confirm_exit,
        bg=RED,
        fg="white",
        activebackground="#b91c1c",
        activeforeground="white",
        font=("Arial", 13, "bold"),
        relief="solid",
        bd=2,
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black",
        padx=18,
        pady=8
    ).pack(side="right", padx=24, pady=18)

    # Build the centered login content area.
    main_frame = tk.Frame(root, bg=LOGIN_PAGE_BG)
    main_frame.pack(expand=True)

    tk.Label(
        main_frame,
        text="Sales and Inventory Management",
        font=("Arial", 24, "bold"),
        bg=LOGIN_PAGE_BG,
        fg="#9a3412"
    ).pack(pady=(0, 24))

    # Build the login form card.
    login_frame = tk.Frame(
        main_frame,
        bg=CARD_BG,
        padx=50,
        pady=38,
        highlightthickness=3,
        highlightbackground=LOGIN_HEADER_BG,
        highlightcolor=LOGIN_HEADER_BG,
    )
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
        # Toggle password visibility on the login form.
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
        relief="solid",
        bd=2,
        highlightthickness=1,
        highlightbackground="black",
        highlightcolor="black",
        command=login
    )
    login_btn.pack(pady=(0, 4), ipady=6)

    # Wire login button hover states and Enter key submission.
    login_btn.bind("<Enter>", on_enter)
    login_btn.bind("<Leave>", on_leave)
    root.bind("<Return>", lambda _event: login())


def run_app():
    # Create the Tk root window and start the login application loop.
    global root

    root = tk.Tk()
    show_login_screen()
    root.mainloop()
