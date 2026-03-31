import sqlite3
import tkinter as tk
from tkinter import messagebox
import hashlib

DB_NAME = "jasp.db"

# ---------- PASSWORD HASH ----------
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ---------- DATABASE SETUP ----------
def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    # Insert default admin if not exists
    cursor.execute("SELECT * FROM users WHERE username=?", ("admin",))
    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            ("admin", hash_password("admin123"), "admin")
        )
        conn.commit()

    conn.close()

# ---------- OPEN MAIN DASHBOARD ----------
def open_main():
    import main_dashboard
    main_dashboard.open_main()

# ---------- LOGIN FUNCTION ----------
def login():
    username = username_entry.get().strip()
    password_input = password_entry.get().strip()

    # ❗ EMPTY CHECK
    if username == "" or password_input == "":
        messagebox.showerror("Error", "Please enter both username and password")
        return

    password = hash_password(password_input)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT * FROM users WHERE username=? AND password=?",
        (username, password)
    )
    user = cursor.fetchone()
    conn.close()

    if user:
        messagebox.showinfo("Success", "Login Successful!")
        root.destroy()
        open_main()
    else:
        messagebox.showerror("Error", "Invalid Username or Password")


# ---------- REGISTER FUNCTION ----------
def register():
    username = username_entry.get().strip()
    password_input = password_entry.get().strip()
    role = "admin"

    # ❗ EMPTY CHECK
    if username == "" or password_input == "":
        messagebox.showerror("Error", "All fields are required!")
        return

    # ❗ OPTIONAL: Minimum password length
    if len(password_input) < 4:
        messagebox.showerror("Error", "Password must be at least 4 characters")
        return

    password = hash_password(password_input)

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
            (username, password, role)
        )
        conn.commit()
        messagebox.showinfo("Success", "User Registered!")
    except sqlite3.IntegrityError:
        messagebox.showerror("Error", "Username already exists")

    conn.close()

# ---------- GUI ----------
setup_database()

root = tk.Tk()
root.title("Login")
root.state("zoomed")
root.configure(bg="#1950a3")

# Center container
main_frame = tk.Frame(root, bg="#1950a3")
main_frame.pack(expand=True)

# Login Card
login_frame = tk.Frame(main_frame, bg="white", padx=50, pady=40)
login_frame.pack()

# Title
tk.Label(login_frame, text="JASP Hardware System",
         font=("Arial", 22, "bold"), bg="white", fg="#1950a3").pack(pady=(0,10))

tk.Label(login_frame, text="Login to continue",
         font=("Arial", 11), bg="white", fg="gray").pack(pady=(0,20))

# ---------- Username ----------
tk.Label(login_frame, text="Username",
         font=("Arial", 10, "bold"), bg="white").pack(anchor="w")

username_entry = tk.Entry(login_frame, width=35, font=("Arial", 11), bd=2, relief="groove")
username_entry.pack(pady=8, ipady=5)

# ---------- Password ----------
tk.Label(login_frame, text="Password",
         font=("Arial", 10, "bold"), bg="white").pack(anchor="w")

password_entry = tk.Entry(login_frame, show="*", width=35, font=("Arial", 11), bd=2, relief="groove")
password_entry.pack(pady=8, ipady=5)

# ---------- BUTTON HOVER EFFECT ----------
def on_enter(e):
    e.widget['background'] = "#218838"

def on_leave(e):
    e.widget['background'] = "#28a745"

# ---------- Login Button ----------
login_btn = tk.Button(login_frame, text="Login",
                      font=("Arial", 11, "bold"),
                      width=30, bg="#28a745", fg="white",
                      activebackground="#218838",
                      relief="flat", command=login)
login_btn.pack(pady=15, ipady=5)

login_btn.bind("<Enter>", on_enter)
login_btn.bind("<Leave>", on_leave)

# ---------- Register Button ----------
register_btn = tk.Button(login_frame, text="Register",
                         font=("Arial", 10),
                         width=30, bg="#007bff", fg="white",
                         relief="flat", command=register)
register_btn.pack(ipady=5)

# ---------- Exit Button ----------
tk.Button(root, text="Exit", command=root.destroy,
          bg="#dc3545", fg="white",
          font=("Arial", 10, "bold"),
          relief="flat").place(x=20, y=20)

root.mainloop()