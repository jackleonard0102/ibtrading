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
        order_statuses = ['Submitted', 'PreSubmitted', 'PendingSubmit']
        # Get all open trades
        current_orders = ib.openTrades()
        pending = []
        
        for trade in current_orders:
            if trade.orderStatus.status in order_statuses:
                contract = trade.contract
                # For options, match by localSymbol
                if isinstance(contract, Option) and contract.localSymbol == symbol:
                    pending.append(trade)
                # For stocks, match by symbol
                elif contract.symbol == symbol:
                    pending.append(trade)
                    
        pending_orders[symbol] = pending
        has_pending = bool(pending)
        if has_pending:
            log_message(f"Found pending orders for {symbol}: {[t.orderStatus.status for t in pending]}")
        return has_pending
        
    except Exception as e:
        log_message(f"Error checking pending orders: {str(e)}")
        return False

def execute_trade(contract, order_qty, order_type='MKT'):
    """Execute a trade with the given parameters and create an alert."""
    try:
        # For options, check pending orders by localSymbol
        check_symbol = contract.localSymbol if isinstance(contract, Option) else contract.symbol
        if has_pending_orders(check_symbol):
            log_message(f"Skipping trade - pending orders exist for {check_symbol}")
            return False

        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        if order_qty > 0:
            order = MarketOrder('BUY', abs(order_qty))
            action = 'BUY'
        else:
            order = MarketOrder('SELL', abs(order_qty))
            action = 'SELL'

        identifier = contract.localSymbol if isinstance(contract, Option) else contract.symbol
        log_message(f"Attempting to place order: {order_type} {order.action} {abs(order_qty)} {identifier}")
        
        alert = HedgeAlert(
            timestamp=timestamp,
            symbol=identifier,
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
            log_message(f"Failed to place order for {identifier}")
            return False

        # Wait for initial order status
        ib.sleep(1)

        order_status = trade.orderStatus.status
        if order_status in ['Submitted', 'PreSubmitted', 'PendingSubmit']:
            alert.status = 'PENDING'
            alert.details = f"Order pending: {order_status}"
            add_alert(alert)
            log_message(f"Order pending: {order_status}")
            # Consider pending orders as "success" to prevent duplicate orders
            return True
            
        elif order_status == 'Filled':
            alert.status = 'FILLED'
            alert.price = trade.orderStatus.avgFillPrice
            alert.details = f"Filled at {trade.orderStatus.avgFillPrice}"
            add_alert(alert)
            log_message(f"Order filled: {order_type} {order.action} {abs(order_qty)} {identifier} at {trade.orderStatus.avgFillPrice}")
            return True
            
        else:
            alert.status = 'FAILED'
            alert.details = f"Order failed: {order_status}"
            add_alert(alert)
            log_message(f"Order failed: {order_status}")
            return False
            
    except Exception as e:
        error_msg = f"Error executing trade: {str(e)}"
        identifier = contract.localSymbol if isinstance(contract, Option) else contract.symbol
        alert = HedgeAlert(
            timestamp=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            symbol=identifier,
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

def parse_option_symbol(symbol: str) -> dict:
    """Parse option symbol into components."""
    try:
        # Expected format: "QQQ   241101P00498000"
        # Remove extra spaces but keep at least one space
        parts = " ".join(symbol.split()).split()
        underlying = parts[0]  # 'QQQ'
        
        if len(parts) < 2:
            raise ValueError("Invalid option symbol format")
            
        date_str = parts[1][:6]  # '241101'
        year = "20" + date_str[:2]
        month = date_str[2:4]
        day = date_str[4:6]
        
        # Extract right and strike
        detail = parts[1][6:]  # 'P00498000'
        right = detail[0]  # 'P' or 'C'
        strike = float(detail[1:]) / 1000.0  # '00498000' -> 498.0
        
        return {
            'symbol': underlying,
            'lastTradeDateOrContractMonth': f"{year}{month}{day}",
            'strike': strike,
            'right': right,
            'exchange': 'SMART',
            'currency': 'USD',
            'multiplier': '100'
        }
    except Exception as e:
        log_message(f"Error parsing option symbol {symbol}: {str(e)}")
        return None

def create_contract_from_key(position_key: str):
    """Create appropriate contract based on position key."""
    try:
        # Check if this is an option by looking for standard option format
        if 'C' in position_key or 'P' in position_key:
            option_data = parse_option_symbol(position_key)
            if option_data:
                contract = Option(**option_data)
                # Set primary exchange for options
                contract.primaryExchange = 'AMEX'
                log_message(f"Created option contract for {position_key}")
                return contract
        else:
            # Create stock contract
            contract = define_stock_contract(position_key)
            log_message(f"Created stock contract for {position_key}")
            return contract
            
    except Exception as e:
        log_message(f"Error creating contract for {position_key}: {str(e)}")
        return None

def hedge_position(position_key, target_delta, delta_change_threshold, max_order_qty):
    """Hedge a position based on delta difference."""
    try:
        if position_key not in hedger_status or not hedger_status[position_key]:
            return

        # Create appropriate contract
        if 'C' in position_key or 'P' in position_key:
            # Option contract
            hedging_contract = create_contract_from_key(position_key)
        else:
            # Stock contract - don't try to parse as option
            hedging_contract = define_stock_contract(position_key)
            
        if not hedging_contract:
            log_message(f"Failed to create contract for {position_key}")
            return

        # Get current positions
        positions = get_current_positions(position_key)
        if not positions:
            log_message(f"No positions found for {position_key}")
            return

        # Check for open orders AFTER validating position exists
        if has_pending_orders(position_key):
            log_message(f"Skipping hedge - pending orders exist for {position_key}")
            return
            
        current_delta = sum(get_delta(pos, ib) for pos in positions)
        
        log_message(f"Current aggregate delta for {position_key}: {current_delta:.2f}")
        log_message(f"Target delta: {target_delta}")
        
        delta_difference = target_delta - current_delta
        log_message(f"Delta difference for {position_key}: {delta_difference:.2f}")
        
        # Only hedge if delta difference exceeds threshold
        if abs(delta_difference) > delta_change_threshold:
            if isinstance(hedging_contract, Option):
                # For options, adjust order quantity based on contract delta and multiplier
                multiplier = float(hedging_contract.multiplier) if hasattr(hedging_contract, "multiplier") else 100.0
                contract_delta = 0.5 if hedging_contract.right == 'C' else -0.5
                # Convert position delta to contract quantity
                order_qty = int(delta_difference / (contract_delta * multiplier))
                log_message(f"Option order calculation: delta_diff={delta_difference:.2f}, contract_delta={contract_delta}, multiplier={multiplier}")
                log_message(f"Calculated option order quantity: {order_qty} contracts")
            else:
                # For stocks, just use delta difference directly
                order_qty = int(delta_difference)
                log_message(f"Stock order calculation: delta_diff={delta_difference:.2f}")
                log_message(f"Calculated stock order quantity: {order_qty} shares")
            
            # Apply max order limit if needed
            original_qty = order_qty
            if abs(order_qty) > max_order_qty:
                order_qty = max_order_qty if order_qty > 0 else -max_order_qty
                log_message(f"Order quantity adjusted from {original_qty} to {order_qty} due to max order limit")
            
            if order_qty != 0:
                identifier = hedging_contract.localSymbol if isinstance(hedging_contract, Option) else hedging_contract.symbol
                instrument_type = 'contracts' if isinstance(hedging_contract, Option) else 'shares'
                
                # Log full order details
                direction = "BUY" if order_qty > 0 else "SELL"
                log_message(f"Preparing order: {direction} {abs(order_qty)} {instrument_type} of {identifier}")
                
                success = execute_trade(hedging_contract, order_qty)
                if success:
                    log_message(f"Successfully placed hedge order for {identifier}")
                else:
                    log_message(f"Failed to place hedge order for {identifier}")
            else:
                log_message("Calculated order quantity is zero, skipping trade")
        else:
            log_message(f"Delta difference {delta_difference:.2f} within threshold {delta_change_threshold}, no hedge needed")
            
    except Exception as e:
        log_message(f"Error in hedge_position: {str(e)}")
        log_message(f"Exception details: {str(e.__class__.__name__)}: {str(e)}")

def run_auto_hedger(position_key, target_delta, delta_change_threshold, max_order_qty):
    """Function for auto hedging."""
    global main_event_loop
    try:
        loop = get_or_create_event_loop()
        if main_event_loop is None:
            main_event_loop = loop

        log_message(f"**** Auto-Hedger started for {position_key} ****")
        log_message(f"Parameters: target_delta={target_delta}, threshold={delta_change_threshold}, max_qty={max_order_qty}")
        
        error_count = 0
        max_errors = 3  # Maximum consecutive errors before stopping
        
        while hedger_status.get(position_key, False):
            try:
                # Try to hedge
                hedge_position(position_key, target_delta, delta_change_threshold, max_order_qty)
                error_count = 0  # Reset error count on success
                
                # Sleep before next check
                log_message("Waiting 5 seconds before next hedge check...")
                ib.sleep(5)
                
            except Exception as e:
                error_count += 1
                log_message(f"Error in hedging cycle: {str(e)}")
                if error_count >= max_errors:
                    log_message(f"Stopping auto-hedger after {max_errors} consecutive errors")
                    break
                ib.sleep(5)  # Wait before retrying
            
    except Exception as e:
        log_message(f"Fatal error in auto_hedger_thread: {str(e)}")
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
