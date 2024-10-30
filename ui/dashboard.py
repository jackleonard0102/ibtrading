import asyncio
import tkinter as tk
from tkinter import ttk, messagebox
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
    is_hedger_running,
    get_recent_alerts
)
from components.iv_calculator import get_iv
from components.rv_calculator import get_latest_rv

class AlertNotification(tk.Toplevel):
    """Alert notification window."""
    
    def __init__(self, parent, alert):
        super().__init__(parent)
        
        self.title("Trade Alert")
        self.geometry("400x200")
        
        # Configure style
        style = ttk.Style()
        if alert.status == 'FILLED':
            bg_color = '#e6ffe6'  # Light green
            fg_color = '#006600'  # Dark green
        elif alert.status == 'FAILED' or alert.status == 'ERROR':
            bg_color = '#ffe6e6'  # Light red
            fg_color = '#cc0000'  # Dark red
        else:
            bg_color = '#fff9e6'  # Light yellow
            fg_color = '#cc7700'  # Dark orange
            
        self.configure(bg=bg_color)
        
        # Header
        header_frame = ttk.Frame(self)
        header_frame.pack(fill=tk.X, padx=10, pady=(10,5))
        
        ttk.Label(header_frame, text=f"Trade Alert - {alert.status}", 
                 font=('Arial', 12, 'bold'), foreground=fg_color).pack()
        
        # Content
        content_frame = ttk.Frame(self)
        content_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)
        
        details = [
            ("Symbol:", alert.symbol),
            ("Action:", alert.action),
            ("Quantity:", str(alert.quantity)),
            ("Type:", alert.order_type),
            ("Time:", alert.timestamp)
        ]
        
        if alert.price:
            details.append(("Price:", f"${alert.price:.2f}"))
            
        if alert.details:
            details.append(("Details:", alert.details))
            
        for label, value in details:
            row = ttk.Frame(content_frame)
            row.pack(fill=tk.X, pady=2)
            ttk.Label(row, text=label, width=10).pack(side=tk.LEFT)
            ttk.Label(row, text=value).pack(side=tk.LEFT)
            
        # Close button
        ttk.Button(self, text="Close", command=self.destroy).pack(pady=10)
        
        # Center window
        self.update_idletasks()
        width = self.winfo_width()
        height = self.winfo_height()
        x = (self.winfo_screenwidth() // 2) - (width // 2)
        y = (self.winfo_screenheight() // 2) - (height // 2)
        self.geometry(f"+{x}+{y}")
        
        # Auto-close after 10 seconds
        self.after(10000, self.destroy)

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
        self.check_alerts()  # Start checking for alerts

    def create_widgets(self):
        # Configure main window size and grid weights
        self.master.geometry("1200x800")
        
        # Configure grid weights for the main window
        self.grid(sticky="nsew")
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        
        # Configure grid weights for the dashboard frame
        self.grid_rowconfigure(0, weight=3)  # Portfolio section
        self.grid_rowconfigure(1, weight=2)  # Auto-Hedger and IV/RV section
        self.grid_columnconfigure(0, weight=1)
        
        # Create portfolio frame
        self.create_portfolio_frame()
        
        # Create bottom frame to hold Auto-Hedger and IV/RV Calculator side by side
        bottom_frame = ttk.Frame(self)
        bottom_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        bottom_frame.grid_columnconfigure(0, weight=1)  # Auto-Hedger
        bottom_frame.grid_columnconfigure(1, weight=1)  # IV/RV Calculator
        
        # Create Auto-Hedger and IV/RV Calculator frames in the bottom frame
        self.create_hedger_frame(bottom_frame)
        self.create_ivrv_frame(bottom_frame)

    def create_portfolio_frame(self):
        # Portfolio Frame
        portfolio_frame = ttk.LabelFrame(self, text="Portfolio")
        portfolio_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        # Status Frame
        status_frame = ttk.Frame(portfolio_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.connection_status = ttk.Label(status_frame, text="Connection Status: Checking...", foreground="orange")
        self.connection_status.pack(side=tk.LEFT, padx=5)
        
        self.update_status = ttk.Label(status_frame, text="Last Update: Never", foreground="gray")
        self.update_status.pack(side=tk.LEFT, padx=5)
        
        self.refresh_button = ttk.Button(status_frame, text="Refresh", 
                                       command=lambda: asyncio.run_coroutine_threadsafe(
                                           self.async_update_portfolio_display(), self.loop))
        self.refresh_button.pack(side=tk.RIGHT, padx=5)
        
        # Portfolio Treeview
        self.portfolio_tree = ttk.Treeview(
            portfolio_frame,
            columns=('Symbol', 'Type', 'Position', 'Delta', 'Avg Cost', 'Market Price', 'Unrealized PNL'),
            show='headings',
            height=10
        )
        
        # Configure columns
        columns = [
            ('Symbol', 100),
            ('Type', 80),
            ('Position', 100),
            ('Delta', 100),
            ('Avg Cost', 100),
            ('Market Price', 100),
            ('Unrealized PNL', 120)
        ]
        
        for col, width in columns:
            self.portfolio_tree.heading(col, text=col)
            self.portfolio_tree.column(col, width=width, minwidth=50)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(portfolio_frame, orient=tk.VERTICAL, command=self.portfolio_tree.yview)
        self.portfolio_tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack the treeview and scrollbar
        self.portfolio_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

    def create_hedger_frame(self, parent):
        # Auto Hedger Frame
        hedger_frame = ttk.LabelFrame(parent, text="Auto Hedger")
        hedger_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        # Configure grid
        for i in range(8):
            hedger_frame.grid_rowconfigure(i, weight=1)
        hedger_frame.grid_columnconfigure(1, weight=1)
        
        # Labels and inputs
        labels_inputs = [
            ("Select Stock Symbol:", self.create_stock_dropdown, 0),
            ("Current Delta:", lambda f: ttk.Label(f, text="Loading..."), 1),
            ("Target Delta:", lambda f: ttk.Entry(f), 2),
            ("Delta Change Threshold:", lambda f: ttk.Entry(f), 3),
            ("Max Order Qty:", lambda f: ttk.Entry(f), 4)
        ]
        
        for label_text, input_creator, row in labels_inputs:
            ttk.Label(hedger_frame, text=label_text).grid(row=row, column=0, padx=5, pady=5, sticky="e")
            widget = input_creator(hedger_frame)
            if isinstance(widget, ttk.Entry):
                widget.grid(row=row, column=1, padx=5, pady=5, sticky="ew")
            else:
                widget.grid(row=row, column=1, padx=5, pady=5, sticky="w")
            
            if row == 1:
                self.delta_value = widget
            elif row == 2:
                self.target_delta_entry = widget
                widget.insert(0, "200")
            elif row == 3:
                self.delta_change_entry = widget
                widget.insert(0, "50")
            elif row == 4:
                self.max_order_qty_entry = widget
                widget.insert(0, "500")
        
        # Buttons and status
        ttk.Button(hedger_frame, text="Run Auto-Hedger", command=self.run_auto_hedger).grid(
            row=5, column=0, columnspan=2, pady=10)
        ttk.Button(hedger_frame, text="Stop Auto-Hedger", command=self.stop_auto_hedger).grid(
            row=6, column=0, columnspan=2, pady=5)
        
        self.hedger_status_label = ttk.Label(hedger_frame, text="Auto-Hedger Status: OFF", foreground="red")
        self.hedger_status_label.grid(row=7, column=0, columnspan=2, pady=10)

        # Alert History Button
        ttk.Button(hedger_frame, text="Show Alert History", command=self.show_alert_history).grid(
            row=8, column=0, columnspan=2, pady=5)

    def create_ivrv_frame(self, parent):
        # IV/RV Calculator Frame
        ivrv_frame = ttk.LabelFrame(parent, text="IV / RV Calculator")
        ivrv_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        # Configure grid
        for i in range(6):
            ivrv_frame.grid_rowconfigure(i, weight=1)
        ivrv_frame.grid_columnconfigure(1, weight=1)
        
        # Symbol dropdown
        ttk.Label(ivrv_frame, text="Select Symbol:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.symbol_var = tk.StringVar()
        self.symbol_dropdown = ttk.Combobox(ivrv_frame, textvariable=self.symbol_var)
        self.symbol_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        # IV and RV displays
        ttk.Label(ivrv_frame, text="Implied Volatility (IV):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.iv_value = ttk.Label(ivrv_frame, text="Calculating...")
        self.iv_value.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(ivrv_frame, text="Realized Volatility (RV):").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.rv_value = ttk.Label(ivrv_frame, text="Calculating...")
        self.rv_value.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        # Time period dropdown
        ttk.Label(ivrv_frame, text="Time Period:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.rv_time_var = tk.StringVar()
        self.rv_time_dropdown = ttk.Combobox(ivrv_frame, textvariable=self.rv_time_var)
        self.rv_time_dropdown['values'] = ['15 min', '30 min', '1 hour', '2 hours']
        self.rv_time_dropdown.current(0)
        self.rv_time_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        # Update button and last update label
        ttk.Button(ivrv_frame, text="Update Data", command=self.update_data).grid(
            row=4, column=0, columnspan=2, pady=10)
        
        self.last_update_label = ttk.Label(ivrv_frame, text="Last Update: N/A")
        self.last_update_label.grid(row=5, column=0, columnspan=2, pady=5)

    def show_alert_history(self):
        """Show alert history in a new window."""
        history_window = tk.Toplevel(self)
        history_window.title("Alert History")
        history_window.geometry("600x400")
        
        # Create Treeview
        columns = ('Time', 'Symbol', 'Action', 'Quantity', 'Status', 'Price', 'Details')
        tree = ttk.Treeview(history_window, columns=columns, show='headings', height=15)
        
        # Configure columns
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=80)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(history_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Pack widgets
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        # Populate with alerts
        alerts = get_recent_alerts()
        for alert in reversed(alerts):  # Show newest first
            tree.insert('', 'end', values=(
                alert.timestamp,
                alert.symbol,
                alert.action,
                alert.quantity,
                alert.status,
                f"${alert.price:.2f}" if alert.price else "N/A",
                alert.details or "N/A"
            ))
    def create_stock_dropdown(self, parent):
        self.stock_var = tk.StringVar()
        self.stock_dropdown = ttk.Combobox(parent, textvariable=self.stock_var)
        self.stock_dropdown.bind("<<ComboboxSelected>>", self.on_stock_selection)
        return self.stock_dropdown

    def check_alerts(self):
        """Check for new alerts and display notifications."""
        alerts = get_recent_alerts()
        
        # Get the last displayed alert timestamp from widget attribute
        last_shown = getattr(self, '_last_alert_shown', '')
        
        # Show notifications for new alerts
        for alert in alerts:
            if alert.timestamp > last_shown:
                AlertNotification(self, alert)
                self._last_alert_shown = alert.timestamp
        
        # Schedule next check
        self.after(1000, self.check_alerts)

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
            messagebox.showerror("Error", f"Failed to start auto-hedger: {str(e)}")

    def stop_auto_hedger(self):
        """Stop the auto-hedger"""
        try:
            stock_symbol = self.stock_var.get()
            stop_auto_hedger(stock_symbol)
        except Exception as e:
            print(f"Error stopping auto-hedger: {str(e)}")
            messagebox.showerror("Error", f"Failed to stop auto-hedger: {str(e)}")

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
