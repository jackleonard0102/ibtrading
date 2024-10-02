from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout
from ui.dashboard import Dashboard

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.setWindowTitle("Auto Hedger and IV/RV Calculator")
        self.setGeometry(100, 100, 800, 600)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)

        # Add dashboard to main window
        self.dashboard = Dashboard(self)
        layout = QVBoxLayout(self.central_widget)
        layout.addWidget(self.dashboard)
