import tkinter as tk
from tkinter import ttk
import time
import threading
from components.ib_connection import get_portfolio_positions, get_market_data_for_iv, get_historical_data_for_rv
from components.auto_hedger import monitor_and_hedge
from components.iv_calculator import calculate_iv
from components.rv_calculator import calculate_realized_volatility
import matplotlib.pyplot as plt
import asyncio


class Dashboard(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)

        self.create_widgets()

    def create_widgets(self):
        # Section for Portfolio and Auto Hedger
        self.portfolio_frame = ttk.LabelFrame(self, text="Portfolio / Auto Hedger")
        self.portfolio_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")

        # Stock selection dropdown
        self.stock_label = ttk.Label(self.portfolio_frame, text="Select Stock Symbol:")
        self.stock_label.grid(row=0, column=0, padx=10, pady=10)
        self.stock_var = tk.StringVar()
        self.stock_dropdown = ttk.Combobox(self.portfolio_frame, textvariable=self.stock_var)
        self.stock_dropdown.grid(row=0, column=1, padx=10, pady=10)

        # Load portfolio positions dynamically
        self.load_stocks()

        # Target Delta input
        self.target_delta_label = ttk.Label(self.portfolio_frame, text="Target Delta:")
        self.target_delta_label.grid(row=1, column=0, padx=10, pady=10)
        self.target_delta_entry = ttk.Entry(self.portfolio_frame)
        self.target_delta_entry.grid(row=1, column=1, padx=10, pady=10)
        self.target_delta_entry.insert(0, "200")  # Default target delta

        # Max Order Quantity input
        self.max_order_qty_label = ttk.Label(self.portfolio_frame, text="Max Order Qty:")
        self.max_order_qty_label.grid(row=2, column=0, padx=10, pady=10)
        self.max_order_qty_entry = ttk.Entry(self.portfolio_frame)
        self.max_order_qty_entry.grid(row=2, column=1, padx=10, pady=10)
        self.max_order_qty_entry.insert(0, "500")  # Default max order qty

        # Button to start hedging
        self.hedge_button = ttk.Button(self.portfolio_frame, text="Run Auto-Hedger", command=self.run_auto_hedger)
        self.hedge_button.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

        # Add Stop Auto-Hedger Button
        self.stop_button = ttk.Button(self.portfolio_frame, text="Stop Auto-Hedger", command=self.stop_auto_hedger)
        self.stop_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)


        # Section for IV/RV Calculator
        self.ivrv_frame = ttk.LabelFrame(self, text="IV / RV Calculator")
        self.ivrv_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Labels for IV and RV
        self.iv_label = ttk.Label(self.ivrv_frame, text="Implied Volatility (IV):")
        self.iv_label.grid(row=0, column=0, padx=10, pady=10)
        self.iv_value = ttk.Label(self.ivrv_frame, text="Calculating...")
        self.iv_value.grid(row=0, column=1, padx=10, pady=10)

        self.rv_label = ttk.Label(self.ivrv_frame, text="Realized Volatility (RV):")
        self.rv_label.grid(row=1, column=0, padx=10, pady=10)
        self.rv_value = ttk.Label(self.ivrv_frame, text="Calculating...")
        self.rv_value.grid(row=1, column=1, padx=10, pady=10)

        # Dropdown for time window selection
        self.rv_time_var = tk.StringVar()
        self.rv_time_dropdown = ttk.Combobox(self.ivrv_frame, textvariable=self.rv_time_var)
        self.rv_time_dropdown['values'] = ['15 min', '30 min', '1 hour', '2 hours']
        self.rv_time_dropdown.grid(row=2, column=1, padx=10, pady=10)
        self.rv_time_dropdown.current(0)

        # Button to update IV and RV data
        self.update_button = ttk.Button(self.ivrv_frame, text="Update Data", command=self.update_data)
        self.update_button.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

        # Button for plotting RV graph
        self.plot_button = ttk.Button(self.ivrv_frame, text="Show RV Graph", command=self.show_rv_graph)
        self.plot_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

        # Section for Activity Logs
        self.logs_frame = ttk.LabelFrame(self, text="Activity Logs")
        self.logs_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        self.logs_text = tk.Text(self.logs_frame, height=10, width=50)
        self.logs_text.grid(row=0, column=0, padx=10, pady=10)

    def load_stocks(self):
        """
        Load portfolio positions dynamically and filter the dropdown to show only eligible stocks.
        """
        try:
            positions = get_portfolio_positions()
            eligible_symbols = set([p.contract.symbol for p in positions if p.contract.secType == 'STK'])  # Example filter: only stocks
            self.stock_dropdown['values'] = list(eligible_symbols)
            self.stock_dropdown.current(0)
        except Exception as e:
            self.stock_dropdown['values'] = ["Error fetching positions"]
            print(f"Error loading portfolio: {e}")

    def update_data(self):
        stock_symbol = self.stock_var.get()

        try:
            # Fetch IV and RV data
            stock_data, option_data = get_market_data_for_iv(stock_symbol)
            S = stock_data.marketPrice()
            K = option_data.contract.strike
            T = 30 / 365  # 30 days to expiration
            r = 0.01  # Risk-free rate
            market_price = option_data.marketPrice()

            iv = calculate_iv(S, K, T, r, market_price)
            self.iv_value.config(text=f"{iv:.4f}")

            # Fetch and calculate RV with custom time window
            selected_rv_time = self.rv_time_var.get()
            window_mapping = {'15 min': 15, '30 min': 30, '1 hour': 60, '2 hours': 120}
            window = window_mapping.get(selected_rv_time, 30)  # Default to 30 minutes

            price_data = get_historical_data_for_rv(stock_symbol)
            rv = calculate_realized_volatility(price_data, window=window)
            self.rv_value.config(text=f"{rv:.4f}")

        except Exception as e:
            self.iv_value.config(text="Error fetching IV")
            self.rv_value.config(text="Error fetching RV")
            print(f"Error: {e}")

    def run_auto_hedger(self):
        """
        Start the auto-hedger with the specified target delta and max order quantity.
        If the stock or delta changes, it restarts monitoring.
        """
        stock_symbol = self.stock_var.get()
        target_delta = float(self.target_delta_entry.get())
        max_order_qty = int(self.max_order_qty_entry.get())

        # Stop any previous hedger thread
        if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
            self.stop_auto_hedger()  # Stops current monitoring

        # Log monitoring start
        self.logs_text.insert(tk.END, f"Monitoring {stock_symbol} with target delta {target_delta}...\n")

        # Start new monitoring thread
        self.monitor_thread = threading.Thread(target=self.run_async_monitor_and_hedge, args=(stock_symbol, target_delta, max_order_qty))
        self.monitor_thread.start()

    def stop_auto_hedger(self):
        """
        Stops the auto-hedger by terminating the current monitoring thread.
        """
        if hasattr(self, 'monitor_thread') and self.monitor_thread.is_alive():
            self.logs_text.insert(tk.END, "Stopping current auto-hedger...\n")
            self.stop_event.set()  # Set an event to stop the thread
            self.monitor_thread.join(1)  # Join and stop the thread

    def run_async_monitor_and_hedge(self, stock_symbol, target_delta, max_order_qty):
        """
        Create a new asyncio event loop and run the asynchronous hedging function in it.
        Monitor for stop signals.
        """
        self.stop_event = threading.Event()  # Create stop event
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            while not self.stop_event.is_set():
                loop.run_until_complete(monitor_and_hedge(stock_symbol, target_delta, max_order_qty))
        except Exception as e:
            self.logs_text.insert(tk.END, f"Error in Auto-Hedger: {e}\n")

    def monitor_and_hedge_real_time(self, stock_symbol, target_delta, max_order_qty):
        """
        Monitor the delta in real-time and adjust as needed. Log each action.
        """
        while True:
            # Perform delta hedging and log the action
            hedge_qty = monitor_and_hedge(stock_symbol, target_delta, max_order_qty)
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            log_msg = f"{timestamp} - Adjusted delta by {hedge_qty}, Qty: {hedge_qty}\n"
            self.logs_text.insert(tk.END, log_msg)

            time.sleep(60)  # Check every minute

    def show_rv_graph(self):
        """
        Show a graph of RV over time using matplotlib.
        """
        price_data = get_historical_data_for_rv(self.stock_var.get())
        rv_values = calculate_realized_volatility(price_data, window=30)

        plt.plot(rv_values)
        plt.title("Realized Volatility over Time")
        plt.xlabel("Time")
        plt.ylabel("RV")
        plt.show()
