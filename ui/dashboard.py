import tkinter as tk
from tkinter import ttk
import threading
from components.ib_connection import (
    get_portfolio_positions,
    define_stock_contract,
    fetch_market_data_for_stock,
    get_delta,
    ib
)
from components.auto_hedger import (
    start_auto_hedger,
    stop_auto_hedger,
    get_hedge_log,
    is_hedger_running
)
from components.iv_calculator import get_iv, get_stock_list
from components.rv_calculator import get_latest_rv
import webbrowser
from ib_insync import Stock, Option


class Dashboard(tk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.hedger_thread = None
        self.create_widgets()
        self.update_hedge_log()
        self.update_hedger_status()

    def create_widgets(self):
        # Set window size
        self.master.geometry("1645x940")

        # Portfolio Section
        self.portfolio_frame = ttk.LabelFrame(self, text="Portfolio")
        self.portfolio_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky="nsew")

        # Create a treeview for portfolio display (including options)
        self.portfolio_tree = ttk.Treeview(
            self.portfolio_frame,
            columns=(
                'Symbol', 'Type', 'Position', 'Delta', 'Avg Cost', 'Market Price', 'Market Value', 'Unrealized PNL'
            ),
            show='headings'
        )
        self.portfolio_tree.heading('Symbol', text='Symbol')
        self.portfolio_tree.heading('Type', text='Type')  # Stock or Option
        self.portfolio_tree.heading('Position', text='Position')
        self.portfolio_tree.heading('Delta', text='Delta')  # New Delta Column
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

        # Delta for selected stock
        self.delta_label = ttk.Label(self.hedger_frame, text="Current Delta:")
        self.delta_label.grid(row=1, column=0, padx=10, pady=10)
        self.delta_value = ttk.Label(self.hedger_frame, text="Loading...")
        self.delta_value.grid(row=1, column=1, padx=10, pady=10)

        # Target Delta input
        self.target_delta_label = ttk.Label(self.hedger_frame, text="Target Delta:")
        self.target_delta_label.grid(row=2, column=0, padx=10, pady=10)
        self.target_delta_entry = ttk.Entry(self.hedger_frame)
        self.target_delta_entry.grid(row=2, column=1, padx=10, pady=10)
        self.target_delta_entry.insert(0, "200")  # Default target delta

        # Delta Change Threshold input
        self.delta_change_label = ttk.Label(self.hedger_frame, text="Delta Change Threshold:")
        self.delta_change_label.grid(row=3, column=0, padx=10, pady=10)
        self.delta_change_entry = ttk.Entry(self.hedger_frame)
        self.delta_change_entry.grid(row=3, column=1, padx=10, pady=10)
        self.delta_change_entry.insert(0, "50")  # Default delta change

        # Max Order Quantity input
        self.max_order_qty_label = ttk.Label(self.hedger_frame, text="Max Order Qty:")
        self.max_order_qty_label.grid(row=4, column=0, padx=10, pady=10)
        self.max_order_qty_entry = ttk.Entry(self.hedger_frame)
        self.max_order_qty_entry.grid(row=4, column=1, padx=10, pady=10)
        self.max_order_qty_entry.insert(0, "500")  # Default max order qty

        # Button to start hedging
        self.hedge_button = ttk.Button(self.hedger_frame, text="Run Auto-Hedger", command=self.run_auto_hedger)
        self.hedge_button.grid(row=5, column=0, columnspan=2, padx=10, pady=10)

        # Stop Auto-Hedger Button
        self.stop_button = ttk.Button(self.hedger_frame, text="Stop Auto-Hedger", command=self.stop_auto_hedger)
        self.stop_button.grid(row=6, column=0, columnspan=2, padx=10, pady=10)

        # Hedger status indicator
        self.hedger_status_label = ttk.Label(self.hedger_frame, text="Auto-Hedger Status: OFF", foreground="red")
        self.hedger_status_label.grid(row=7, column=0, columnspan=2, padx=10, pady=10)

        # IV/RV Calculator Section
        self.ivrv_frame = ttk.LabelFrame(self, text="IV / RV Calculator")
        self.ivrv_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        # Dropdown for symbol selection
        self.symbol_var = tk.StringVar()
        self.symbol_dropdown = ttk.Combobox(self.ivrv_frame, textvariable=self.symbol_var)
        self.symbol_dropdown['values'] = get_stock_list()
        self.symbol_dropdown.grid(row=0, column=1, padx=10, pady=10)
        
        # Labels for IV and RV
        self.iv_label = ttk.Label(self.ivrv_frame, text="Implied Volatility (IV):")
        self.iv_label.grid(row=1, column=0, padx=10, pady=10)
        self.iv_value = ttk.Label(self.ivrv_frame, text="Calculating...")
        self.iv_value.grid(row=1, column=1, padx=10, pady=10)

        self.rv_label = ttk.Label(self.ivrv_frame, text="Realized Volatility (RV):")
        self.rv_label.grid(row=2, column=0, padx=10, pady=10)
        self.rv_value = ttk.Label(self.ivrv_frame, text="Calculating...")
        self.rv_value.grid(row=2, column=1, padx=10, pady=10)

        # Dropdown for time window
        self.rv_time_var = tk.StringVar()
        self.rv_time_dropdown = ttk.Combobox(self.ivrv_frame, textvariable=self.rv_time_var)
        self.rv_time_dropdown['values'] = ['15 min', '30 min', '1 hour', '2 hours']
        self.rv_time_dropdown.grid(row=3, column=1, padx=10, pady=10)
        self.rv_time_dropdown.current(0)

        # Button to update IV/RV data
        self.update_button = ttk.Button(self.ivrv_frame, text="Update Data", command=self.update_data)
        self.update_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

        # Activity Logs Section
        self.logs_frame = ttk.LabelFrame(self, text="Activity Logs", width=400)
        self.logs_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        self.logs_text = tk.Text(self.logs_frame, height=10, width=50)
        self.logs_text.grid(row=0, column=0, padx=10, pady=10)

        # Clear Logs button
        self.clear_logs_button = ttk.Button(self.logs_frame, text="Clear Logs", command=self.clear_logs)
        self.clear_logs_button.grid(row=1, column=0, padx=10, pady=10)

        # Contact Info Section
        self.contact_frame = ttk.LabelFrame(self, text="Contact Info", width=400)
        self.contact_frame.grid(row=2, column=1, padx=10, pady=10, sticky="nsew")

        # Contact Information
        self.contact_label = ttk.Label(self.contact_frame, text="It's not safe to share detailed information in freelancer, even calling is disabled.")
        self.contact_label.grid(row=0, column=0, padx=10, pady=10)
        self.email_label = ttk.Label(self.contact_frame, text="fazeenlancer@gmail.com", foreground="blue", cursor="hand2")
        self.email_label.grid(row=1, column=0, padx=10, pady=5)
        self.email_label.bind("<Button-1>", lambda e: self.open_email())
        self.contact_label.grid(row=2, column=0, padx=10, pady=5)

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
            self.symbol_dropdown['values'] = list(eligible_symbols)
            if eligible_symbols:
                self.stock_dropdown.current(0)
                self.symbol_dropdown.current(0)
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
            self.symbol_var.set(stock_list)
            self.log_message(f"Loaded {len(stock_list)} stocks for IV/RV calculator.")
        except Exception as e:
            self.log_message(f"Error loading stock list: {str(e)}")

    def update_portfolio_display(self):
        """
        Update portfolio display by fetching positions from IBKR and qualifying contracts properly.
        """
        for i in self.portfolio_tree.get_children():
            self.portfolio_tree.delete(i)

        # Fetch and display portfolio positions
        try:
            positions = get_portfolio_positions()
            for position in positions:
                contract = position.contract

                # Define and qualify the contract properly
                if contract.secType == 'STK':
                    contract = define_stock_contract(contract.symbol)
                elif contract.secType == 'OPT':
                    # Reconstruct the option contract with necessary fields
                    contract = Option(
                        symbol=contract.symbol,
                        lastTradeDateOrContractMonth=contract.lastTradeDateOrContractMonth,
                        strike=contract.strike,
                        right=contract.right,
                        multiplier=contract.multiplier,
                        exchange='SMART',
                        currency='USD'
                    )
                    ib.qualifyContracts(contract)
                else:
                    continue  # Skip if not stock or option

                # Fetch market data
                market_data = fetch_market_data_for_stock(contract)
                delta = get_delta(position)

                if market_data:
                    market_price = market_data.last or market_data.close or market_data.bid or market_data.ask or 0
                    market_value = position.position * market_price
                    unrealized_pnl = market_value - (position.position * position.avgCost)

                    self.portfolio_tree.insert('', 'end', values=(
                        contract.symbol,
                        contract.secType,  # Show STK or OPT
                        position.position,
                        f"{delta:.2f}",  # Show delta
                        f"{position.avgCost:.2f}",
                        f"{market_price:.2f}",
                        f"{market_value:.2f}",
                        f"{unrealized_pnl:.2f}"
                    ))
                else:
                    self.log_message(f"Failed to fetch market data for {contract.symbol}.")

        except Exception as e:
            self.log_message(f"Error updating portfolio display: {str(e)}")

        # Schedule the next update
        self.after(5000, self.update_portfolio_display)  # Update every 5 seconds
        
    def update_data(self):
        symbol = self.symbol_dropdown.get()
        rv_time = self.rv_time_var.get()

        # Fetch and update IV
        try:
            iv = get_iv(symbol)
            if iv is not None:
                self.iv_value.config(text=f"{iv:.2%}")
            else:
                self.iv_value.config(text="N/A")
                self.log_message(f"IV not available for {symbol}")
        except Exception as e:
            self.iv_value.config(text="Error")
            self.log_message(f"Error updating IV: {str(e)}")

        # Fetch and update RV
        try:
            window = self.get_window_size(rv_time)
            rv = get_latest_rv(symbol, window)
            if rv is not None:
                self.rv_value.config(text=f"{rv:.2%}")
            else:
                self.rv_value.config(text="N/A")
                self.log_message(f"RV not available for {symbol}")
        except Exception as e:
            self.rv_value.config(text="Error")
            self.log_message(f"Error updating RV: {str(e)}")

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
            stop_auto_hedger()  # This will stop the global thread
            self.hedger_thread.join()  # Wait for the thread to cleanly finish
            self.log_message("Auto-Hedger stopped.")
            self.hedger_status_label.config(text="Auto-Hedger Status: OFF", foreground="red")
        else:
            self.log_message("Auto-Hedger is not running.")
        # Update the status label on the UI
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
