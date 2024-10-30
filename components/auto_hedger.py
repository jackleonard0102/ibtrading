"""Auto hedger implementation with alert functionality."""

from collections import deque
import threading
from datetime import datetime
import queue
import asyncio
from dataclasses import dataclass
from typing import Optional, Dict, List
from components.ib_connection import (
    ib,
    define_stock_contract,
    get_delta,
)
from ib_insync import MarketOrder, Option, Stock
import nest_asyncio
nest_asyncio.apply()

@dataclass
class HedgeAlert:
    """Class for storing hedge alert information."""
    timestamp: str
    symbol: str
    action: str  # 'BUY' or 'SELL'
    quantity: int
    order_type: str
    status: str
    price: Optional[float] = None
    details: Optional[str] = None

# Dictionary to track hedger status for each product
hedger_status = {}
hedge_log = deque(maxlen=100)  # Keep last 100 log entries
command_queue = queue.Queue()
main_event_loop = None

# Queue for storing alerts
alert_queue = queue.Queue(maxsize=100)  # Store up to 100 alerts
recent_alerts = deque(maxlen=20)  # Keep last 20 alerts for display

# Track pending orders
pending_orders = {}

def log_message(message: str) -> None:
    """Log a message with timestamp."""
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted_message = f"{timestamp} - {message}"
    hedge_log.append(formatted_message)
    print(formatted_message)

def add_alert(alert: HedgeAlert) -> None:
    """Add a new alert to the queue and recent alerts."""
    try:
        alert_queue.put(alert, block=False)
        recent_alerts.append(alert)
    except queue.Full:
        log_message("Alert queue is full - oldest alert will be dropped")
        try:
            alert_queue.get_nowait()  # Remove oldest alert
            alert_queue.put(alert, block=False)
            recent_alerts.append(alert)
        except queue.Empty:
            pass

def get_recent_alerts() -> List[HedgeAlert]:
    """Get list of recent alerts."""
    return list(recent_alerts)

def get_or_create_event_loop():
    """Get or create an event loop."""
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

def has_pending_orders(symbol: str) -> bool:
    """Check if there are pending orders for a symbol."""
    try:
        # Clean up old pending orders
        current_orders = [o for o in ib.openTrades() if not o.isDone()]
        pending_orders[symbol] = [
            order for order in current_orders 
            if (order.contract.symbol == symbol and 
                order.orderStatus.status in ['Submitted', 'PreSubmitted'])
        ]
        return bool(pending_orders.get(symbol, []))
    except Exception as e:
        log_message(f"Error checking pending orders: {str(e)}")
        return False

def execute_trade(contract, order_qty, order_type='MKT'):
    """Execute a trade with the given parameters and create an alert."""
    try:
        # Check for pending orders
        if has_pending_orders(contract.symbol):
            log_message(f"Skipping trade - pending orders exist for {contract.symbol}")
            return False

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if order_qty > 0:
            order = MarketOrder('BUY', abs(order_qty))
            action = 'BUY'
        else:
            order = MarketOrder('SELL', abs(order_qty))
            action = 'SELL'

        log_message(f"Attempting to place order: {order_type} {order.action} {abs(order_qty)} {contract.symbol}")
        
        alert = HedgeAlert(
            timestamp=timestamp,
            symbol=contract.localSymbol if isinstance(contract, Option) else contract.symbol,
            action=action,
            quantity=abs(order_qty),
            order_type=order_type,
            status='PENDING'
        )
        add_alert(alert)
        
        trade = ib.placeOrder(contract, order)
        if not trade:
            alert.status = 'FAILED'
            alert.details = 'Failed to place order'
            add_alert(alert)
            log_message(f"Failed to place order for {contract.symbol}")
            return False

        # Wait for initial order status
        ib.sleep(1)

        order_status = trade.orderStatus.status
        if order_status in ['Submitted', 'PreSubmitted']:
            alert.status = 'PENDING'
            alert.details = f"Order pending: {order_status}"
            add_alert(alert)
            log_message(f"Order pending: {order_status}")
            return False
            
        elif order_status == 'Filled':
            alert.status = 'FILLED'
            alert.price = trade.orderStatus.avgFillPrice
            alert.details = f"Filled at {trade.orderStatus.avgFillPrice}"
            add_alert(alert)
            log_message(f"Order filled: {order_type} {order.action} {abs(order_qty)} {contract.symbol} at {trade.orderStatus.avgFillPrice}")
            return True
            
        else:
            alert.status = 'FAILED'
            alert.details = f"Order failed: {order_status}"
            add_alert(alert)
            log_message(f"Order failed: {order_status}")
            return False
            
    except Exception as e:
        error_msg = f"Error executing trade: {str(e)}"
        alert = HedgeAlert(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            symbol=contract.localSymbol if isinstance(contract, Option) else contract.symbol,
            action=action,
            quantity=abs(order_qty),
            order_type=order_type,
            status='ERROR',
            details=error_msg
        )
        add_alert(alert)
        log_message(error_msg)
        return False

def get_current_positions(position_key):
    """Get current positions for a position key."""
    try:
        positions = []
        all_positions = ib.positions()
        
        for pos in all_positions:
            identifier = pos.contract.localSymbol if isinstance(pos.contract, Option) else pos.contract.symbol
            if identifier == position_key:
                positions.append(pos)
                
        return positions
    except Exception as e:
        log_message(f"Error getting positions: {str(e)}")
        return []

