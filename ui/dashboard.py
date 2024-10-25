import asyncio
import tkinter as tk
from tkinter import ttk
from datetime import datetime
from components.ib_connection import (
    get_portfolio_positions,
    define_stock_contract,
    get_market_price,
    get_delta,
    ib
)
from components.auto_hedger import (
    start_auto_hedger,
    stop_auto_hedger,
    is_hedger_running
)
from components.iv_calculator import get_iv
from components.rv_calculator import get_latest_rv

class Dashboard(tk.Frame):
    def __init__(self, parent, loop):
        super().__init__(parent)
        self.loop = loop
        self.create_widgets()
        # Initialize portfolio update status
        self.portfolio_last_update = None
        self.portfolio_update_error = None
        self.load_stocks()
        self.update_current_delta()
        self.schedule_update_portfolio()
        self.update_hedger_status()

    def create_widgets(self):
        self.master.geometry("1180x930")  # Reduced height since we removed Activity Logs
        
        # Configure grid layout for master (main window) to expand as needed
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_rowconfigure(1, weight=3)
        self.master.grid_columnconfigure(0, weight=1)
        
        # Create portfolio frame with status indicators
        self.portfolio_frame = ttk.LabelFrame(self, text="Portfolio")
        self.portfolio_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Configure grid layout within portfolio_frame
        self.portfolio_frame.grid_rowconfigure(0, weight=0)
        self.portfolio_frame.grid_rowconfigure(1, weight=1)
        self.portfolio_frame.grid_columnconfigure(0, weight=1)

        # Add status indicators for portfolio
        self.portfolio_status_frame = ttk.Frame(self.portfolio_frame)
        self.portfolio_status_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=2)
        
        self.connection_status = ttk.Label(self.portfolio_status_frame, text="Connection Status: Checking...", foreground="orange")
        self.connection_status.pack(side=tk.LEFT, padx=5)
        
        self.update_status = ttk.Label(self.portfolio_status_frame, text="Last Update: Never", foreground="gray")
        self.update_status.pack(side=tk.LEFT, padx=5)
        
        self.portfolio_tree = ttk.Treeview(
            self.portfolio_frame,
            columns=('Symbol', 'Type', 'Position', 'Delta', 'Avg Cost', 'Market Price', 'Unrealized PNL'),
            show='headings',
            height=20
        )
        self.portfolio_tree.heading('Symbol', text='Symbol')
        self.portfolio_tree.heading('Type', text='Type')
        self.portfolio_tree.heading('Position', text='Position')
        self.portfolio_tree.heading('Delta', text='Delta')
        self.portfolio_tree.heading('Avg Cost', text='Avg Cost')
        self.portfolio_tree.heading('Market Price', text='Market Price')
        self.portfolio_tree.heading('Unrealized PNL', text='Unrealized PNL')
        self.portfolio_tree.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        self.portfolio_tree.column('Symbol', width=150)
        self.portfolio_tree.column('Type', width=100)
        self.portfolio_tree.column('Position', width=100)
        self.portfolio_tree.column('Delta', width=100)
        self.portfolio_tree.column('Avg Cost', width=100)
        self.portfolio_tree.column('Market Price', width=100)
        self.portfolio_tree.column('Unrealized PNL', width=150)

        # Add refresh button for portfolio
        self.refresh_button = ttk.Button(self.portfolio_status_frame, text="Refresh", 
                                       command=lambda: asyncio.run_coroutine_threadsafe(self.async_update_portfolio_display(), self.loop))
        self.refresh_button.pack(side=tk.RIGHT, padx=5)

        # Auto Hedger Frame
        self.hedger_frame = ttk.LabelFrame(self, text="Auto Hedger")
        self.hedger_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        self.stock_label = ttk.Label(self.hedger_frame, text="Select Stock Symbol:")
        self.stock_label.grid(row=0, column=0, padx=10, pady=10)
        self.stock_var = tk.StringVar()
        self.stock_dropdown = ttk.Combobox(self.hedger_frame, textvariable=self.stock_var)
        self.stock_dropdown.grid(row=0, column=1, padx=10, pady=10)
        self.stock_dropdown.bind("<<ComboboxSelected>>", self.on_stock_selection)

        self.delta_label = ttk.Label(self.hedger_frame, text="Current Delta:")
        self.delta_label.grid(row=1, column=0, padx=10, pady=10)
        self.delta_value = ttk.Label(self.hedger_frame, text="Loading...")
        self.delta_value.grid(row=1, column=1, padx=10, pady=10)

        self.target_delta_label = ttk.Label(self.hedger_frame, text="Target Delta:")
        self.target_delta_label.grid(row=2, column=0, padx=10, pady=10)
        self.target_delta_entry = ttk.Entry(self.hedger_frame)
        self.target_delta_entry.grid(row=2, column=1, padx=10, pady=10)
        self.target_delta_entry.insert(0, "200")

        self.delta_change_label = ttk.Label(self.hedger_frame, text="Delta Change Threshold:")
        self.delta_change_label.grid(row=3, column=0, padx=10, pady=10)
        self.delta_change_entry = ttk.Entry(self.hedger_frame)
        self.delta_change_entry.grid(row=3, column=1, padx=10, pady=10)
        self.delta_change_entry.insert(0, "50")

        self.max_order_qty_label = ttk.Label(self.hedger_frame, text="Max Order Qty:")
        self.max_order_qty_label.grid(row=4, column=0, padx=10, pady=10)
        self.max_order_qty_entry = ttk.Entry(self.hedger_frame)
        self.max_order_qty_entry.grid(row=4, column=1, padx=10, pady=10)
        self.max_order_qty_entry.insert(0, "500")

        self.hedge_button = ttk.Button(self.hedger_frame, text="Run Auto-Hedger", command=self.run_auto_hedger)
        self.hedge_button.grid(row=5, column=0, columnspan=2, padx=10, pady=10)

        self.stop_button = ttk.Button(self.hedger_frame, text="Stop Auto-Hedger", command=self.stop_auto_hedger)
        self.stop_button.grid(row=6, column=0, columnspan=2, padx=10, pady=10)

        self.hedger_status_label = ttk.Label(self.hedger_frame, text="Auto-Hedger Status: OFF", foreground="red")
        self.hedger_status_label.grid(row=7, column=0, columnspan=2, padx=10, pady=10)

        # IV/RV Calculator Frame
        self.ivrv_frame = ttk.LabelFrame(self, text="IV / RV Calculator")
        self.ivrv_frame.grid(row=1, column=1, padx=10, pady=10, sticky="nsew")

        self.symbol_var = tk.StringVar()
        self.symbol_dropdown = ttk.Combobox(self.ivrv_frame, textvariable=self.symbol_var)
        self.symbol_dropdown.grid(row=0, column=1, padx=10, pady=10)
        
        self.iv_label = ttk.Label(self.ivrv_frame, text="Implied Volatility (IV):")
        self.iv_label.grid(row=1, column=0, padx=10, pady=10)
        self.iv_value = ttk.Label(self.ivrv_frame, text="Calculating...")
        self.iv_value.grid(row=1, column=1, padx=10, pady=10)

        self.rv_label = ttk.Label(self.ivrv_frame, text="Realized Volatility (RV):")
        self.rv_label.grid(row=2, column=0, padx=10, pady=10)
        self.rv_value = ttk.Label(self.ivrv_frame, text="Calculating...")
        self.rv_value.grid(row=2, column=1, padx=10, pady=10)

        self.rv_time_var = tk.StringVar()
        self.rv_time_dropdown = ttk.Combobox(self.ivrv_frame, textvariable=self.rv_time_var)
        self.rv_time_dropdown['values'] = ['15 min', '30 min', '1 hour', '2 hours']
        self.rv_time_dropdown.grid(row=3, column=1, padx=10, pady=10)
        self.rv_time_dropdown.current(0)

        self.update_button = ttk.Button(self.ivrv_frame, text="Update Data", command=self.update_data)
        self.update_button.grid(row=4, column=0, columnspan=2, padx=10, pady=10)

        self.last_update_label = ttk.Label(self.ivrv_frame, text="Last Update: N/A")
        self.last_update_label.grid(row=5, column=0, columnspan=2, padx=10, pady=10)

    async def async_update_portfolio_display(self):
        """Update the portfolio display with current position data"""
        try:
            # Update connection status
            if not ib.isConnected():
                self.connection_status.config(text="Connection Status: Disconnected", foreground="red")
                return
            else:
                self.connection_status.config(text="Connection Status: Connected", foreground="green")

            # Clear existing data in the treeview
            for i in self.portfolio_tree.get_children():
                self.portfolio_tree.delete(i)

            positions = get_portfolio_positions()
            if not positions:
                return

            for position in positions:
                try:
                    contract = position.contract
                    market_price, market_value, unrealized_pnl = get_market_price(contract)
                    delta = get_delta(position, ib)

                    if market_price is not None:
                        # Insert the row with portfolio data
                        self.master.after(0, self.insert_treeview_row, 
                                        contract.symbol, 
                                        contract.secType, 
                                        position.position,
                                        f"{delta:.2f}", 
                                        f"{position.avgCost:.2f}", 
                                        f"{market_price:.2f}", 
                                        f"{unrealized_pnl:.2f}")

                except Exception as e:
                    print(f"Error processing position {contract.symbol}: {str(e)}")

            # Update the last update time
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.update_status.config(text=f"Last Update: {current_time}", foreground="green")
            self.portfolio_last_update = current_time
            
        except Exception as e:
            print(f"Error in async_update_portfolio_display: {str(e)}")
            self.update_status.config(text="Update Failed", foreground="red")
            self.portfolio_update_error = str(e)

    def insert_treeview_row(self, symbol, secType, position, delta, avg_cost, market_price, unrealized_pnl):
        """Insert a row into the portfolio treeview"""
        try:
            self.portfolio_tree.insert('', 'end', values=(
                symbol, secType, position, delta, avg_cost, market_price, unrealized_pnl
            ))
        except Exception as e:
            print(f"Error inserting row into treeview: {str(e)}")

    def schedule_update_portfolio(self):
        """Schedule regular updates of the portfolio display"""
        try:
            if ib.isConnected():
                asyncio.run_coroutine_threadsafe(self.async_update_portfolio_display(), self.loop)
        except Exception as e:
            print(f"Error scheduling portfolio update: {str(e)}")
        finally:
            # Schedule next update in 5 seconds
            self.after(5000, self.schedule_update_portfolio)

    def load_stocks(self):
        """Load stock symbols into dropdowns"""
        try:
            positions = get_portfolio_positions()
            eligible_symbols = []
            for p in positions:
                if p.contract.secType == 'STK':
                    eligible_symbols.append(p.contract.symbol)
                elif p.contract.secType == 'OPT':
                    details = f"{p.contract.symbol} {p.contract.lastTradeDateOrContractMonth} {p.contract.strike} {p.contract.right}"
                    eligible_symbols.append(details)

            self.stock_dropdown['values'] = eligible_symbols
            self.symbol_dropdown['values'] = eligible_symbols
            if eligible_symbols:
                self.stock_dropdown.current(0)
                self.symbol_dropdown.current(0)
        except Exception as e:
            print(f"Error loading stocks: {str(e)}")

    def update_data(self):
        """Update IV/RV data for the selected symbol"""
        symbol = self.symbol_dropdown.get()
        rv_time = self.rv_time_var.get()

        try:
            iv = get_iv(symbol)
            if iv is not None:
                self.iv_value.config(text=f"{iv:.2%}")
            else:
                self.iv_value.config(text="N/A")
        except Exception as e:
            self.iv_value.config(text="Error")
            print(f"Error updating IV: {str(e)}")

        try:
            window_days = 30  # Use a 30-day window for RV calculation
            rv = get_latest_rv(symbol, window_days)
            if rv is not None:
                self.rv_value.config(text=f"{rv:.2%}")
            else:
                self.rv_value.config(text="N/A")
        except Exception as e:
            self.rv_value.config(text="Error")
            print(f"Error updating RV: {str(e)}")
        
        self.last_update_label.config(text=f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    def run_auto_hedger(self):
        """Start the auto-hedger"""
        try:
            stock_symbol = self.stock_var.get()
            target_delta = float(self.target_delta_entry.get())
            delta_change = float(self.delta_change_entry.get())
            max_order_qty = int(self.max_order_qty_entry.get())

            start_auto_hedger(stock_symbol, target_delta, delta_change, max_order_qty)
        except Exception as e:
            print(f"Error starting auto-hedger: {str(e)}")

    def stop_auto_hedger(self):
        """Stop the auto-hedger"""
        try:
            stock_symbol = self.stock_var.get()
            stop_auto_hedger(stock_symbol)
        except Exception as e:
            print(f"Error stopping auto-hedger: {str(e)}")

    def update_hedger_status(self):
        """Update the auto-hedger status display"""
        try:
            stock_symbol = self.stock_var.get()
            if is_hedger_running(stock_symbol):
                self.hedger_status_label.config(text=f"Auto-Hedger Status: ON for {stock_symbol}", foreground="green")
            else:
                self.hedger_status_label.config(text="Auto-Hedger Status: OFF", foreground="red")
        except Exception as e:
            print(f"Error updating hedger status: {str(e)}")
        self.after(1000, self.update_hedger_status)

    def update_current_delta(self):
        """Update the current delta display"""
        try:
            stock_symbol = self.stock_var.get()
            if not stock_symbol:
                self.delta_value.config(text="N/A")
                return

            positions = get_portfolio_positions()
            positions = [p for p in positions if p.contract.symbol == stock_symbol]
            aggregate_delta = sum([get_delta(p, ib) for p in positions])

            self.delta_value.config(text=f"{aggregate_delta:.2f}")
        except Exception as e:
            self.delta_value.config(text="Error")
            print(f"Error updating current delta: {str(e)}")
        self.after(5000, self.update_current_delta)

    def on_stock_selection(self, event):
        """Handle stock selection change"""
        self.update_current_delta()
