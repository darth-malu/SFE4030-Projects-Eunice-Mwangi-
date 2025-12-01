from sys import argv as ARGV, exit as EXIT
from os import makedirs, path

from ghost_workers.worker import Worker

# import Worker.Worker as Worker

from PySide6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QWidget,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QLabel,
    QLineEdit,
    QFileDialog,
    QProgressBar,
)

from PySide6.QtGui import QPalette, QColor

from PySide6.QtCore import (
    Qt,
    QThreadPool,
    QTimer,
)


class MainApp(QMainWindow):
    def __init__(self):
        # initialise QMainWindow obj
        super().__init__()

        self.main_ui()
        self.main_logic()

        # self.setIcon()

        self.apply_dark_palette()

        self.show()

    def toggle_controls(self, enable: bool) -> None:
        """Helper to enable/disable main UI elements."""
        self.url_input.setEnabled(enable)
        self.file_choose_btn.setEnabled(enable)

    def main_ui(self):
        self.setWindowTitle("youtubr")
        # self.setGeometry(500, 400, 800, 500) #x, y, width, height
        self.placeholder = "Enter YouTube Link       "
        # self.setWindowFlags(self.windowFlags() | Qt.WindowStaysOnTopHint)
        # self.resize(300, 200)
        # self.setMinimumSize(350, 100)
        self.setFixedSize(350, 100)

        self.url_input = QLineEdit()
        self.url_input.setClearButtonEnabled(True)  # TODO: set red color
        self.url_input.setPlaceholderText(self.placeholder)
        self.url_input.setStyleSheet(
            """
            QLineEdit {
                border: 1px solid #4CAF50;
                border-radius: 6px;
                padding: 7px 8px 7px 8x;
                font-size: 14px;
                color: white;
            }

            QLineEdit:focus {
                border: 0px;
            }

            QLineEdit::placeholder {
                color: #999;
                font-style: italic;
            }
        """
        )

        # QStyle
        """
        self.file_choose_btn = QPushButton()
        icon = self.file_choose_btn.style().standardIcon(QStyle.SP_DirIcon)
        self.file_choose_btn.setIcon(icon)
        self.file_choose_btn.setIconSize(QSize(42, 42))
        """
        self.file_choose_btn = QPushButton("📂")  # 
        self.file_choose_btn.setStyleSheet(
            """
             QPushButton {
                 /* background-color: red; */
                 /*color: #6BBF59;*/
                 /*border-radius: 16px; Half of width/height */
                 font-size: 28px;
                 margin: 0px 1px 0px 6px;
                 padding-right: 0px;
                 border: 0px
             }
            /*
             QPushButton:hover {
                 background-color: darkred;
                 color: cyan;
             }
            */
             """
        )

        # Download Btn + input URL combo (QHBoxLayout + QWidget)
        button_url_combo_layout = QHBoxLayout()
        button_url_combo_layout.addWidget(self.url_input)
        button_url_combo_layout.addWidget(self.file_choose_btn)
        button_url_combo_widget = QWidget()
        button_url_combo_widget.setLayout(button_url_combo_layout)

        # Download path label - Below button_url_combo_widget
        self.download_path_label = QLabel(f"**{self.formatted_dwn_path()}**")
        self.download_path_label.setTextFormat(Qt.MarkdownText)
        self.download_path_label.setAlignment(
            Qt.AlignRight
        )  # (Qt.AlignCenter | Qt.AlignTop)
        self.download_path_label.setContentsMargins(0, 7, 8, 0)
        self.download_path_label.setStyleSheet(
            "color: #D6D5B3;"
        )  # #3CDBD3 187795 357266 B7B7B7

        # PROGRESS BAR 🔋
        self.progress_bar = QProgressBar()
        self.progress_bar.setAlignment(Qt.AlignCenter)
        self.progress_bar.hide()  # start hidden show after download starts
        self.progress_bar.setRange(0, 100)  # 0.1% steps

        # PROGRESS BAR 🔋 plus download location 📁
        self.bar_download_layout = QHBoxLayout()
        self.bar_download_layout.addWidget(self.progress_bar)
        self.bar_download_layout.addWidget(self.download_path_label)
        self.bar_download_widget = QWidget()
        self.bar_download_widget.setLayout(self.bar_download_layout)

        # Main Layout + CentralWidget
        layout = QVBoxLayout()
        layout.addWidget(button_url_combo_widget)
        layout.addWidget(self.bar_download_widget)
        # layout.addStretch()
        # layout.setContentsMargins(0, 0, 0, 0)
        # layout.setSpacing(0)

        central_widget = QWidget()
        central_widget.setLayout(layout)

        self.setCentralWidget(central_widget)

    def main_logic(self):
        # Define ThreadPool
        self.current_download_folder = self.default_download_path()
        self.url_input.returnPressed.connect(self.url_download_on_return)  # worker init
        self.file_choose_btn.clicked.connect(self.file_chooser)
        self.threadpool = QThreadPool()  # HACK scales to users Threads

    def default_download_path(self) -> str:
        return path.expanduser("~/Videos/ytbr")

    def formatted_dwn_path(self) -> str:
        display_path = self.default_download_path().replace(path.expanduser("~"), "~")
        return display_path

    def worker_init(self, url: str) -> None:
        worker = Worker(url, self.current_download_folder)  # HACK !null input

        self.toggle_controls(False)  # HACK off when downloads start

        worker.worker_signals.progress.connect(self.progress_bar.setValue)
        self.url_input.clear()  # HACK clear input once progress starrtss
        self.progress_bar.show()
        worker.worker_signals.finished.connect(lambda: self.progress_bar.hide())
        worker.worker_signals.finished.connect(lambda: self.progress_bar.setValue(0))
        worker.worker_signals.finished.connect(lambda: self.toggle_controls(True))

        def update_placeholder(text: str):
            self.url_input.setPlaceholderText(text)
            # QTimer.singleShot(
            #     1500, lambda: self.url_input.setPlaceholderText(self.placeholder)
            # )
            # This prevents intermediate messages ("Downloading video...") from resetting the placeholder.
            if text.startswith("Downloaded"):
                QTimer.singleShot(
                    3500, lambda: self.url_input.setPlaceholderText(self.placeholder)
                )

        def update_placeholder_error(error: str):
            self.url_input.setPlaceholderText(f"❌ {error}")
            print(f"ERROR SIGNAL RECEIVED: {error}")
            self.progress_bar.hide()
            self.toggle_controls(True)  # HACK off when downloads start
            QTimer.singleShot(
                2500, lambda: self.url_input.setPlaceholderText(self.placeholder)
            )

        worker.worker_signals.message.connect(update_placeholder)
        worker.worker_signals.error.connect(update_placeholder_error)

        self.threadpool.start(worker)

    def url_download_on_return(self):
        url_text = self.url_input.text().strip()
        if not url_text:
            self.url_input.setPlaceholderText("❌ Enter url ... empty")
            QTimer.singleShot(
                2000, lambda: self.url_input.setPlaceholderText(self.placeholder)
            )
            return  # HACK stop execution of function if empty

        if not url_text.startswith("https://youtu.be/"):
            self.url_input.clear()
            self.url_input.setPlaceholderText("❌ Enter valid Youtube URL")
            QTimer.singleShot(
                2000, lambda: self.url_input.setPlaceholderText(self.placeholder)
            )
            return  # HACK stop execution if URL is invalide

        # Triggered by pressing Enter. Uses default folder. *
        folder_path = self.current_download_folder or self.default_download_path()

        # Cross-platform: ensure folder exists, create it if not
        try:
            makedirs(folder_path, exist_ok=True)
        except Exception as e:
            self.url_input.setPlaceholderText(
                f"❌ Failed to access folder {folder_path}: {e}"
            )
            return
        self.worker_init(url_text)

    def file_chooser(self):
        # Triggered by clicking the download button. Opens folder dialog.
        folder = QFileDialog.getExistingDirectory(
            self, "Select Download Folder", self.default_download_path()
        )

        if folder:
            self.current_download_folder = folder  # HACK last lesson...no coupling
            self.download_path_label.setText(
                f"{folder.replace(path.expanduser( "~"), "~")}"
            )
        else:
            self.url_input.setPlaceholderText(" No folder selected ‼️")
            QTimer.singleShot(
                1500, lambda: self.url_input.setPlaceholderText(self.placeholder)
            )

    def apply_dark_palette(self):
        # Define dark colors
        dark_palette = QPalette()
        dark_palette.setColor(
            QPalette.Window, QColor(53, 53, 53)
        )  # Main window background
        dark_palette.setColor(QPalette.WindowText, Qt.white)  # Main window text
        dark_palette.setColor(
            QPalette.Base, QColor(25, 25, 25)
        )  # Input fields, list views etc. background
        dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
        dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
        dark_palette.setColor(QPalette.ToolTipText, Qt.white)
        dark_palette.setColor(QPalette.Text, Qt.white)  # General text color
        dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))  # Button background
        dark_palette.setColor(QPalette.ButtonText, Qt.white)  # Button text
        dark_palette.setColor(QPalette.BrightText, Qt.red)
        dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
        dark_palette.setColor(
            QPalette.Highlight, QColor(42, 130, 218)
        )  # Selection color
        dark_palette.setColor(QPalette.HighlightedText, Qt.black)  # Text on selection

        # Apply the palette to the application
        QApplication.instance().setPalette(dark_palette)


def main():
    app = QApplication(ARGV)
    # app.setApplicationName("youtubr") # TODO really?
    main_window = MainApp()
    EXIT(app.exec())


if __name__ == "__main__":
    main()
