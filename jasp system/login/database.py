import hashlib
import os
import sqlite3

# Store the shared SQLite database path and default security question.
DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")
SECURITY_QUESTION = "What is your username?"


def hash_password(password):
    # Hash passwords and security answers before storing or comparing them.
    return hashlib.sha256(password.encode()).hexdigest()


def setup_database():
    # Open the database connection used for login table setup.
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Create the users table when the system is first initialized.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        password TEXT NOT NULL,
        role TEXT NOT NULL
    )
    """)

    # Check existing user columns for older database compatibility.
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]

    # Add missing account recovery fields for older users tables.
    if "security_question" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN security_question TEXT")
    if "security_answer" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN security_answer TEXT")
    if "contact_number" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN contact_number TEXT")

    # Create the default admin account when no admin user exists yet.
    cursor.execute("SELECT id FROM users WHERE username=?", ("admin",))
    if not cursor.fetchone():
        cursor.execute(
            """
            INSERT INTO users (username, password, role, security_question, security_answer)
            VALUES (?, ?, ?, ?, ?)
            """,
            ("admin", hash_password("admin123"), "Admin", SECURITY_QUESTION, hash_password("admin"))
        )

    # Normalize role names so login permissions match expected values.
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
    # Ensure the default admin account has a recoverable security answer.
    cursor.execute("""
        UPDATE users
        SET security_answer = ?
        WHERE username = 'admin'
        AND (security_answer IS NULL OR TRIM(security_answer) = '')
    """, (hash_password("admin"),))
    # Find users missing security answers so they can be backfilled.
    cursor.execute("""
        SELECT id, username
        FROM users
        WHERE security_answer IS NULL OR TRIM(security_answer) = ''
    """)
    users_without_answers = cursor.fetchall()
    for user_id, username in users_without_answers:
        # Backfill missing security answers with the username hash.
        cursor.execute(
            "UPDATE users SET security_answer=? WHERE id=?",
            (hash_password(username), user_id)
        )

    # Save login schema/account updates and close the connection.
    conn.commit()
    conn.close()


def get_authenticated_user(username, password):
    # Return the matching user account when username and password are valid.
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
    # Fetch the saved security question for a username.
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT security_question FROM users WHERE username=?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def get_contact_number(username):
    # Fetch the saved contact number for password recovery.
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT contact_number FROM users WHERE username=?", (username,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else None


def normalize_contact_number(contact_number):
    # Remove common formatting characters before comparing contact numbers.
    return contact_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")


def get_user_id_by_contact_number(contact_number):
    # Find a user id by matching a normalized contact number.
    entered_contact = normalize_contact_number(contact_number)
    if not entered_contact:
        return None

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, contact_number FROM users WHERE COALESCE(contact_number, '') != ''")
    users = cursor.fetchall()
    conn.close()

    for user_id, saved_contact in users:
        if normalize_contact_number(saved_contact or "") == entered_contact:
            return user_id
    return None


def reset_user_password_by_contact(contact_number, new_password):
    # Reset a password using only a matching contact number.
    user_id = get_user_id_by_contact_number(contact_number)
    if not user_id:
        return False

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(new_password), user_id)
    )
    conn.commit()
    conn.close()
    return True


def reset_user_password_with_contact(username, contact_number, new_password):
    # Reset a password after username and contact number both match.
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, contact_number FROM users WHERE username=?",
        (username,)
    )
    user = cursor.fetchone()

    if not user or not user[1]:
        # Reject reset attempts when the account or contact number is missing.
        conn.close()
        return False

    saved_contact = normalize_contact_number(user[1])
    entered_contact = normalize_contact_number(contact_number)
    if saved_contact != entered_contact:
        # Reject reset attempts when contact numbers do not match.
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
    # Reset a password after the stored security answer matches.
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, security_answer FROM users WHERE username=?",
        (username,)
    )
    user = cursor.fetchone()

    if not user or user[1] != hash_password(security_answer):
        # Reject reset attempts when the security answer is incorrect.
        conn.close()
        return False

    cursor.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(new_password), user[0])
    )
    conn.commit()
    conn.close()
    return True
