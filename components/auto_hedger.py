from ib_insync import Stock, MarketOrder, LimitOrder
from components.ib_connection import ib, define_stock_contract, fetch_market_data_for_stock, get_delta
import asyncio
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

is_running = False
hedge_log = []
hedge_thread = None

async def monitor_and_hedge(stock_symbol, target_delta, delta_change, max_order_qty):
    global is_running, hedge_log
    is_running = True

    stock_contract = define_stock_contract(stock_symbol)

    try:
        await ib.qualifyContractsAsync(stock_contract)
        hedge_log.append(f"Qualified contract for {stock_symbol}")
    except Exception as e:
        hedge_log.append(f"Failed to qualify contract for {stock_symbol}: {e}")
        return

    while is_running:
        try:
            # Fetch current positions
            positions = await ib.reqPositionsAsync()
            aggregate_delta = sum([get_delta(p.contract) for p in positions if p.contract.symbol == stock_symbol])

            # Calculate delta difference
            delta_diff = target_delta - aggregate_delta
            hedge_log.append(f"Delta difference for {stock_symbol}: {delta_diff}")

            if abs(delta_diff) > delta_change:
                hedge_qty = min(abs(delta_diff), max_order_qty)

                # Fetch market data before placing an order
                market_data = await fetch_market_data_for_stock(stock_contract)
                if not market_data:
                    hedge_log.append(f"Unable to fetch market data for {stock_symbol}. Skipping hedging.")
                    continue

                # Place order based on delta difference
                order = MarketOrder('BUY' if delta_diff > 0 else 'SELL', hedge_qty)
                trade = ib.placeOrder(stock_contract, order)
                hedge_log.append(f"Placed order: {trade}")
            else:
                hedge_log.append(f"No hedging needed. Delta difference {delta_diff} is below threshold {delta_change}.")

        except Exception as e:
            hedge_log.append(f"Error during hedging for {stock_symbol}: {e}")

        await asyncio.sleep(60)  # Wait before the next iteration

    hedge_log.append("Auto-Hedger has been stopped.")

def stop_auto_hedger():
    global is_running, hedge_thread
    is_running = False  # Signal to stop the hedging loop
    print("**** Auto-Hedger stop signal received ****")
    logger.info("Auto-Hedger stop signal received.")

    if hedge_thread and hedge_thread.is_alive():
        hedge_thread.join(timeout=65)  # Wait for the thread to finish
        if hedge_thread.is_alive():
            logger.warning("Auto-Hedger thread did not stop in time. Forcing termination.")
        else:
            logger.info("Auto-Hedger has stopped successfully.")
    else:
        logger.info("Auto-Hedger is not running.")

def start_auto_hedger(stock_symbol, target_delta, delta_change, max_order_qty):
    print("**** Auto-Hedger started for {stock_symbol} ****")
    global hedge_log, hedge_thread, is_running
    hedge_log = []
    is_running = True
    
    def run_hedger():
        asyncio.run(monitor_and_hedge(stock_symbol, target_delta, delta_change, max_order_qty))
    
    hedge_thread = threading.Thread(target=run_hedger)
    hedge_thread.start()

def get_hedge_log():
    global hedge_log
    return hedge_log

def is_hedger_running():
    global is_running, hedge_thread
    return is_running and hedge_thread and hedge_thread.is_alive()
