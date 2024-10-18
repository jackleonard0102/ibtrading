# auto_hedger.py
from ib_insync import Stock, MarketOrder
from components.ib_connection import ib, define_stock_contract, get_portfolio_positions, get_delta
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

is_running = False
hedge_log = []

def start_auto_hedger(stock_symbol, target_delta, delta_change, max_order_qty):
    print(f"**** Auto-Hedger started for {stock_symbol} ****")
    global hedge_log, is_running
    hedge_log = []
    is_running = True

    def monitor_and_hedge():
        stock_contract = define_stock_contract(stock_symbol)
        try:
            ib.qualifyContracts(stock_contract)
            hedge_log.append(f"Qualified contract for {stock_symbol}")
        except Exception as e:
            hedge_log.append(f"Failed to qualify contract for {stock_symbol}: {e}")
            is_running = False
            return

        while is_running:
            try:
                # Fetch current positions
                positions = ib.positions()
                positions = [p for p in positions if p.contract.symbol == stock_symbol]
                aggregate_delta = sum([get_delta(p) for p in positions])

                # Calculate delta difference
                delta_diff = target_delta - aggregate_delta
                hedge_log.append(f"Delta difference for {stock_symbol}: {delta_diff}")

                if abs(delta_diff) > delta_change:
                    hedge_qty = min(abs(delta_diff), max_order_qty)
                    hedge_qty = int(hedge_qty)

                    # Place order based on delta difference
                    order_action = 'BUY' if delta_diff > 0 else 'SELL'
                    order = MarketOrder(order_action, hedge_qty)
                    trade = ib.placeOrder(stock_contract, order)
                    hedge_log.append(f"Placed order: {order_action} {hedge_qty} shares of {stock_symbol}")
                else:
                    hedge_log.append(f"No hedging needed. Delta difference {delta_diff} is below threshold {delta_change}.")

            except Exception as e:
                hedge_log.append(f"Error during hedging for {stock_symbol}: {e}")

            ib.sleep(60)  # Wait before the next iteration

        hedge_log.append("Auto-Hedger has been stopped.")

    # Schedule the monitor_and_hedge function to run in the event loop
    ib.schedule(monitor_and_hedge)

def stop_auto_hedger():
    global is_running
    is_running = False  # Signal to stop the hedging loop
    print("**** Auto-Hedger stop signal received ****")
    logger.info("Auto-Hedger stop signal received.")
    hedge_log.append("Auto-Hedger has been stopped.")

def get_hedge_log():
    global hedge_log
    return hedge_log

def is_hedger_running():
    global is_running
    return is_running
