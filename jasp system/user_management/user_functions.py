import sqlite3
import tkinter as tk

from . import user_database


# Keep shared user-management state and UI colors in one place.
current_user_role = "Admin"
DEFAULT_SECURITY_QUESTION = "What is your username?"
SAVE_GREEN = "#00c853"
CANCEL_RED = "#dc2626"
PRIMARY_BLUE = "#2563eb"


def center_window(window, width, height, parent=None):
    # Center a popup over its parent window or the screen.
    window.update_idletasks()
    if parent and parent.winfo_exists():
        x = parent.winfo_rootx() + (parent.winfo_width() // 2) - (width // 2)
        y = parent.winfo_rooty() + (parent.winfo_height() // 2) - (height // 2)
    else:
        x = (window.winfo_screenwidth() // 2) - (width // 2)
        y = (window.winfo_screenheight() // 2) - (height // 2)
    window.geometry(f"{width}x{height}+{max(x, 0)}+{max(y, 0)}")


def get_popup_parent(widget):
    # Resolve the nearest top-level window for popup ownership.
    try:
        return widget.winfo_toplevel()
    except Exception:
        return None


def show_user_popup(parent, title, message, accent_color, button_text="OK"):
    # Show a reusable modal popup for user-management messages.
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)

    tk.Frame(popup, bg=accent_color, height=12).pack(fill="x")
    content = tk.Frame(popup, bg="#ffffff", padx=48, pady=36)
    content.pack(fill="both", expand=True)
    tk.Label(content, text=title, bg="#ffffff", fg=accent_color, font=("Arial", 28, "bold")).pack(pady=(0, 14))
    tk.Label(content, text=message, bg="#ffffff", fg="#111827", font=("Arial", 17), wraplength=430, justify="center").pack(pady=(0, 28))

    def close_popup():
        # Close the active message popup.
        popup.destroy()

    # Build the popup action button and keyboard shortcuts.
    ok_btn = tk.Button(
        content,
        text=button_text,
        command=close_popup,
        bg=accent_color,
        fg="white",
        activebackground=accent_color,
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
    center_window(popup, 540, 290, parent)
    parent.wait_window(popup)


def show_user_error(parent, title, message):
    # Show a red error popup.
    show_user_popup(parent, title, message, CANCEL_RED)


def show_user_success(parent, title, message):
    # Show a green success popup.
    show_user_popup(parent, title, message, SAVE_GREEN)


def ask_user_confirmation(parent, title, message):
    # Ask the user to confirm a destructive action.
    popup = tk.Toplevel(parent)
    popup.title(title)
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#ffffff")
    popup.resizable(False, False)
    result = {"confirmed": False}

    tk.Frame(popup, bg=PRIMARY_BLUE, height=12).pack(fill="x")
    content = tk.Frame(popup, bg="#ffffff", padx=48, pady=36)
    content.pack(fill="both", expand=True)
    tk.Label(content, text=title, bg="#ffffff", fg=PRIMARY_BLUE, font=("Arial", 26, "bold")).pack(pady=(0, 14))
    tk.Label(content, text=message, bg="#ffffff", fg="#111827", font=("Arial", 17), wraplength=460, justify="center").pack(pady=(0, 28))

    button_frame = tk.Frame(content, bg="#ffffff")
    button_frame.pack()

    def confirm():
        # Mark the confirmation as accepted.
        result["confirmed"] = True
        popup.destroy()

    def cancel():
        # Close the confirmation popup without accepting.
        popup.destroy()

    # Build confirmation buttons and modal keyboard shortcuts.
    tk.Button(button_frame, text="Yes", command=confirm, bg=SAVE_GREEN, fg="white", font=("Arial", 14, "bold"), relief="flat", width=12, pady=8).pack(side="left", padx=8)
    tk.Button(button_frame, text="No", command=cancel, bg=CANCEL_RED, fg="white", font=("Arial", 14, "bold"), relief="flat", width=12, pady=8).pack(side="left", padx=8)
    popup.bind("<Return>", lambda _event: confirm())
    popup.bind("<Escape>", lambda _event: cancel())
    popup.protocol("WM_DELETE_WINDOW", cancel)
    center_window(popup, 560, 320, parent)
    parent.wait_window(popup)
    return result["confirmed"]


def normalize_contact_number(contact_number):
    # Normalize and validate contact numbers with optional plus prefix.
    cleaned = contact_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if cleaned.startswith("+"):
        digits = cleaned[1:]
        if digits.isdigit() and 10 <= len(digits) <= 15:
            return cleaned
        return None
    if cleaned.isdigit() and 10 <= len(cleaned) <= 15:
        return cleaned
    return None


def validate_user_form(parent, username, password, confirm_password, role, contact_number, require_password=True):
    # Validate required fields, password rules, and contact number format.
    if not username or not password or not confirm_password or role == "Select Role" or not contact_number:
        if require_password or not username or role == "Select Role" or not contact_number:
            show_user_error(parent, "Error", "All required fields must be filled.")
            return None
    if require_password and (not password or not confirm_password):
        show_user_error(parent, "Error", "Password and Confirm Password are required.")
        return None
    if password or confirm_password:
        if len(password) < 4:
            show_user_error(parent, "Error", "Password too weak.")
            return None
        if password != confirm_password:
            show_user_error(parent, "Error", "Confirm password is incorrect.")
            return None
    elif require_password:
        show_user_error(parent, "Error", "Password and Confirm Password are required.")
        return None
    normalized_contact = normalize_contact_number(contact_number)
    if not normalized_contact:
        show_user_error(parent, "Error", "Contact Number must be 10 to 15 digits. It may start with +.")
        return None
    return normalized_contact


def get_filtered_users(cursor, role, search_text=""):
    # Return users for one role that match the optional search text.
    search_text = search_text.strip().lower()
    users = []
    for row in user_database.get_users(cursor):
        row_role = row[2] or ""
        if row_role.lower() != role.lower():
            continue
        username = row[1] or ""
        contact_number = row[4] or ""
        if search_text and search_text not in username.lower() and search_text not in contact_number.lower():
            continue
        users.append(row)
    return users


def clear_user_form(username_entry, password_entry, confirm_password_entry, role_var, contact_entry, selected_user_id):
    # Reset the user form fields and clear the selected user id.
    password_entry.config(state="normal")
    confirm_password_entry.config(state="normal")
    username_entry.delete(0, "end")
    password_entry.delete(0, "end")
    confirm_password_entry.delete(0, "end")
    contact_entry.delete(0, "end")
    role_var.set("Select Role")
    selected_user_id.set("")


def load_user_by_id(cursor, user_id, selected_user_id, username_entry, password_entry, confirm_password_entry, role_var, contact_entry):
    # Load the selected user's details into the form for editing.
    user = user_database.get_user_by_id(cursor, user_id)
    if not user:
        return

    selected_user_id.set(user[0])
    password_entry.config(state="normal")
    confirm_password_entry.config(state="normal")
    username_entry.delete(0, "end")
    username_entry.insert(0, user[1])
    password_entry.delete(0, "end")
    confirm_password_entry.delete(0, "end")
    password_entry.config(state="disabled")
    confirm_password_entry.config(state="disabled")
    role_var.set(user[3])
    contact_entry.delete(0, "end")
    contact_entry.insert(0, user[5])


def create_user(conn, cursor, username_entry, password_entry, confirm_password_entry, role_var, contact_entry, selected_user_id, refresh_callback):
    # Validate the form and create a new user account.
    parent = get_popup_parent(username_entry)
    username = username_entry.get().strip()
    password = password_entry.get()
    confirm_password = confirm_password_entry.get()
    role = role_var.get()
    contact_number = contact_entry.get().strip()

    normalized_contact = validate_user_form(parent, username, password, confirm_password, role, contact_number, require_password=True)
    if not normalized_contact:
        return

    # Stop duplicate usernames before trying to insert the record.
    if user_database.username_exists(cursor, username):
        show_user_error(parent, "Error", "Username already exists. Please use a different username.")
        return

    # Save the new user and refresh the visible list.
    try:
        user_database.create_user_record(conn, cursor, username, password, role, DEFAULT_SECURITY_QUESTION, normalized_contact)
        refresh_callback()
        clear_user_form(username_entry, password_entry, confirm_password_entry, role_var, contact_entry, selected_user_id)
        show_user_success(parent, "Success", "User created successfully!")
    except sqlite3.IntegrityError:
        show_user_error(parent, "Error", "Username already exists.")


def update_user(conn, cursor, selected_user_id, username_entry, password_entry, confirm_password_entry, role_var, contact_entry, refresh_callback):
    # Validate the form and update selected user details without changing the password.
    parent = get_popup_parent(username_entry)
    if not selected_user_id.get():
        show_user_error(parent, "Error", "Select a user to update.")
        return

    username = username_entry.get().strip()
    role = role_var.get()
    contact_number = contact_entry.get().strip()

    normalized_contact = validate_user_form(parent, username, "", "", role, contact_number, require_password=False)
    if not normalized_contact:
        return

    # Prevent updates from reusing another account's username.
    if user_database.username_exists(cursor, username, selected_user_id.get()):
        show_user_error(parent, "Error", "Username already exists. Please use a different username.")
        return

    existing_user = user_database.get_user_by_id(cursor, selected_user_id.get())
    security_question = existing_user[4] if existing_user and existing_user[4] else DEFAULT_SECURITY_QUESTION

    # Save only account information; password changes use the Change Password form.
    try:
        user_database.update_user_record_without_password(conn, cursor, selected_user_id.get(), username, role, security_question, normalized_contact)
        refresh_callback()
        clear_user_form(username_entry, password_entry, confirm_password_entry, role_var, contact_entry, selected_user_id)
        show_user_success(parent, "Success", "User information updated successfully!")
    except sqlite3.IntegrityError:
        show_user_error(parent, "Error", "Username already exists.")


def delete_user_by_id(conn, cursor, user_id, selected_user_id, username_entry, password_entry, confirm_password_entry, role_var, contact_entry, refresh_callback):
    # Confirm and delete a user by id.
    parent = get_popup_parent(username_entry)
    if not ask_user_confirmation(parent, "Confirm Delete", "Delete this user?"):
        return

    user_database.delete_user_record(conn, cursor, user_id)
    refresh_callback()
    # Clear the form when the deleted user was selected.
    if str(selected_user_id.get()) == str(user_id):
        clear_user_form(username_entry, password_entry, confirm_password_entry, role_var, contact_entry, selected_user_id)
    show_user_success(parent, "Success", "User deleted successfully!")


def delete_selected_user(conn, cursor, selected_user_id, username_entry, password_entry, confirm_password_entry, role_var, contact_entry, refresh_callback):
    # Delete the user currently loaded in the form.
    parent = get_popup_parent(username_entry)
    if not selected_user_id.get():
        show_user_error(parent, "Error", "Select a user to delete.")
        return

    delete_user_by_id(
        conn,
        cursor,
        selected_user_id.get(),
        selected_user_id,
        username_entry,
        password_entry,
        confirm_password_entry,
        role_var,
        contact_entry,
        refresh_callback
    )


def open_change_password_form(conn, cursor, parent, selected_user_id):
    # Open a modal form for changing the selected user's password.
    if not selected_user_id.get():
        show_user_error(parent, "Error", "Select a user first before changing password.")
        return

    user = user_database.get_user_by_id(cursor, selected_user_id.get())
    if not user:
        show_user_error(parent, "Error", "Selected user was not found.")
        return

    popup = tk.Toplevel(parent)
    popup.title("Change Password")
    popup.transient(parent)
    popup.grab_set()
    popup.configure(bg="#fef3c7")
    popup.resizable(False, False)

    # Build the change-password form fields.
    content = tk.Frame(popup, bg="#fef3c7", padx=34, pady=28)
    content.pack(fill="both", expand=True)

    tk.Label(content, text="Change Password", bg="#fef3c7", fg=PRIMARY_BLUE, font=("Arial", 22, "bold")).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 18))
    tk.Label(content, text=f"User: {user[1]}", bg="#fef3c7", fg="#111827", font=("Arial", 14, "bold")).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0, 16))

    tk.Label(content, text="New Password", bg="#fef3c7", fg="#111827", font=("Arial", 13, "bold")).grid(row=2, column=0, sticky="w", pady=8)
    new_password_entry = tk.Entry(content, show="*", font=("Arial", 13), width=24, bd=1, relief="solid")
    new_password_entry.grid(row=2, column=1, sticky="ew", pady=8, padx=(12, 0), ipady=3)

    tk.Label(content, text="Confirm Password", bg="#fef3c7", fg="#111827", font=("Arial", 13, "bold")).grid(row=3, column=0, sticky="w", pady=8)
    confirm_entry = tk.Entry(content, show="*", font=("Arial", 13), width=24, bd=1, relief="solid")
    confirm_entry.grid(row=3, column=1, sticky="ew", pady=8, padx=(12, 0), ipady=3)

    show_password_var = tk.BooleanVar(value=False)

    def toggle_password_visibility():
        # Toggle both password entries between hidden and visible text.
        visible = "" if show_password_var.get() else "*"
        new_password_entry.config(show=visible)
        confirm_entry.config(show=visible)

    tk.Checkbutton(
        content,
        text="See Password",
        variable=show_password_var,
        command=toggle_password_visibility,
        bg="#fef3c7",
        fg="#111827",
        activebackground="#fef3c7",
        font=("Arial", 12, "bold")
    ).grid(row=4, column=1, sticky="w", padx=(12, 0), pady=(2, 8))

    button_frame = tk.Frame(content, bg="#fef3c7")
    button_frame.grid(row=5, column=0, columnspan=2, pady=(14, 0))

    def submit():
        # Validate and save the new password.
        new_password = new_password_entry.get()
        confirm_password = confirm_entry.get()

        if not new_password or not confirm_password:
            show_user_error(popup, "Error", "New Password and Confirm Password are required.")
            return
        if len(new_password) < 4:
            show_user_error(popup, "Error", "Password too weak.")
            return
        if new_password != confirm_password:
            show_user_error(popup, "Error", "Confirm password is incorrect.")
            return

        user_database.update_user_password(conn, cursor, selected_user_id.get(), new_password)
        popup.destroy()
        show_user_success(parent, "Success", "Password changed successfully!")

    # Build password form action buttons and keyboard shortcuts.
    tk.Button(button_frame, text="Save", command=submit, bg=SAVE_GREEN, fg="white", font=("Arial", 13, "bold"), width=12, pady=7, relief="solid", bd=2).pack(side="left", padx=8)
    tk.Button(button_frame, text="Cancel", command=popup.destroy, bg=CANCEL_RED, fg="white", font=("Arial", 13, "bold"), width=12, pady=7, relief="solid", bd=2).pack(side="left", padx=8)

    content.columnconfigure(1, weight=1)
    new_password_entry.focus_set()
    popup.bind("<Return>", lambda _event: submit())
    popup.bind("<Escape>", lambda _event: popup.destroy())
    center_window(popup, 520, 330, parent)
    parent.wait_window(popup)


def go_back_to_dashboard(root, conn):
    # Close the user database connection and return to the main dashboard.
    conn.close()
    from main_dashboard.main_gui import open_main
    open_main(root)
