import tkinter as tk
from tkinter import ttk
import threading
from components.ib_connection import get_portfolio_positions
from components.auto_hedger import start_auto_hedger, stop_auto_hedger, get_hedge_log, is_hedger_running
from components.iv_calculator import get_iv, get_stock_list
from components.rv_calculator import get_latest_rv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
import webbrowser

class Dashboard(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.hedger_thread = None
        self.create_widgets()
        self.update_hedge_log()
        self.update_hedger_status()

    def create_widgets(self):
        # Portfolio Section
        self.portfolio_frame = ttk.LabelFrame(self, text="Portfolio")
        self.portfolio_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Create a treeview for portfolio display
        self.portfolio_tree = ttk.Treeview(self.portfolio_frame, columns=('Symbol', 'Position', 'Avg Cost', 'Market Price', 'Market Value', 'Unrealized PNL'), show='headings')
        self.portfolio_tree.heading('Symbol', text='Symbol')
        self.portfolio_tree.heading('Position', text='Position')
        self.portfolio_tree.heading('Avg Cost', text='Avg Cost')
        self.portfolio_tree.heading('Market Price', text='Market Price')
        self.portfolio_tree.heading('Market Value', text='Market Value')
        self.portfolio_tree.heading('Unrealized PNL', text='Unrealized PNL')
        self.portfolio_tree.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Auto Hedger Section
        self.hedger_frame = ttk.LabelFrame(self, text="Auto Hedger")
        self.hedger_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Stock selection dropdown
        self.stock_label = ttk.Label(self.hedger_frame, text="Select Stock Symbol:")
        self.stock_label.grid(row=0, column=0, padx=10, pady=10)
        self.stock_var = tk.StringVar()
        self.stock_dropdown = ttk.Combobox(self.hedger_frame, textvariable=self.stock_var)
        self.stock_dropdown.grid(row=0, column=1, padx=10, pady=10)

        # Target Delta input
        self.target_delta_label = ttk.Label(self.hedger_frame, text="Target Delta:")
        self.target_delta_label.grid(row=1, column=0, padx=10, pady=10)
        self.target_delta_entry = ttk.Entry(self.hedger_frame)
        self.target_delta_entry.grid(row=1, column=1, padx=10, pady=10)
        self.target_delta_entry.insert(0, "200")  # Default target delta

        # Delta Change Threshold input
        self.delta_change_label = ttk.Label(self.hedger_frame, text="Delta Change Threshold:")
        self.delta_change_label.grid(row=2, column=0, padx=10, pady=10)
        self.delta_change_entry = ttk.Entry(self.hedger_frame)
        self.delta_change_entry.grid(row=2, column=1, padx=10, pady=10)
        self.delta_change_entry.insert(0, "50")  # Default delta change

        # Max Order Quantity input
        self.max_order_qty_label = ttk.Label(self.hedger_frame, text="Max Order Qty:")
        self.max_order_qty_label.grid(row=3, column=0, padx=10, pady=10)
        self.max_order_qty_entry = ttk.Entry(self.hedger_frame)
        self.max_order_qty_entry.grid(row=3, column=1, padx=10, pady=10)
        self.max_order_qty_entry.insert(0, "500")  # Default max order qty

        # Button to start hedging
        self.hedge_button = ttk.Button(self.hedger_frame, text="Run Auto-Hedger", command=self.run_auto_hedger)
        self.hedge_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

        # Add Stop Auto-Hedger Button
        self.stop_button = ttk.Button(self.hedger_frame, text="Stop Auto-Hedger", command=self.stop_auto_hedger)
        self.stop_button.grid(row=5, column=0, columnspan=2, padx=10, pady=10)

        # Hedger status indicator
        self.hedger_status_label = ttk.Label(self.hedger_frame, text="Auto-Hedger Status: OFF", foreground="red")
        self.hedger_status_label.grid(row=6, column=0, columnspan=2, padx=10, pady=10)

        # Section for IV/RV Calculator
        self.ivrv_frame = ttk.LabelFrame(self, text="IV / RV Calculator")
        self.ivrv_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        # Allow multiple symbols selection
        self.symbols_label = ttk.Label(self.ivrv_frame, text="Select Symbols:")
        self.symbols_label.grid(row=0, column=0, padx=10, pady=10)
        self.symbols_var = tk.StringVar()
        self.symbols_listbox = tk.Listbox(self.ivrv_frame, listvariable=self.symbols_var, selectmode='multiple', height=5)
        self.symbols_listbox.grid(row=0, column=1, padx=10, pady=10)

        # Labels for IV and RV
        self.iv_label = ttk.Label(self.ivrv_frame, text="Implied Volatility (IV):")
        self.iv_label.grid(row=1, column=0, padx=10, pady=10)
        self.iv_value = ttk.Label(self.ivrv_frame, text="Calculating...")
        self.iv_value.grid(row=1, column=1, padx=10, pady=10)

        self.rv_label = ttk.Label(self.ivrv_frame, text="Realized Volatility (RV):")
        self.rv_label.grid(row=2, column=0, padx=10, pady=10)
        self.rv_value = ttk.Label(self.ivrv_frame, text="Calculating...")
        self.rv_value.grid(row=2, column=1, padx=10, pady=10)

        # Dropdown for time window selection
        self.rv_time_var = tk.StringVar()
        self.rv_time_dropdown = ttk.Combobox(self.ivrv_frame, textvariable=self.rv_time_var)
        self.rv_time_dropdown['values'] = ['15 min', '30 min', '1 hour', '2 hours']
        self.rv_time_dropdown.grid(row=3, column=1, padx=10, pady=10)
        self.rv_time_dropdown.current(0)

        # Button to update IV and RV data
        self.update_button = ttk.Button(self.ivrv_frame, text="Update Data", command=self.update_data)
        self.update_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

        # Section for Activity Logs
        self.logs_frame = ttk.LabelFrame(self, text="Activity Logs")
        self.logs_frame.grid(row=3, column=0, padx=10, pady=10, sticky="nsew")

        self.logs_text = tk.Text(self.logs_frame, height=10, width=50)
        self.logs_text.grid(row=0, column=0, padx=10, pady=10)

        # Add Clear Logs button
        self.clear_logs_button = ttk.Button(self.logs_frame, text="Clear Logs", command=self.clear_logs)
        self.clear_logs_button.grid(row=1, column=0, padx=10, pady=10)

        # Add contact information
        contact_label = ttk.Label(self, text="Contact: ")
        contact_label.grid(row=4, column=0, sticky="w", padx=10, pady=5)
        contact_link = ttk.Label(self, text="fazeenlancer@gmail.com", foreground="blue", cursor="hand2")
        contact_link.grid(row=4, column=0, sticky="w", padx=100, pady=5)
        contact_link.bind("<Button-1>", lambda e: self.open_email())

        # Load stocks after creating all widgets
        self.load_stocks()
        # Update portfolio display
        self.update_portfolio_display()

    def load_stocks(self):
        self.log_message("Loading stocks...")
        try:
            positions = get_portfolio_positions()
            eligible_symbols = set([p.contract.symbol for p in positions if p.contract.secType == 'STK'])
            self.stock_dropdown['values'] = list(eligible_symbols)
            if eligible_symbols:
                self.stock_dropdown.current(0)
                self.log_message(f"Loaded {len(eligible_symbols)} eligible stock positions.")
            else:
                self.log_message("No eligible stock positions found.")
        except Exception as e:
            self.log_message(f"Error fetching positions: {str(e)}")
            self.stock_dropdown['values'] = ["Error fetching positions"]

        try:
            # Load stock list for IV/RV calculator
            self.log_message("Fetching stock list for IV/RV calculator...")
            stock_list = get_stock_list()
            self.symbols_var.set(stock_list)
            self.log_message(f"Loaded {len(stock_list)} stocks for IV/RV calculator.")
        except Exception as e:
            self.log_message(f"Error loading stock list: {str(e)}")

    def update_portfolio_display(self):
        # Clear existing items
        for i in self.portfolio_tree.get_children():
            self.portfolio_tree.delete(i)

        # Fetch and display portfolio positions
        try:
            positions = get_portfolio_positions()
            for position in positions:
                if position.contract.secType == 'STK':
                    self.portfolio_tree.insert('', 'end', values=(
                        position.contract.symbol,
                        position.position,
                        f"{position.avgCost:.2f}",
                        f"{position.marketPrice:.2f}",
                        f"{position.marketValue:.2f}",
                        f"{position.unrealizedPNL:.2f}"
                    ))
        except Exception as e:
            self.log_message(f"Error updating portfolio display: {str(e)}")

        # Schedule the next update
        self.after(5000, self.update_portfolio_display)  # Update every 5 seconds

    def update_data(self):
        selected_symbols = [self.symbols_listbox.get(i) for i in self.symbols_listbox.curselection()]
        rv_time = self.rv_time_var.get()

        for symbol in selected_symbols:
            self.log_message(f"Fetching data for {symbol}...")
            try:
                iv = get_iv(symbol)
                self.iv_value.config(text=f"{iv:.2%}")

                window = self.get_window_size(rv_time)
                rv = get_latest_rv(symbol, window)
                self.rv_value.config(text=f"{rv:.2%}")

                self.log_message(f"Updated IV and RV for {symbol}")
            except Exception as e:
                self.log_message(f"Error updating data for {symbol}: {str(e)}")

    def run_auto_hedger(self):
        stock_symbol = self.stock_var.get()
        target_delta = float(self.target_delta_entry.get())
        delta_change = float(self.delta_change_entry.get())
        max_order_qty = int(self.max_order_qty_entry.get())

        self.log_message(f"Starting Auto-Hedger for {stock_symbol}...")
        self.log_message(f"Target Delta: {target_delta}, Delta Change Threshold: {delta_change}, Max Order Qty: {max_order_qty}")

        self.hedger_thread = threading.Thread(target=start_auto_hedger, 
                                              args=(stock_symbol, target_delta, delta_change, max_order_qty))
        self.hedger_thread.start()
        self.update_hedge_log()
        self.update_hedger_status()

    def stop_auto_hedger(self):
        if self.hedger_thread and self.hedger_thread.is_alive():
            stop_auto_hedger()
            self.hedger_thread.join()
            self.log_message("Auto-Hedger stopped.")
        else:
            self.log_message("Auto-Hedger is not running.")
        self.update_hedger_status()

    def update_hedger_status(self):
        if is_hedger_running():
            self.hedger_status_label.config(text="Auto-Hedger Status: ON", foreground="green")
        else:
            self.hedger_status_label.config(text="Auto-Hedger Status: OFF", foreground="red")
        self.after(1000, self.update_hedger_status)  # Update every 1 second

    def update_hedge_log(self):
        hedge_log = get_hedge_log()
        if hedge_log:
            self.logs_text.delete(1.0, tk.END)
            for log in hedge_log:
                self.log_message(log)
        self.after(1000, self.update_hedge_log)  # Update every 1 second

    def log_message(self, message):
        self.logs_text.insert(tk.END, message + "\n")
        self.logs_text.see(tk.END)  # Scroll to the bottom

    def clear_logs(self):
        self.logs_text.delete(1.0, tk.END)

    def open_email(self):
        webbrowser.open('mailto:fazeenlancer@gmail.com')

    def get_window_size(self, rv_time):
        if rv_time == '15 min':
            return 15
        elif rv_time == '30 min':
            return 30
        elif rv_time == '1 hour':
            return 60
        elif rv_time == '2 hours':
            return 120
        else:
            return 30  # default to 30 minutes

if __name__ == '__main__':
    root = tk.Tk()
    app = Dashboard(root)
    app.pack(fill=tk.BOTH, expand=True)
    root.mainloop()