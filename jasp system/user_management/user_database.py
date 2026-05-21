import hashlib
import os
import sqlite3


# Point user management queries to the shared JASP database file.
DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")


def hash_password(password):
    # Hash passwords before saving or comparing them.
    return hashlib.sha256(password.encode()).hexdigest()


def open_user_connection():
    # Open a SQLite connection and cursor for user management queries.
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    return conn, cursor


def setup_user_database(conn, cursor):
    # Create the users table if it does not already exist.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT,
            security_question TEXT DEFAULT '',
            security_answer TEXT DEFAULT '',
            contact_number TEXT DEFAULT ''
        )
    """)
    conn.commit()

    # Backfill older user tables with account recovery and contact columns.
    cursor.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in cursor.fetchall()]
    if "security_question" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN security_question TEXT DEFAULT ''")
        conn.commit()
    if "security_answer" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN security_answer TEXT DEFAULT ''")
        conn.commit()
    if "contact_number" not in columns:
        cursor.execute("ALTER TABLE users ADD COLUMN contact_number TEXT DEFAULT ''")
        conn.commit()


def get_users(cursor):
    # Fetch all users for display in the management table.
    cursor.execute("""
        SELECT id, username, role, COALESCE(security_question, ''), COALESCE(contact_number, '')
        FROM users
        ORDER BY role, username
    """)
    return cursor.fetchall()


def get_user_by_id(cursor, user_id):
    # Fetch one user record for loading into the edit form.
    cursor.execute("""
        SELECT id, username, password, role, COALESCE(security_question, ''), COALESCE(contact_number, '')
        FROM users
        WHERE id=?
    """, (user_id,))
    return cursor.fetchone()


def username_exists(cursor, username, exclude_user_id=None):
    # Check if a username is already used, ignoring letter case.
    if exclude_user_id is None:
        cursor.execute(
            "SELECT 1 FROM users WHERE LOWER(username)=LOWER(?) LIMIT 1",
            (username,)
        )
    else:
        cursor.execute(
            "SELECT 1 FROM users WHERE LOWER(username)=LOWER(?) AND id<>? LIMIT 1",
            (username, exclude_user_id)
        )
    return cursor.fetchone() is not None


def create_user_record(conn, cursor, username, password, role, security_question, contact_number):
    # Insert a new user account with a hashed password.
    cursor.execute(
        """
        INSERT INTO users (username, password, role, security_question, contact_number)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, hash_password(password), role, security_question, contact_number)
    )
    conn.commit()


def update_user_record(conn, cursor, user_id, username, password, role, security_question, contact_number):
    # Update a user account and replace its password.
    cursor.execute("""
        UPDATE users
        SET username=?, password=?, role=?, security_question=?, contact_number=?
        WHERE id=?
    """, (username, hash_password(password), role, security_question, contact_number, user_id))
    conn.commit()


def update_user_record_without_password(conn, cursor, user_id, username, role, security_question, contact_number):
    # Update user details while keeping the existing password.
    cursor.execute("""
        UPDATE users
        SET username=?, role=?, security_question=?, contact_number=?
        WHERE id=?
    """, (username, role, security_question, contact_number, user_id))
    conn.commit()


def update_user_password(conn, cursor, user_id, password):
    # Change only the selected user's password.
    cursor.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(password), user_id)
    )
    conn.commit()


def delete_user_record(conn, cursor, user_id):
    # Delete the selected user account from the database.
    cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
