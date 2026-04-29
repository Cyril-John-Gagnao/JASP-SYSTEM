from login.database import setup_database
from login.log_gui import run_app


if __name__ == "__main__":
    setup_database()
    run_app()
