# auto_hedger.py
import threading
import queue
from ib_insync import Stock, MarketOrder
from components.ib_connection import define_stock_contract, get_delta
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

is_running = False
hedge_log = []
hedge_thread = None
command_queue = queue.Queue()
hedge_configs = {}

def start_auto_hedger(stock_symbol, target_delta, delta_change, max_order_qty, selected_positions):
    global hedge_log, is_running, hedge_thread
    print(f"**** Auto-Hedger started for {stock_symbol} ****")
    hedge_log = []
    is_running = True
    hedge_configs[stock_symbol] = {
        "target_delta": target_delta,
        "delta_change": delta_change,
        "max_order_qty": max_order_qty,
        "selected_positions": selected_positions
    }

    def monitor_and_hedge():
        global is_running
        stock_contract = define_stock_contract(stock_symbol)
        command_queue.put(('qualify_contract', stock_contract))

        while is_running:
            try:
                command_queue.put(('get_positions', stock_symbol))
                time.sleep(0.1)  # Wait for the main thread to process the command
                positions = command_queue.get()
                if not isinstance(positions, list):
                    print(f"Unexpected response for get_positions: {positions}")
                    continue
                
                command_queue.put(('get_deltas', positions))
                time.sleep(0.1)  # Wait for the main thread to process the command
                deltas = command_queue.get()
                if not isinstance(deltas, list):
                    print(f"Unexpected response for get_deltas: {deltas}")
                    continue
                
                # Ensure all deltas are float values
                try:
                    deltas = [float(delta) for delta in deltas]
                except ValueError as e:
                    print(f"Error converting deltas to float: {e}")
                    continue

                aggregate_delta = sum(deltas)

                message = f"Current positions for {stock_symbol}: {positions}"
                hedge_log.append(message)
                print(message)
                message = f"Aggregate delta for {stock_symbol}: {aggregate_delta:.2f}"
                hedge_log.append(message)
                print(message)

                delta_diff = float(target_delta) - aggregate_delta
                message = f"Delta difference for {stock_symbol}: {delta_diff:.2f}"
                hedge_log.append(message)
                print(message)

                if abs(delta_diff) > float(delta_change):
                    hedge_qty = min(abs(delta_diff), float(max_order_qty))
                    hedge_qty = int(hedge_qty)

                    order_action = 'BUY' if delta_diff > 0 else 'SELL'
                    order = MarketOrder(order_action, hedge_qty)
                    command_queue.put(('place_order', stock_contract, order))
                    time.sleep(0.1)  # Wait for the main thread to process the command
                    trade_status = command_queue.get()

                    message = f"Placed order: {order_action} {hedge_qty} shares of {stock_symbol}"
                    hedge_log.append(message)
                    print(message)
                    message = f"Order status: {trade_status}"
                    hedge_log.append(message)
                    print(message)

                    if trade_status == 'Rejected':
                        message = f"Order rejected: {trade_status}"
                        hedge_log.append(message)
                        print(message)
                else:
                    message = f"No hedging needed. Delta difference {delta_diff:.2f} is below threshold {delta_change}."
                    hedge_log.append(message)
                    print(message)

            except Exception as e:
                message = f"Error during hedging for {stock_symbol}: {e}"
                hedge_log.append(message)
                print(message)

            time.sleep(60)  # Wait before the next iteration

        message = "Auto-Hedger has been stopped."
        hedge_log.append(message)
        print(message)

    hedge_thread = threading.Thread(target=monitor_and_hedge)
    hedge_thread.start()

def stop_auto_hedger():
    global is_running, hedge_thread
    is_running = False
    print("**** Auto-Hedger stop signal received ****")
    logger.info("Auto-Hedger stop signal received.")
    if hedge_thread and hedge_thread.is_alive():
        hedge_thread.join()
        hedge_thread = None
        logger.info("Auto-Hedger has stopped successfully.")

def get_hedge_log():
    global hedge_log
    return hedge_log

def is_hedger_running():
    global is_running, hedge_thread
    return is_running and hedge_thread is not None and hedge_thread.is_alive()

def get_command():
    return command_queue.get() if not command_queue.empty() else None
