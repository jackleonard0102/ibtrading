import tkinter as tk
from ui.dashboard import Dashboard
from components.ib_connection import connect_ib

class AutoHedgerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Auto Hedger and IV/RV Calculator")

        # Connect to IBKR
        connection_successful = connect_ib()
        
        if connection_successful:
            # Create and display the dashboard
            self.dashboard = Dashboard(self.root)
            self.dashboard.pack(fill=tk.BOTH, expand=True)
        else:
            # Display error message if connection fails
            error_label = tk.Label(self.root, text="Failed to connect to IBKR. Please check your connection and try again.", fg="red", wraplength=300)
            error_label.pack(pady=20)

if __name__ == '__main__':
    root = tk.Tk()
    app = AutoHedgerApp(root)
    root.mainloop()
