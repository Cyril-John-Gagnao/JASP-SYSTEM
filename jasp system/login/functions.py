import re
from tkinter import messagebox


def contains_malicious_input(value):
    value_lower = value.lower()
    harmful_patterns = [
        r"<\s*script",
        r"<\s*/\s*script",
        r"<\s*marquee",
        r"javascript\s*:",
        r"vbscript\s*:",
        r"on\w+\s*=",
        r"document\s*\.",
        r"window\s*\.",
        r"eval\s*\(",
        r"alert\s*\(",
        r"<\s*iframe",
        r"<\s*object",
        r"<\s*embed",
    ]
    return any(re.search(pattern, value_lower) for pattern in harmful_patterns)


def has_control_characters(value):
    return any(ord(char) < 32 for char in value)


def is_valid_username(username):
    return bool(re.fullmatch(r"[A-Za-z0-9_.@-]{3,50}", username))


def is_valid_password(password):
    if len(password) < 4 or len(password) > 128:
        return False
    if has_control_characters(password):
        return False
    return True


def is_valid_security_answer(answer):
    if len(answer) < 1 or len(answer) > 100:
        return False
    if has_control_characters(answer):
        return False
    return bool(re.fullmatch(r"[A-Za-z0-9_.@#,\- ?]+", answer))


def is_valid_contact_number(contact_number):
    cleaned = contact_number.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if cleaned.startswith("+"):
        return cleaned[1:].isdigit() and 10 <= len(cleaned[1:]) <= 15
    return cleaned.isdigit() and 10 <= len(cleaned) <= 15


def validate_common_inputs(*values, error_callback=None):
    for value in values:
        if contains_malicious_input(value) or has_control_characters(value):
            if error_callback:
                error_callback("Error", "Invalid input detected.")
            else:
                messagebox.showerror("Error", "Invalid input detected.")
            return False
    return True
