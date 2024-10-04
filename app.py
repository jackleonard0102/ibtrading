import tkinter as tk
from ui.dashboard import Dashboard
from components.ib_connection import connect_ib

class AutoHedgerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Hedger and IV/RV Calculator")

        # Connect to IBKR
        connect_ib()

        # Create and display the dashboard
        self.dashboard = Dashboard(self.root)
        self.dashboard.pack(fill=tk.BOTH, expand=True)

if __name__ == '__main__':
    root = tk.Tk()
    app = AutoHedgerApp(root)
    root.mainloop()
