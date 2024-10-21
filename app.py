# app.py
import tkinter as tk
from ui.dashboard import Dashboard
from components.ib_connection import connect_ib

def main():
    root = tk.Tk()
    root.title("Auto Hedger and IV/RV Calculator")

    # Connect to IBKR
    connection_successful = connect_ib()
    if not connection_successful:
        error_label = tk.Label(root, text="Failed to connect to IBKR. Please check your connection and try again.", fg="red", wraplength=300)
        error_label.pack(pady=20)
    else:
        dashboard = Dashboard(root)
        dashboard.pack(fill=tk.BOTH, expand=True)

    root.mainloop()

if __name__ == '__main__':
    main()
