import tkinter as tk
from tkinter import ttk
import threading
from components.ib_connection import get_portfolio_positions, get_market_data_for_iv, get_historical_data_for_rv
from components.auto_hedger import start_auto_hedger, stop_auto_hedger
from components.iv_calculator import get_iv
from components.rv_calculator import calculate_realized_volatility, get_latest_rv
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

class Dashboard(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.hedger_thread = None
        self.create_widgets()

    def create_widgets(self):
        # Portfolio Section - Auto Hedger
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

        # Delta Change Threshold input
        self.delta_change_label = ttk.Label(self.portfolio_frame, text="Delta Change Threshold:")
        self.delta_change_label.grid(row=2, column=0, padx=10, pady=10)
        self.delta_change_entry = ttk.Entry(self.portfolio_frame)
        self.delta_change_entry.grid(row=2, column=1, padx=10, pady=10)
        self.delta_change_entry.insert(0, "50")  # Default delta change

        # Max Order Quantity input
        self.max_order_qty_label = ttk.Label(self.portfolio_frame, text="Max Order Qty:")
        self.max_order_qty_label.grid(row=3, column=0, padx=10, pady=10)
        self.max_order_qty_entry = ttk.Entry(self.portfolio_frame)
        self.max_order_qty_entry.grid(row=3, column=1, padx=10, pady=10)
        self.max_order_qty_entry.insert(0, "500")  # Default max order qty

        # Button to start hedging
        self.hedge_button = ttk.Button(self.portfolio_frame, text="Run Auto-Hedger", command=self.run_auto_hedger)
        self.hedge_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

        # Add Stop Auto-Hedger Button
        self.stop_button = ttk.Button(self.portfolio_frame, text="Stop Auto-Hedger", command=self.stop_auto_hedger)
        self.stop_button.grid(row=5, column=0, columnspan=2, padx=10, pady=10)

        # Hedger status indicator
        self.hedger_status_label = ttk.Label(self.portfolio_frame, text="Auto-Hedger Status: OFF", foreground="red")
        self.hedger_status_label.grid(row=6, column=0, columnspan=2, padx=10, pady=10)

        # Section for IV/RV Calculator
        self.ivrv_frame = ttk.LabelFrame(self, text="IV / RV Calculator")
        self.ivrv_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Allow multiple symbols selection
        self.symbols_label = ttk.Label(self.ivrv_frame, text="Select Symbols:")
        self.symbols_label.grid(row=0, column=0, padx=10, pady=10)
        self.symbols_var = tk.StringVar(value=["AAPL", "AMZN", "NVDA", "QQQ"])
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

        # Button for plotting RV graph
        self.plot_button = ttk.Button(self.ivrv_frame, text="Show RV Graph", command=self.show_rv_graph)
        self.plot_button.grid(row=5, column=0, columnspan=2, padx=10, pady=10)

        # Section for Activity Logs
        self.logs_frame = ttk.LabelFrame(self, text="Activity Logs")
        self.logs_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        self.logs_text = tk.Text(self.logs_frame, height=10, width=50)
        self.logs_text.grid(row=0, column=0, padx=10, pady=10)

    def load_stocks(self):
        try:
            positions = get_portfolio_positions()
            eligible_symbols = set([p.contract.symbol for p in positions if p.contract.secType == 'STK'])
            self.stock_dropdown['values'] = list(eligible_symbols)
            self.stock_dropdown.current(0)
        except Exception as e:
            self.stock_dropdown['values'] = ["Error fetching positions"]
            print(f"Error loading portfolio: {e}")

    def update_data(self):
        selected_symbols = [self.symbols_listbox.get(i) for i in self.symbols_listbox.curselection()]
        rv_time = self.rv_time_var.get()

        for symbol in selected_symbols:
            self.logs_text.insert(tk.END, f"Fetching data for {symbol}...\n")
            try:
                stock_data, option_data = get_market_data_for_iv(symbol)
                iv = get_iv(stock_data, option_data)
                self.iv_value.config(text=f"{iv:.2%}")

                price_data = get_historical_data_for_rv(symbol)
                window = self.get_window_size(rv_time)
                rv = get_latest_rv(price_data, window)
                self.rv_value.config(text=f"{rv:.2%}")

                self.logs_text.insert(tk.END, f"Updated IV and RV for {symbol}\n")
            except Exception as e:
                self.logs_text.insert(tk.END, f"Error updating data for {symbol}: {str(e)}\n")

    def run_auto_hedger(self):
        stock_symbol = self.stock_var.get()
        target_delta = float(self.target_delta_entry.get())
        delta_change = float(self.delta_change_entry.get())
        max_order_qty = int(self.max_order_qty_entry.get())

        self.hedger_status_label.config(text="Auto-Hedger Status: ON", foreground="green")
        self.logs_text.insert(tk.END, f"Starting Auto-Hedger for {stock_symbol}...\n")

        self.hedger_thread = threading.Thread(target=start_auto_hedger, 
                                              args=(stock_symbol, target_delta, delta_change, max_order_qty))
        self.hedger_thread.start()

    def stop_auto_hedger(self):
        if self.hedger_thread and self.hedger_thread.is_alive():
            stop_auto_hedger()
            self.hedger_thread.join()
            self.hedger_status_label.config(text="Auto-Hedger Status: OFF", foreground="red")
            self.logs_text.insert(tk.END, "Auto-Hedger stopped.\n")
        else:
            self.logs_text.insert(tk.END, "Auto-Hedger is not running.\n")

    def show_rv_graph(self):
        selected_symbols = [self.symbols_listbox.get(i) for i in self.symbols_listbox.curselection()]
        if not selected_symbols:
            self.logs_text.insert(tk.END, "Please select at least one symbol for the RV graph.\n")
            return

        rv_time = self.rv_time_var.get()
        window = self.get_window_size(rv_time)

        fig, ax = plt.subplots(figsize=(10, 6))

        for symbol in selected_symbols:
            try:
                price_data = get_historical_data_for_rv(symbol)
                rv_values = calculate_realized_volatility(price_data, window)
                ax.plot(rv_values, label=symbol)
            except Exception as e:
                self.logs_text.insert(tk.END, f"Error calculating RV for {symbol}: {str(e)}\n")

        ax.set_title("Realized Volatility over Time")
        ax.set_xlabel("Time")
        ax.set_ylabel("RV")
        ax.legend()

        # Create a new top-level window for the graph
        graph_window = tk.Toplevel(self)
        graph_window.title("Realized Volatility Graph")

        canvas = FigureCanvasTkAgg(fig, master=graph_window)
        canvas.draw()
        canvas.get_tk_widget().pack()

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
