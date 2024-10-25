from collections import deque
import threading
from datetime import datetime
import queue
import asyncio
from components.ib_connection import (
    ib,
    define_stock_contract,
    get_delta,
)
from ib_insync import MarketOrder
import nest_asyncio
nest_asyncio.apply()

# Dictionary to track hedger status for each product
hedger_status = {}
hedge_log = deque(maxlen=100)  # Keep last 100 log entries
command_queue = queue.Queue()
main_event_loop = None

def log_message(message):
    timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    formatted_message = f"{timestamp} - {message}"
    hedge_log.append(formatted_message)
    print(formatted_message)

def get_or_create_event_loop():
    try:
        return asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        return loop

def execute_trade(stock_contract, order_qty, order_type='MKT'):
    """Execute a trade with the given parameters"""
    try:
        if order_qty > 0:
            order = MarketOrder('BUY', abs(order_qty))
        else:
            order = MarketOrder('SELL', abs(order_qty))

        log_message(f"Attempting to place order: {order_type} {order.action} {abs(order_qty)} {stock_contract.symbol}")
        
        trade = ib.placeOrder(stock_contract, order)
        if not trade:
            log_message(f"Failed to place order for {stock_contract.symbol}")
            return False

        # Wait for the trade to complete
        while not trade.isDone():
            ib.sleep(0.1)
            
        if trade.orderStatus.status == 'Filled':
            log_message(f"Order filled: {order_type} {order.action} {abs(order_qty)} {stock_contract.symbol} at {trade.orderStatus.avgFillPrice}")
            return True
        else:
            log_message(f"Order failed: {trade.orderStatus.status}")
            return False
            
    except Exception as e:
        log_message(f"Error executing trade: {str(e)}")
        return False

def get_current_positions(stock_symbol):
    """Get current positions for a stock symbol"""
    try:
        positions = [p for p in ib.positions() if p.contract.symbol == stock_symbol]
        return positions
    except Exception as e:
        log_message(f"Error getting positions: {str(e)}")
        return []

def calculate_aggregate_delta(positions):
    """Calculate aggregate delta for given positions"""
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

def hedge_position(stock_symbol, target_delta, delta_change_threshold, max_order_qty):
    """Hedge a position based on delta difference"""
    try:
        if stock_symbol not in hedger_status or not hedger_status[stock_symbol]:
            return

        stock_contract = define_stock_contract(stock_symbol)
        if not stock_contract:
            log_message(f"Failed to create stock contract for {stock_symbol}")
            return

        positions = get_current_positions(stock_symbol)
        if not positions:
            log_message(f"No positions found for {stock_symbol}")
            return
            
        current_delta = calculate_aggregate_delta(positions)
        
        log_message(f"Current aggregate delta for {stock_symbol}: {current_delta:.2f}")
        log_message(f"Target delta: {target_delta}")
        
        delta_difference = target_delta - current_delta
        log_message(f"Delta difference for {stock_symbol}: {delta_difference:.2f}")
        
        if abs(delta_difference) > delta_change_threshold:
            # Calculate the number of shares needed to adjust delta
            order_qty = int(delta_difference)
            
            # Limit order quantity to max_order_qty
            if abs(order_qty) > max_order_qty:
                order_qty = max_order_qty if order_qty > 0 else -max_order_qty
            
            if order_qty != 0:
                log_message(f"Placing order for {order_qty} shares of {stock_symbol}")
                success = execute_trade(stock_contract, order_qty)
                if success:
                    log_message(f"Successfully hedged {stock_symbol}")
                else:
                    log_message(f"Failed to hedge {stock_symbol}")
            
    except Exception as e:
        log_message(f"Error in hedge_position: {str(e)}")

def run_auto_hedger(stock_symbol, target_delta, delta_change_threshold, max_order_qty):
    """Function for auto hedging"""
    global main_event_loop
    try:
        # Ensure we have an event loop
        loop = get_or_create_event_loop()
        if main_event_loop is None:
            main_event_loop = loop

        log_message(f"**** Auto-Hedger started for {stock_symbol} ****")
        while hedger_status.get(stock_symbol, False):
            try:
                hedge_position(stock_symbol, target_delta, delta_change_threshold, max_order_qty)
                ib.sleep(5)  # Wait before next check
            except Exception as e:
                log_message(f"Error in hedging cycle: {str(e)}")
                ib.sleep(5)  # Wait before retrying
            
    except Exception as e:
        log_message(f"Error in auto_hedger_thread: {str(e)}")
    finally:
        hedger_status[stock_symbol] = False
        log_message(f"Auto-Hedger stopped for {stock_symbol}")

def start_auto_hedger(stock_symbol, target_delta, delta_change_threshold, max_order_qty):
    """Start the auto hedger for a specific symbol"""
    try:
        if not stock_symbol:
            log_message("No stock symbol provided")
            return False
            
        if stock_symbol in hedger_status and hedger_status[stock_symbol]:
            log_message(f"Auto-Hedger already running for {stock_symbol}")
            return False
            
        hedger_status[stock_symbol] = True
        
        # Start the auto hedger in a new thread
        thread = threading.Thread(
            target=run_auto_hedger,
            args=(stock_symbol, target_delta, delta_change_threshold, max_order_qty),
            daemon=True
        )
        thread.start()
        
        log_message(f"Auto-Hedger started for {stock_symbol}")
        return True
    except Exception as e:
        log_message(f"Error starting auto-hedger: {str(e)}")
        return False

def stop_auto_hedger(stock_symbol=None):
    """Stop the auto hedger for a specific symbol or all symbols"""
    try:
        if stock_symbol:
            if stock_symbol in hedger_status:
                hedger_status[stock_symbol] = False
                log_message(f"Stopping Auto-Hedger for {stock_symbol}")
        else:
            for symbol in hedger_status:
                hedger_status[symbol] = False
            log_message("Stopping all Auto-Hedgers")
    except Exception as e:
        log_message(f"Error stopping auto-hedger: {str(e)}")

def is_hedger_running(stock_symbol=None):
    """Check if auto hedger is running for a specific symbol or any symbol"""
    if stock_symbol:
        return hedger_status.get(stock_symbol, False)
    return any(hedger_status.values())

def get_hedge_log():
    """Get the hedge log entries"""
    return list(hedge_log)
