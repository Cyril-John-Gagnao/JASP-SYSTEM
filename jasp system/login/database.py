import hashlib
import os
import sqlite3

DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")
SECURITY_QUESTION = "What is your username?"


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def setup_database():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]

    if "security_question" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN security_question TEXT")
    if "security_answer" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN security_answer TEXT")
    if "contact_number" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN contact_number TEXT")

    cursor.execute("SELECT id FROM users WHERE username=?", ("admin",))
    if not cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO users (username, password, role, security_question, security_answer)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("admin", hash_password("admin123"), "Admin", SECURITY_QUESTION, hash_password("admin"))
        )

    cursor.execute("""
        UPDATE users
        SET role = 'Admin'
        WHERE LOWER(role) = 'admin'
    """)
    cursor.execute("""
        UPDATE users
        SET role = 'Cashier'
        WHERE LOWER(role) = 'cashier'
    """)
    cursor.execute("""
        UPDATE users
        SET security_question = ?
        WHERE security_question IS NULL OR TRIM(security_question) = ''
    """, (SECURITY_QUESTION,))
    cursor.execute("""
        UPDATE users
        SET security_answer = ?
        WHERE username = 'admin'
          AND (security_answer IS NULL OR TRIM(security_answer) = '')
    """, (hash_password("admin"),))
    cursor.execute("""
        SELECT id, username
        FROM users
        WHERE security_answer IS NULL OR TRIM(security_answer) = ''
    """)
    users_without_answers = cursor.fetchall()
    for user_id, username in users_without_answers:
        cursor.execute(
            "UPDATE users SET security_answer=? WHERE id=?",
            (hash_password(username), user_id)
        )

    conn.commit()
    conn.close()


def get_authenticated_user(username, password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, username, role
        FROM users
        WHERE username=? AND password=?
        """,
        (username, hash_password(password))
    )
    user = cursor.fetchone()
    conn.close()
    return user


def get_security_question(username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT security_question FROM users WHERE username=?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_contact_number(username):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT contact_number FROM users WHERE username=?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def normalize_contact_number(contact_number):
    return contact_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")


def reset_user_password_with_contact(username, contact_number, new_password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, contact_number FROM users WHERE username=?",
        (username,)
    )
    user = cursor.fetchone()

    if not user or not user[1]:
        conn.close()
        return False

    saved_contact = normalize_contact_number(user[1])
    entered_contact = normalize_contact_number(contact_number)
    if saved_contact != entered_contact:
        conn.close()
        return False

    cursor.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(new_password), user[0])
    )
    conn.commit()
    conn.close()
    return True


def reset_user_password(username, security_answer, new_password):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, security_answer FROM users WHERE username=?",
        (username,)
    )
    user = cursor.fetchone()

    if not user or user[1] != hash_password(security_answer):
        conn.close()
        return False

    cursor.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(new_password), user[0])
    )
    conn.commit()
    conn.close()
    return True