def calculate_aggregate_delta(positions):
    """Calculate aggregate delta for given positions."""
    try:
        total_delta = 0
        for position in positions:
            if not position:
                continue
            delta = get_delta(position, ib)
            if delta is not None:
                total_delta += delta
        return total_delta
    except Exception as e:
        log_message(f"Error calculating aggregate delta: {str(e)}")
        return 0

def get_or_create_contract(position_key):
    """Get or create appropriate contract based on position key."""
    try:
        # Check if this is an option by looking for standard option format
        if any(x in position_key for x in ['C', 'P']) and any(c.isdigit() for c in position_key):
            # Parse option details from localSymbol
            parts = position_key.split()
            symbol = parts[0]
            expiry = parts[1]
            strike = float(parts[2])
            right = parts[3]
            
            contract = Option(symbol, expiry, strike, right, 'SMART')
            contract.currency = 'USD'
            contract.multiplier = '100'
            return contract
            
        else:
            # Create stock contract
            return define_stock_contract(position_key)
            
    except Exception as e:
        log_message(f"Error creating contract for {position_key}: {str(e)}")
        return None

def hedge_position(position_key, target_delta, delta_change_threshold, max_order_qty):
    """Hedge a position based on delta difference."""
    try:
        if position_key not in hedger_status or not hedger_status[position_key]:
            return

        if has_pending_orders(position_key.split()[0]):
            log_message(f"Skipping hedge - pending orders exist for {position_key}")
            return

        hedging_contract = get_or_create_contract(position_key)
        if not hedging_contract:
            log_message(f"Failed to create contract for {position_key}")
            return

        positions = get_current_positions(position_key)
        if not positions:
            log_message(f"No positions found for {position_key}")
            return
            
        current_delta = calculate_aggregate_delta(positions)
        
        log_message(f"Current aggregate delta for {position_key}: {current_delta:.2f}")
        log_message(f"Target delta: {target_delta}")
        
        delta_difference = target_delta - current_delta
        log_message(f"Delta difference for {position_key}: {delta_difference:.2f}")
        
        if abs(delta_difference) > delta_change_threshold:
            # For options, adjust order quantity based on contract delta
            if isinstance(hedging_contract, Option):
                # Get approximate contract delta
                contract_delta = 0.5 if hedging_contract.right == 'C' else -0.5
                order_qty = int(delta_difference / (contract_delta * 100))
            else:
                # For stocks, delta difference is directly share quantity
                order_qty = int(delta_difference)
            
            # Limit order quantity
            if abs(order_qty) > max_order_qty:
                order_qty = max_order_qty if order_qty > 0 else -max_order_qty
            
            if order_qty != 0:
                log_message(f"Placing order for {order_qty} {'contracts' if isinstance(hedging_contract, Option) else 'shares'} of {position_key}")
                success = execute_trade(hedging_contract, order_qty)
                if success:
                    log_message(f"Successfully hedged {position_key}")
                else:
                    log_message(f"Failed to hedge {position_key}")
            
    except Exception as e:
        log_message(f"Error in hedge_position: {str(e)}")

def run_auto_hedger(position_key, target_delta, delta_change_threshold, max_order_qty):
    """Function for auto hedging."""
    global main_event_loop
    try:
        loop = get_or_create_event_loop()
        if main_event_loop is None:
            main_event_loop = loop

        log_message(f"**** Auto-Hedger started for {position_key} ****")
        while hedger_status.get(position_key, False):
            try:
                hedge_position(position_key, target_delta, delta_change_threshold, max_order_qty)
                ib.sleep(5)  # Wait before next check
            except Exception as e:
                log_message(f"Error in hedging cycle: {str(e)}")
                ib.sleep(5)  # Wait before retrying
            
    except Exception as e:
        log_message(f"Error in auto_hedger_thread: {str(e)}")
    finally:
        hedger_status[position_key] = False
        log_message(f"Auto-Hedger stopped for {position_key}")

def start_auto_hedger(position_key, target_delta, delta_change_threshold, max_order_qty):
    """Start the auto hedger for a specific position."""
    try:
        if not position_key:
            log_message("No position key provided")
            return False
            
        if position_key in hedger_status and hedger_status[position_key]:
            log_message(f"Auto-Hedger already running for {position_key}")
            return False
            
        hedger_status[position_key] = True
        
        thread = threading.Thread(
            target=run_auto_hedger,
            args=(position_key, target_delta, delta_change_threshold, max_order_qty),
            daemon=True
        )
        thread.start()
        
        log_message(f"Auto-Hedger started for {position_key}")
        return True
    except Exception as e:
        log_message(f"Error starting auto-hedger: {str(e)}")
        return False

def stop_auto_hedger(position_key=None):
    """Stop the auto hedger for a specific position or all positions."""
    try:
        if position_key:
            if position_key in hedger_status:
                hedger_status[position_key] = False
                log_message(f"Stopping Auto-Hedger for {position_key}")
        else:
            for key in hedger_status:
                hedger_status[key] = False
            log_message("Stopping all Auto-Hedgers")
    except Exception as e:
        log_message(f"Error stopping auto-hedger: {str(e)}")

def is_hedger_running(position_key=None):
    """Check if auto hedger is running for a specific position or any position."""
    if position_key:
        return hedger_status.get(position_key, False)
    return any(hedger_status.values())

def get_hedge_log():
    """Get the hedge log entries."""
    return list(hedge_log)
