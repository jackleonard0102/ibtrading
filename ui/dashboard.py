import asyncio
import tkinter as tk
from tkinter import ttk
import webbrowser
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
    get_hedge_log,
    is_hedger_running,
    get_command,
    command_queue
)
from components.iv_calculator import get_iv, get_stock_list
from components.rv_calculator import get_latest_rv
from ib_insync import Stock, Option

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
        self.update_hedge_log()
        self.process_auto_hedger_commands()
        # Start initial portfolio update
        asyncio.run_coroutine_threadsafe(self.async_update_portfolio_display(), self.loop)

    def create_widgets(self):
        self.master.geometry("1645x940")
        
        # Configure grid layout for master (main window) to expand as needed
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_rowconfigure(1, weight=3)  # Allocate more weight for the portfolio section
        self.master.grid_columnconfigure(0, weight=1)
        
        # Create portfolio frame with status indicators
        self.portfolio_frame = ttk.LabelFrame(self, text="Portfolio")
        self.portfolio_frame.grid(row=0, column=0, padx=10, pady=10, sticky="nsew")
        
        # Configure grid layout within portfolio_frame to allow resizing
        self.portfolio_frame.grid_rowconfigure(0, weight=0)  # Status row doesn't need to expand
        self.portfolio_frame.grid_rowconfigure(1, weight=1)  # Treeview row should expand
        self.portfolio_frame.grid_columnconfigure(0, weight=1)

        # Add status indicators for portfolio
        self.portfolio_status_frame = ttk.Frame(self.portfolio_frame)
        self.portfolio_status_frame.grid(row=0, column=0, sticky="ew", padx=5, pady=2)

        self.connection_status = ttk.Label(self.portfolio_status_frame, text="Connection Status: Checking...", foreground="orange")
        self.connection_status.pack(side=tk.LEFT, padx=5)

        self.update_status = ttk.Label(self.portfolio_status_frame, text="Last Update: Never", foreground="gray")
        self.update_status.pack(side=tk.LEFT, padx=5)

        self.refresh_button = ttk.Button(self.portfolio_status_frame, text="Refresh", 
                                        command=lambda: asyncio.run_coroutine_threadsafe(self.async_update_portfolio_display(), self.loop))
        self.refresh_button.pack(side=tk.RIGHT, padx=5)

        # Create a Treeview for displaying portfolio details
        self.portfolio_tree = ttk.Treeview(
            self.portfolio_frame,
            columns=('Symbol', 'Type', 'Position', 'Delta', 'Avg Cost', 'Market Price', 'Unrealized PNL'),
            show='headings'
        )
        self.portfolio_tree.heading('Symbol', text='Symbol')
        self.portfolio_tree.heading('Type', text='Type')
        self.portfolio_tree.heading('Position', text='Position')
        self.portfolio_tree.heading('Delta', text='Delta')
        self.portfolio_tree.heading('Avg Cost', text='Avg Cost')
        self.portfolio_tree.heading('Market Price', text='Market Price')
        self.portfolio_tree.heading('Unrealized PNL', text='Unrealized PNL')
        self.portfolio_tree.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")

        # Configure column widths (optional, adjust if necessary)
        self.portfolio_tree.column('Symbol', width=150)
        self.portfolio_tree.column('Type', width=100)
        self.portfolio_tree.column('Position', width=100)
        self.portfolio_tree.column('Delta', width=100)
        self.portfolio_tree.column('Avg Cost', width=100)
        self.portfolio_tree.column('Market Price', width=100)
        self.portfolio_tree.column('Unrealized PNL', width=150)

        # Create the Auto Hedger frame
        self.hedger_frame = ttk.LabelFrame(self, text="Auto Hedger")
        self.hedger_frame.grid(row=1, column=0, padx=10, pady=10, sticky="nsew")
        self.hedger_frame.grid_rowconfigure(8, weight=1)
        self.hedger_frame.grid_columnconfigure(1, weight=1)

        self.stock_label = ttk.Label(self.hedger_frame, text="Select Stock Symbol:")
        self.stock_label.grid(row=0, column=0, padx=10, pady=10)
        self.stock_var = tk.StringVar()
        self.stock_dropdown = ttk.Combobox(self.hedger_frame, textvariable=self.stock_var)
        self.stock_dropdown.grid(row=0, column=1, padx=10, pady=10)
        self.stock_dropdown.bind("<<ComboboxSelected>>", self.on_stock_selection)
        self.position_listbox = tk.Listbox(self.hedger_frame, selectmode=tk.MULTIPLE)
        self.position_listbox.grid(row=8, column=0, columnspan=2, padx=10, pady=10)

        self.delta_label = ttk.Label(self.hedger_frame, text="Current Delta:")
        self.delta_label.grid(row=1, column=0, padx=10, pady=10)
        self.delta_value = ttk.Label(self.hedger_frame, text="Loading...")
        self.delta_value.grid(row=1, column=1, padx=10, pady=10)

        # Add refresh button for portfolio
        self.refresh_button = ttk.Button(self.portfolio_status_frame, text="Refresh", 
                                       command=lambda: asyncio.run_coroutine_threadsafe(self.async_update_portfolio_display(), self.loop))
        self.refresh_button.pack(side=tk.RIGHT, padx=5)

        # Rest of the widgets
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

        # Set up the logs frame
        self.logs_frame = ttk.LabelFrame(self, text="Activity Logs")
        self.logs_frame.grid(row=2, column=0, padx=10, pady=10, sticky="nsew")
        
        self.logs_text = tk.Text(self.logs_frame, height=10, width=50)
        self.logs_text.pack(padx=5, pady=5, fill=tk.BOTH, expand=True)
        
        # Add a scrollbar
        self.logs_scrollbar = ttk.Scrollbar(self.logs_frame, command=self.logs_text.yview)
        self.logs_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.logs_text['yscrollcommand'] = self.logs_scrollbar.set
        
        # Configure text widget for logging
        self.logs_text.configure(state='disabled')

    async def async_update_portfolio_display(self):
        """Update the portfolio display with current position data"""
        print("Starting async_update_portfolio_display...")
        
        try:
            # Update connection status
            if not ib.isConnected():
                self.connection_status.config(text="Connection Status: Disconnected", foreground="red")
                self.log_message("Error: Not connected to Interactive Brokers")
                return
            else:
                self.connection_status.config(text="Connection Status: Connected", foreground="green")

            # Clear existing data in the treeview
            for i in self.portfolio_tree.get_children():
                self.portfolio_tree.delete(i)

            positions = get_portfolio_positions()
            if not positions:
                self.log_message("No positions found in portfolio")
                return

            print(f"Fetched {len(positions)} positions for display.")

            for position in positions:
                try:
                    contract = position.contract
                    print(f"Processing position for symbol: {contract.symbol}, secType: {contract.secType}")

                    # Get market price and PNL from portfolio data
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
                    else:
                        print(f"No market data available for {contract.symbol}")
                        self.log_message(f"No market data available for {contract.symbol}")

                except Exception as e:
                    print(f"Error processing position {contract.symbol}: {str(e)}")
                    self.log_message(f"Error processing position {contract.symbol}: {str(e)}")

            # Update the last update time
            current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.update_status.config(text=f"Last Update: {current_time}", foreground="green")
            self.portfolio_last_update = current_time
            
        except Exception as e:
            print(f"Error in async_update_portfolio_display: {str(e)}")
            self.log_message(f"Error updating portfolio display: {str(e)}")
            self.update_status.config(text="Update Failed", foreground="red")
            self.portfolio_update_error = str(e)

        print("Completed async_update_portfolio_display.")

    def insert_treeview_row(self, symbol, secType, position, delta, avg_cost, market_price, unrealized_pnl):
        """Insert a row into the portfolio treeview"""
        try:
            self.portfolio_tree.insert('', 'end', values=(
                symbol, secType, position, delta, avg_cost, market_price, unrealized_pnl
            ))
        except Exception as e:
            print(f"Error inserting row into treeview: {str(e)}")
            self.log_message(f"Error inserting row into treeview: {str(e)}")

    def schedule_update_portfolio(self):
        """Schedule regular updates of the portfolio display"""
        print("Scheduling portfolio update...")
        try:
            if ib.isConnected():
                asyncio.run_coroutine_threadsafe(self.async_update_portfolio_display(), self.loop)
                print("Scheduled portfolio update.")
            else:
                self.log_message("Cannot update portfolio: Not connected to Interactive Brokers")
                self.connection_status.config(text="Connection Status: Disconnected", foreground="red")
        except Exception as e:
            print(f"Error scheduling portfolio update: {str(e)}")
        finally:
            # Schedule next update in 5 seconds
            self.after(5000, self.schedule_update_portfolio)

    def load_stocks(self):
        """Load stock symbols into dropdowns"""
        self.log_message("Loading stocks...")
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
            if eligible_symbols:
                self.stock_dropdown.current(0)
                self.log_message(f"Loaded {len(eligible_symbols)} eligible positions.")
            else:
                self.log_message("No eligible positions found.")
        except Exception as e:
            self.log_message(f"Error loading stocks: {str(e)}")

    def log_message(self, message):
        """Add a message to the logs"""
        try:
            self.logs_text.configure(state='normal')
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            self.logs_text.insert('end', f"{timestamp} - {message}\n")
            self.logs_text.see('end')
            self.logs_text.configure(state='disabled')
        except Exception as e:
            print(f"Error logging message: {str(e)}")

    def run_auto_hedger(self):
        """Start the auto-hedger"""
        try:
            stock_symbol = self.stock_var.get()
            target_delta = float(self.target_delta_entry.get())
            delta_change = float(self.delta_change_entry.get())
            max_order_qty = int(self.max_order_qty_entry.get())

            selected_indices = self.position_listbox.curselection()
            selected_positions = [self.position_listbox.get(i) for i in selected_indices]

            self.log_message(f"Starting Auto-Hedger for {stock_symbol}")
            self.log_message(f"Target Delta: {target_delta}, Change Threshold: {delta_change}, Max Qty: {max_order_qty}")

            start_auto_hedger(stock_symbol, target_delta, delta_change, max_order_qty, selected_positions)
        except Exception as e:
            self.log_message(f"Error starting auto-hedger: {str(e)}")

    def stop_auto_hedger(self):
        """Stop the auto-hedger"""
        try:
            stop_auto_hedger()
            self.log_message("Auto-Hedger stopped.")
        except Exception as e:
            self.log_message(f"Error stopping auto-hedger: {str(e)}")

    def update_hedger_status(self):
        """Update the auto-hedger status display"""
        try:
            if is_hedger_running():
                self.hedger_status_label.config(text="Auto-Hedger Status: ON", foreground="green")
            else:
                self.hedger_status_label.config(text="Auto-Hedger Status: OFF", foreground="red")
        except Exception as e:
            self.log_message(f"Error updating hedger status: {str(e)}")
        self.after(1000, self.update_hedger_status)

    def update_hedge_log(self):
        """Update the hedge log display"""
        try:
            hedge_log = get_hedge_log()
            if hedge_log:
                for log_entry in hedge_log:
                    self.log_message(log_entry)
        except Exception as e:
            self.log_message(f"Error updating hedge log: {str(e)}")
        self.after(1000, self.update_hedge_log)

    def process_auto_hedger_commands(self):
        """Process commands from the auto-hedger"""
        try:
            command = get_command()
            if command:
                action = command[0]
                if action == 'get_positions':
                    stock_symbol = command[1]
                    positions = [p for p in ib.positions() if p.contract.symbol == stock_symbol]
                    command_queue.put(positions)
                elif action == 'get_deltas':
                    positions = command[1]
                    deltas = []
                    for p in positions:
                        try:
                            delta = get_delta(p, ib)
                            deltas.append(delta)
                        except Exception as e:
                            print(f"Error getting delta for position {p}: {e}")
                            deltas.append(0)
                    command_queue.put(deltas)
        except Exception as e:
            self.log_message(f"Error processing auto-hedger command: {str(e)}")
        self.after(100, self.process_auto_hedger_commands)

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
            self.log_message(f"Error updating current delta: {str(e)}")
        self.after(5000, self.update_current_delta)

    def on_stock_selection(self, event):
        """Handle stock selection change"""
        self.update_current_delta()
