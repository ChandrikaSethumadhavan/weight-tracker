from __future__ import annotations

import sys

from PyQt6 import QtWidgets

from .config import load_config
from .database import AppRepository
from .ui.main_window import MainWindow


def main() -> None:
    config = load_config()
    repo = AppRepository(config.db_path)
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("GlowUp Weight Journey")
    window = MainWindow(config, repo)
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
