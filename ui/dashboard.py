import tkinter as tk
from tkinter import ttk
from components.ib_connection import get_portfolio_positions, get_market_data_for_iv, get_historical_data_for_rv
from components.iv_calculator import calculate_iv
from components.rv_calculator import calculate_realized_volatility

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

        # Button to update IV and RV
        self.update_button = ttk.Button(self.ivrv_frame, text="Update Data", command=self.update_data)
        self.update_button.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

        # Section for Activity Logs
        self.logs_frame = ttk.LabelFrame(self, text="Activity Logs")
        self.logs_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")

        self.logs_text = tk.Text(self.logs_frame, height=10, width=50)
        self.logs_text.grid(row=0, column=0, padx=10, pady=10)

    def load_stocks(self):
        """
        Load portfolio positions dynamically and populate the dropdown
        """
        try:
            positions = get_portfolio_positions()
            symbols = set([p.contract.symbol for p in positions])
            self.stock_dropdown['values'] = list(symbols)
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

            price_data = get_historical_data_for_rv(stock_symbol)
            rv = calculate_realized_volatility(price_data, window=30)
            self.rv_value.config(text=f"{rv:.4f}")

        except Exception as e:
            self.iv_value.config(text="Error fetching IV")
            self.rv_value.config(text="Error fetching RV")
            print(f"Error fetching data: {e}")

    def run_auto_hedger(self):
        """
        Start the auto-hedger with the specified target delta and max order quantity.
        """
        stock_symbol = self.stock_var.get()
        target_delta = float(self.target_delta_entry.get())
        max_order_qty = int(self.max_order_qty_entry.get())

        # Simulate hedge execution
        self.logs_text.insert(tk.END, f"Running auto-hedger for {stock_symbol} with target delta {target_delta} and max order {max_order_qty}...\n")
        # Implement hedger logic here or call relevant functions for hedging
