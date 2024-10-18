# app.py
import tkinter as tk
from ui.dashboard import Dashboard
from components.ib_connection import connect_ib, ib  # Import ib here

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
            # Start the IB event loop in the main thread
            self.update_ib_loop()
        else:
            # Display error message if connection fails
            error_label = tk.Label(self.root, text="Failed to connect to IBKR. Please check your connection and try again.", fg="red", wraplength=300)
            error_label.pack(pady=20)

    def update_ib_loop(self):
        # Process any pending IB events
        ib.sleep(0)
        self.root.after(100, self.update_ib_loop)

if __name__ == '__main__':
    root = tk.Tk()
    app = AutoHedgerApp(root)
    root.mainloop()
