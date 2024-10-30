"""Dashboard for Auto Hedger and IV/RV Calculator."""
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
import logging

# Configure module logger
logger = logging.getLogger(__name__)

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
        self.portfolio_last_update = None
        self.portfolio_update_error = None
        self.load_positions()
        self.update_current_delta()
        self.schedule_update_portfolio()
        self.update_hedger_status()
        self.check_alerts()

    def create_widgets(self):
        self.master.geometry("1200x800")
        self.grid(sticky="nsew")
        self.master.grid_rowconfigure(0, weight=1)
        self.master.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=3)
        self.grid_rowconfigure(1, weight=2)
        self.grid_columnconfigure(0, weight=1)
        
        self.create_portfolio_frame()
        
        bottom_frame = ttk.Frame(self)
        bottom_frame.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        bottom_frame.grid_columnconfigure(0, weight=1)
        bottom_frame.grid_columnconfigure(1, weight=1)
        
        self.create_hedger_frame(bottom_frame)
        self.create_ivrv_frame(bottom_frame)

    def create_portfolio_frame(self):
        portfolio_frame = ttk.LabelFrame(self, text="Portfolio")
        portfolio_frame.grid(row=0, column=0, padx=10, pady=5, sticky="nsew")
        
        status_frame = ttk.Frame(portfolio_frame)
        status_frame.pack(fill=tk.X, padx=5, pady=2)
        
        self.connection_status = ttk.Label(status_frame, text="Connection Status: Checking...", foreground="orange")
        self.connection_status.pack(side=tk.LEFT, padx=5)
        
        self.update_status = ttk.Label(status_frame, text="Last Update: Never", foreground="gray")
        self.update_status.pack(side=tk.LEFT, padx=5)
        
        self.refresh_button = ttk.Button(status_frame, text="Refresh", command=self.on_refresh_click)
        self.refresh_button.pack(side=tk.RIGHT, padx=5)
        
        self.portfolio_tree = ttk.Treeview(
            portfolio_frame,
            columns=('Symbol', 'Type', 'Position', 'Delta', 'Avg Cost', 'Market Price', 'Unrealized PNL'),
            show='headings',
            height=10
        )
        
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
        
        scrollbar = ttk.Scrollbar(portfolio_frame, orient=tk.VERTICAL, command=self.portfolio_tree.yview)
        self.portfolio_tree.configure(yscrollcommand=scrollbar.set)
        
        self.portfolio_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)

    def create_hedger_frame(self, parent):
        hedger_frame = ttk.LabelFrame(parent, text="Auto Hedger")
        hedger_frame.grid(row=0, column=0, padx=5, pady=5, sticky="nsew")
        
        for i in range(8):
            hedger_frame.grid_rowconfigure(i, weight=1)
        hedger_frame.grid_columnconfigure(1, weight=1)
        
        labels_inputs = [
            ("Select Position:", self.create_position_dropdown, 0),
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
        
        ttk.Button(hedger_frame, text="Run Auto-Hedger", command=self.run_auto_hedger).grid(
            row=5, column=0, columnspan=2, pady=10)
        ttk.Button(hedger_frame, text="Stop Auto-Hedger", command=self.stop_auto_hedger).grid(
            row=6, column=0, columnspan=2, pady=5)
        
        self.hedger_status_label = ttk.Label(hedger_frame, text="Auto-Hedger Status: OFF", foreground="red")
        self.hedger_status_label.grid(row=7, column=0, columnspan=2, pady=10)

        ttk.Button(hedger_frame, text="Show Alert History", command=self.show_alert_history).grid(
            row=8, column=0, columnspan=2, pady=5)

    def create_ivrv_frame(self, parent):
        ivrv_frame = ttk.LabelFrame(parent, text="IV / RV Calculator")
        ivrv_frame.grid(row=0, column=1, padx=5, pady=5, sticky="nsew")
        
        for i in range(6):
            ivrv_frame.grid_rowconfigure(i, weight=1)
        ivrv_frame.grid_columnconfigure(1, weight=1)
        
        ttk.Label(ivrv_frame, text="Select Symbol:").grid(row=0, column=0, padx=5, pady=5, sticky="e")
        self.symbol_var = tk.StringVar()
        self.symbol_dropdown = ttk.Combobox(ivrv_frame, textvariable=self.symbol_var)
        self.symbol_dropdown.grid(row=0, column=1, padx=5, pady=5, sticky="ew")
        
        ttk.Label(ivrv_frame, text="Implied Volatility (IV):").grid(row=1, column=0, padx=5, pady=5, sticky="e")
        self.iv_value = ttk.Label(ivrv_frame, text="N/A")
        self.iv_value.grid(row=1, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(ivrv_frame, text="Realized Volatility (RV):").grid(row=2, column=0, padx=5, pady=5, sticky="e")
        self.rv_value = ttk.Label(ivrv_frame, text="N/A")
        self.rv_value.grid(row=2, column=1, padx=5, pady=5, sticky="w")
        
        ttk.Label(ivrv_frame, text="Time Period:").grid(row=3, column=0, padx=5, pady=5, sticky="e")
        self.rv_time_var = tk.StringVar(value="30")  # Default 30 days
        self.rv_time_dropdown = ttk.Combobox(ivrv_frame, textvariable=self.rv_time_var)
        self.rv_time_dropdown['values'] = ['15', '30', '60', '90']  # Days
        self.rv_time_dropdown.current(1)  # Default to 30 days
        self.rv_time_dropdown.grid(row=3, column=1, padx=5, pady=5, sticky="ew")
        
        # Add progress indicator
        self.calc_status = ttk.Label(ivrv_frame, text="")
        self.calc_status.grid(row=4, column=0, columnspan=2, pady=5)
        
        ttk.Button(ivrv_frame, text="Update Data", command=self.update_data).grid(
            row=5, column=0, columnspan=2, pady=10)
        
        self.last_update_label = ttk.Label(ivrv_frame, text="Last Update: N/A")
        self.last_update_label.grid(row=6, column=0, columnspan=2, pady=5)

    def show_alert_history(self):
        history_window = tk.Toplevel(self)
        history_window.title("Alert History")
        history_window.geometry("600x400")
        
        columns = ('Time', 'Symbol', 'Action', 'Quantity', 'Status', 'Price', 'Details')
        tree = ttk.Treeview(history_window, columns=columns, show='headings', height=15)
        
        for col in columns:
            tree.heading(col, text=col)
            tree.column(col, width=80)
        
        scrollbar = ttk.Scrollbar(history_window, orient=tk.VERTICAL, command=tree.yview)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=5, pady=5)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y, pady=5)
        
        alerts = get_recent_alerts()
        for alert in reversed(alerts):
            tree.insert('', 'end', values=(
                alert.timestamp,
                alert.symbol,
                alert.action,
                alert.quantity,
                alert.status,
                f"${alert.price:.2f}" if alert.price else "N/A",
                alert.details or "N/A"
            ))

    def create_position_dropdown(self, parent):
        self.position_var = tk.StringVar()
        self.position_dropdown = ttk.Combobox(parent, textvariable=self.position_var)
        self.position_dropdown.bind("<<ComboboxSelected>>", self.on_position_selection)
        return self.position_dropdown

    def check_alerts(self):
        alerts = get_recent_alerts()
        last_shown = getattr(self, '_last_alert_shown', '')
        
        for alert in alerts:
            if alert.timestamp > last_shown:
                AlertNotification(self, alert)
                self._last_alert_shown = alert.timestamp
        
        self.after(1000, self.check_alerts)

    async def async_update_portfolio_display(self, force_refresh=False):
        """Update the portfolio display with current position data"""
        try:
            if not ib.isConnected():
                self.connection_status.config(text="Connection Status: Disconnected", foreground="red")
                return
            else:
                self.connection_status.config(text="Connection Status: Connected", foreground="green")

            # Get current positions first
            positions = get_portfolio_positions()  # Always gets fresh positions
            if not positions:
                # Only clear if we have no positions
                for i in self.portfolio_tree.get_children():
                    self.portfolio_tree.delete(i)
                self.update_status.config(text="No positions found", foreground="orange")
                return

            # Store current selection and values
            selected_items = self.portfolio_tree.selection()
            current_values = {
                self.portfolio_tree.item(item)["values"][0]: item 
                for item in self.portfolio_tree.get_children()
            }

            # Process all positions first and gather data
            position_data = []
            for position in positions:
                try:
                    contract = position.contract
                    # Set exchange before market data request
                    contract.exchange = 'SMART'
                    if contract.secType == 'OPT':
                        contract.exchange = 'AMEX'
                    
                    # Only qualify option contracts
                    if contract.secType == 'OPT':
                        await ib.qualifyContractsAsync(contract)
                    
                    market_price, market_value, unrealized_pnl = get_market_price(contract)  # Gets fresh portfolio data
                    delta = get_delta(position, ib, force_refresh)  # Force refresh when requested
                    
                    if market_price is None:
                        continue
                        
                    symbol = contract.localSymbol if contract.secType == 'OPT' else contract.symbol
                    position_data.append({
                        'symbol': symbol,
                        'secType': contract.secType,
                        'position': position.position,
                        'delta': delta,
                        'avgCost': position.avgCost,
                        'marketPrice': market_price,
                        'unrealizedPNL': unrealized_pnl
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing position {contract.symbol}: {str(e)}")

            # Only update display if we have data
            if position_data:
                # Update existing items and add new ones
                for data in position_data:
                    symbol = data['symbol']
                    if symbol in current_values:
                        # Update existing item
                        item_id = current_values[symbol]
                        self.portfolio_tree.item(item_id, values=(
                            symbol,
                            data['secType'],
                            f"{data['position']:,.0f}",
                            f"{data['delta']:,.2f}",
                            f"{data['avgCost']:,.2f}",
                            f"{data['marketPrice']:,.2f}",
                            f"{data['unrealizedPNL']:,.2f}"
                        ))
                        del current_values[symbol]  # Remove from current values
                    else:
                        # Insert new item
                        self.portfolio_tree.insert('', 'end', values=(
                            symbol,
                            data['secType'],
                            f"{data['position']:,.0f}",
                            f"{data['delta']:,.2f}",
                            f"{data['avgCost']:,.2f}",
                            f"{data['marketPrice']:,.2f}",
                            f"{data['unrealizedPNL']:,.2f}"
                        ))

                # Remove any remaining old items
                for item_id in current_values.values():
                    self.portfolio_tree.delete(item_id)

                # Restore selection
                for item in selected_items:
                    self.portfolio_tree.selection_add(item)

                current_time = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                self.update_status.config(text=f"Last Update: {current_time}", foreground="green")
                self.portfolio_last_update = current_time

        except Exception as e:
            logger.error(f"Error updating portfolio display: {str(e)}")
            self.update_status.config(text="Update Failed", foreground="red")
            self.portfolio_update_error = str(e)

    def schedule_update_portfolio(self):
        """Schedule regular updates of the portfolio display"""
        try:
            if ib.isConnected():
                # Regular update with cache
                asyncio.run_coroutine_threadsafe(self.async_update_portfolio_display(force_refresh=False), self.loop)
        except Exception as e:
            logger.error(f"Error scheduling portfolio update: {str(e)}")
        finally:
            self.after(5000, self.schedule_update_portfolio)

    def load_positions(self):
        try:
            positions = get_portfolio_positions()
            position_details = []
            symbols = set()  # For IV/RV calculator
            
            for p in positions:
                if p.contract.secType == 'STK':
                    position_details.append(p.contract.symbol)
                    symbols.add(p.contract.symbol)
                elif p.contract.secType == 'OPT':
                    position_details.append(p.contract.localSymbol)
                    symbols.add(p.contract.symbol)  # Add underlying symbol for IV/RV

            self.position_dropdown['values'] = position_details  # Keep full details for auto hedger
            self.symbol_dropdown['values'] = list(symbols)  # Only underlying symbols for IV/RV
            if position_details:
                self.position_dropdown.current(0)
            if symbols:
                self.symbol_dropdown.current(0)
                
        except Exception as e:
            logger.error(f"Error loading positions: {str(e)}")

    async def async_update_volatility(self):
        """Calculate IV and RV asynchronously."""
        try:
            symbol = self.symbol_var.get()
            if not symbol:
                return
                
            self.calc_status.config(text="Calculating...", foreground="orange")
            window_days = int(self.rv_time_var.get())
            
            # Run IV and RV calculations concurrently
            iv_task = asyncio.create_task(get_iv(symbol))
            rv_task = asyncio.create_task(get_latest_rv(symbol, window_days))
            
            iv, rv = await asyncio.gather(iv_task, rv_task)
            
            # Update IV display
            if iv is not None:
                self.iv_value.config(text=f"{iv:.2%}")
            else:
                self.iv_value.config(text="N/A")
                
            # Update RV display
            if rv is not None:
                self.rv_value.config(text=f"{rv:.2%}")
            else:
                self.rv_value.config(text="N/A")
                
            self.calc_status.config(text="Calculation complete", foreground="green")
            self.last_update_label.config(text=f"Last Update: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Clear status after a delay
            self.after(3000, lambda: self.calc_status.config(text=""))
            
        except Exception as e:
            logger.error(f"Error updating volatility: {str(e)}")
            self.calc_status.config(text=f"Error: {str(e)}", foreground="red")
            self.iv_value.config(text="Error")
            self.rv_value.config(text="Error")

    def update_data(self):
        """Update IV/RV data with improved async handling."""
        try:
            symbol = self.symbol_var.get()
            if not symbol:
                messagebox.showerror("Error", "Please select a symbol")
                return
                
            # Disable update button during calculation
            update_button = self.winfo_children()[1].winfo_children()[1].winfo_children()[-2]
            update_button.config(state='disabled')
            
            # Run the calculation asynchronously
            asyncio.run_coroutine_threadsafe(self.async_update_volatility(), self.loop)
            
            # Re-enable update button after a delay
            self.after(100, lambda: update_button.config(state='normal'))
            
        except Exception as e:
            logger.error(f"Error in update_data: {str(e)}")
            messagebox.showerror("Error", f"Failed to update data: {str(e)}")
            
        finally:
            # Ensure button is re-enabled
            self.after(100, lambda: update_button.config(state='normal'))

    def run_auto_hedger(self):
        try:
            position_key = self.position_var.get()
            if not position_key:
                messagebox.showerror("Error", "Please select a position")
                return

            target_delta = float(self.target_delta_entry.get())
            delta_change = float(self.delta_change_entry.get())
            max_order_qty = int(self.max_order_qty_entry.get())

            start_auto_hedger(position_key, target_delta, delta_change, max_order_qty)
            
        except Exception as e:
            logger.error(f"Error starting auto-hedger: {str(e)}")
            messagebox.showerror("Error", f"Failed to start auto-hedger: {str(e)}")

    def stop_auto_hedger(self):
        try:
            position_key = self.position_var.get()
            if position_key:
                stop_auto_hedger(position_key)
        except Exception as e:
            logger.error(f"Error stopping auto-hedger: {str(e)}")
            messagebox.showerror("Error", f"Failed to stop auto-hedger: {str(e)}")

    def update_hedger_status(self):
        try:
            position_key = self.position_var.get()
            if not position_key:
                self.hedger_status_label.config(text="Auto-Hedger Status: OFF", foreground="red")
                return

            if is_hedger_running(position_key):
                self.hedger_status_label.config(text=f"Auto-Hedger Status: ON for {position_key}", foreground="green")
            else:
                self.hedger_status_label.config(text="Auto-Hedger Status: OFF", foreground="red")
        except Exception as e:
            logger.error(f"Error updating hedger status: {str(e)}")
        self.after(1000, self.update_hedger_status)

    def update_current_delta(self):
        try:
            position_key = self.position_var.get()
            if not position_key:
                self.delta_value.config(text="N/A")
                return
            
            positions = get_portfolio_positions()
            filtered_positions = []
            
            for p in positions:
                identifier = p.contract.localSymbol if p.contract.secType == 'OPT' else p.contract.symbol
                if identifier == position_key:
                    filtered_positions.append(p)
            
            if filtered_positions:
                total_delta = 0.0
                for position in filtered_positions:
                    position.contract.exchange = 'SMART'
                    if position.contract.secType == 'OPT':
                        position.contract.exchange = 'AMEX'
                    delta = get_delta(position, ib)
                    total_delta += delta

                self.delta_value.config(text=f"{total_delta:,.2f}")
            else:
                self.delta_value.config(text="N/A")
                
        except Exception as e:
            logger.error(f"Error updating current delta: {str(e)}")
            self.delta_value.config(text="Error")
            
        self.after(5000, self.update_current_delta)

    def on_position_selection(self, event):
        self.update_current_delta()

    def on_refresh_click(self):
        """Handle manual refresh button click"""
        try:
            if ib.isConnected():
                # Force refresh when manually requested
                asyncio.run_coroutine_threadsafe(self.async_update_portfolio_display(force_refresh=True), self.loop)
        except Exception as e:
            logger.error(f"Error during manual refresh: {str(e)}")
