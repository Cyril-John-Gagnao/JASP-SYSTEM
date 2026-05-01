import hashlib
import os
import sqlite3


DB_NAME = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "jasp.db")


def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


def open_user_connection():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    return conn, cursor


def setup_user_database(conn, cursor):
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
    cursor.execute("""
        SELECT id, username, role, COALESCE(security_question, ''), COALESCE(contact_number, '')
        FROM users
        ORDER BY role, username
    """)
    return cursor.fetchall()


def get_user_by_id(cursor, user_id):
    cursor.execute("""
        SELECT id, username, password, role, COALESCE(security_question, ''), COALESCE(contact_number, '')
        FROM users
        WHERE id=?
    """, (user_id,))
    return cursor.fetchone()


def create_user_record(conn, cursor, username, password, role, security_question, contact_number):
    cursor.execute(
        """
        INSERT INTO users (username, password, role, security_question, contact_number)
        VALUES (?, ?, ?, ?, ?)
        """,
        (username, hash_password(password), role, security_question, contact_number)
    )
    conn.commit()


def update_user_record(conn, cursor, user_id, username, password, role, security_question, contact_number):
    cursor.execute("""
        UPDATE users
        SET username=?, password=?, role=?, security_question=?, contact_number=?
        WHERE id=?
    """, (username, hash_password(password), role, security_question, contact_number, user_id))
    conn.commit()


def update_user_record_without_password(conn, cursor, user_id, username, role, security_question, contact_number):
    cursor.execute("""
        UPDATE users
        SET username=?, role=?, security_question=?, contact_number=?
        WHERE id=?
    """, (username, role, security_question, contact_number, user_id))
    conn.commit()


def update_user_password(conn, cursor, user_id, password):
    cursor.execute(
        "UPDATE users SET password=? WHERE id=?",
        (hash_password(password), user_id)
    )
    conn.commit()


def delete_user_record(conn, cursor, user_id):
    cursor.execute("DELETE FROM users WHERE id=?", (user_id,))
    conn.commit()
