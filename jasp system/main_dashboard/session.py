current_user = {
    "id": None,
    "username": "",
    "role": "",
}


def set_current_user(user_id, username, role):
    current_user["id"] = user_id
    current_user["username"] = username or ""
    current_user["role"] = role or ""


def clear_current_user():
    set_current_user(None, "", "")


def get_current_username(default="Admin"):
    return current_user.get("username") or default
