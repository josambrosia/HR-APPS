from pathlib import Path

from src.config import DB_PATH
from src.db.schema import init_db
from src.ui.app import HRApp


def main():
    init_db(DB_PATH)
    app = HRApp()
    app.mainloop()


if __name__ == "__main__":
    main()
