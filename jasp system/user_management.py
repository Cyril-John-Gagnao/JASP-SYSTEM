import tkinter as tk
from tkinter import messagebox, ttk
import sqlite3
import os
import hashlib

# ================= DATABASE =================
DB_NAME = os.path.join(os.path.dirname(__file__), "jasp.db")

current_user_role = "Admin"

# ================= COLORS =================
BG = "#eaf4ff"
CARD = "#ffffff"
PRIMARY = "#2563eb"
SUCCESS = "#16a34a"
WARNING = "#f59e0b"
DANGER = "#dc2626"
TEXT = "#0f172a"


# ================= HASH FUNCTION (OPTION 1 FIX) =================
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def open_user_management(root):

    # ================= CLEAR SCREEN =================
    for widget in root.winfo_children():
        widget.destroy()

    root.title("User Management")
    root.configure(bg=BG)

    # ================= ACCESS CONTROL =================
    if current_user_role != "Admin":
        messagebox.showerror("Error", "Access denied. Unauthorized action.")
        return

    # ================= DB =================
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
    """)
    conn.commit()

    selected_user_id = tk.StringVar()

    # ================= HEADER =================
    header = tk.Frame(root, bg=BG)
    header.pack(fill="x", pady=10)

    tk.Label(
        header,
        text="USER MANAGEMENT",
        font=("Arial", 22, "bold"),
        bg=BG,
        fg=PRIMARY
    ).pack()

    # ================= MAIN =================
    main = tk.Frame(root, bg=BG)
    main.pack(fill="both", expand=True, padx=20, pady=10)

    # LEFT (TABLE)
    left = tk.Frame(main, bg=CARD)
    left.pack(side="left", fill="both", expand=True, padx=10, pady=10)

    tk.Label(left, text="User List", font=("Arial", 16, "bold"),
             bg=CARD, fg=TEXT).pack(pady=10)

    listbox = tk.Listbox(left, font=("Arial", 12))
    listbox.pack(fill="both", expand=True, padx=10, pady=10)

    # RIGHT (FORM)
    right = tk.Frame(main, bg=CARD)
    right.pack(side="right", fill="y", padx=10, pady=10)

    tk.Label(right, text="User Form", font=("Arial", 16, "bold"),
             bg=CARD, fg=TEXT).pack(pady=10)

    form = tk.Frame(right, bg=CARD)
    form.pack(pady=10)

    tk.Label(form, text="Username", bg=CARD, font=("Arial", 12)).grid(row=0, column=0, sticky="w")
    username_entry = tk.Entry(form, font=("Arial", 12), width=25)
    username_entry.grid(row=0, column=1, pady=5)

    tk.Label(form, text="Password", bg=CARD, font=("Arial", 12)).grid(row=1, column=0, sticky="w")
    password_entry = tk.Entry(form, font=("Arial", 12), show="*", width=25)
    password_entry.grid(row=1, column=1, pady=5)

    tk.Label(form, text="Role", bg=CARD, font=("Arial", 12)).grid(row=2, column=0, sticky="w")
    role_var = tk.StringVar(value="Select Role")
    ttk.Combobox(form, textvariable=role_var,
                 values=["Admin", "Cashier"],
                 state="readonly",
                 font=("Arial", 11)).grid(row=2, column=1, pady=5)

    # ================= VALIDATION =================
    def validate(u, p, r):
        if not u or not p or r == "Select Role":
            messagebox.showerror("Error", "All fields are required.")
            return False
        if len(p) < 4:
            messagebox.showerror("Error", "Password too weak.")
            return False
        return True

    # ================= LOAD =================
    def refresh():
        listbox.delete(0, tk.END)
        cursor.execute("SELECT id, username, role FROM users")
        for row in cursor.fetchall():
            listbox.insert(tk.END, f"{row[0]} | {row[1]} ({row[2]})")

    def clear():
        username_entry.delete(0, tk.END)
        password_entry.delete(0, tk.END)
        role_var.set("Select Role")
        selected_user_id.set("")

    def load(event):
        if not listbox.curselection():
            return

        user_id = listbox.get(listbox.curselection()[0]).split("|")[0].strip()

        cursor.execute("SELECT * FROM users WHERE id=?", (user_id,))
        user = cursor.fetchone()

        if user:
            selected_user_id.set(user[0])
            username_entry.delete(0, tk.END)
            username_entry.insert(0, user[1])

            # ⚠️ hashed password shown but NOT reversed (security)
            password_entry.delete(0, tk.END)

            role_var.set(user[3])

    listbox.bind("<<ListboxSelect>>", load)

    # ================= CREATE (HASH FIXED) =================
    def create():
        u = username_entry.get()
        p = password_entry.get()
        r = role_var.get()

        if not validate(u, p, r):
            return

        try:
            cursor.execute(
                "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                (u, hash_password(p), r)   # ✅ FIXED
            )
            conn.commit()
            refresh()
            clear()
        except sqlite3.IntegrityError:
            messagebox.showerror("Error", "Username already exists.")

    # ================= UPDATE (HASH FIXED) =================
    def update():
        if not selected_user_id.get():
            return

        u = username_entry.get()
        p = password_entry.get()
        r = role_var.get()

        if not validate(u, p, r):
            return

        cursor.execute("""
            UPDATE users
            SET username=?, password=?, role=?
            WHERE id=?
        """, (u, hash_password(p), r, selected_user_id.get()))  # ✅ FIXED

        conn.commit()
        refresh()
        clear()

    # ================= DELETE =================
    def delete():
        if not selected_user_id.get():
            return

        if messagebox.askyesno("Confirm Delete", "Delete this user?"):
            cursor.execute("DELETE FROM users WHERE id=?", (selected_user_id.get(),))
            conn.commit()
            refresh()
            clear()

    # ================= BUTTONS =================
    btn = tk.Frame(right, bg=CARD)
    btn.pack(pady=15)

    tk.Button(btn, text="Create", command=create, bg=SUCCESS, fg="white",
              font=("Arial", 12, "bold"), width=10).grid(row=0, column=0, padx=5)

    tk.Button(btn, text="Update", command=update, bg=PRIMARY, fg="white",
              font=("Arial", 12, "bold"), width=10).grid(row=0, column=1, padx=5)

    tk.Button(btn, text="Delete", command=delete, bg=DANGER, fg="white",
              font=("Arial", 12, "bold"), width=10).grid(row=0, column=2, padx=5)

    # ================= BACK =================
    def go_back():
        conn.close()
        from main_dashboard import open_main
        open_main(root)

    tk.Button(
        right,
        text="← Back to Dashboard",
        command=go_back,
        bg=WARNING,
        fg="white",
        font=("Arial", 12, "bold"),
        pady=8
    ).pack(pady=20, fill="x")

    refresh()