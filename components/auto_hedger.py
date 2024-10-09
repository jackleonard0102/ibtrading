from ib_insync import Stock, MarketOrder, LimitOrder
from components.ib_connection import ib
import asyncio
import logging
import threading

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

is_running = False
hedge_log = []
hedge_thread = None

async def monitor_and_hedge(stock_symbol, target_delta, delta_change, max_order_qty):
    """
    Monitor the aggregate delta for the selected stock position and hedge as needed.
    """
    global is_running, hedge_log
    is_running = True
    stock = Stock(stock_symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(stock)

    log_message = f"Starting auto-hedger for {stock_symbol}. Target delta: {target_delta}, Delta change threshold: {delta_change}, Max order quantity: {max_order_qty}"
    logger.info(log_message)
    hedge_log.append(log_message)

    # Check if we're using a paper trading account
    account_summary = await ib.accountSummaryAsync()
    is_paper_account = any(item.value == 'PAPERTRADER' for item in account_summary if item.tag == 'AccountType')

    while is_running:
        try:
            positions = await ib.reqPositionsAsync()
            aggregate_delta = sum([p.position for p in positions if p.contract.symbol == stock_symbol])

            log_message = f"Current aggregate delta for {stock_symbol}: {aggregate_delta}"
            logger.info(log_message)
            hedge_log.append(log_message)

            delta_diff = target_delta - aggregate_delta
            log_message = f"Delta difference: {delta_diff}"
            logger.info(log_message)
            hedge_log.append(log_message)

            if abs(delta_diff) > delta_change:
                hedge_qty = min(abs(delta_diff), max_order_qty)
                
                if is_paper_account:
                    # For paper trading, use a LimitOrder with the current market price
                    ticker = await ib.reqTickersAsync(stock)
                    if ticker and ticker[0].marketPrice():
                        price = ticker[0].marketPrice()
                        order = LimitOrder('BUY' if delta_diff > 0 else 'SELL', hedge_qty, price)
                    else:
                        log_message = f"Unable to get market price for {stock_symbol}. Skipping order placement."
                        logger.warning(log_message)
                        hedge_log.append(log_message)
                        continue
                else:
                    # For live trading, use a MarketOrder
                    order = MarketOrder('BUY' if delta_diff > 0 else 'SELL', hedge_qty)

                trade = ib.placeOrder(stock, order)
                log_message = f"Placed {'limit' if is_paper_account else 'market'} order to {'buy' if delta_diff > 0 else 'sell'} {hedge_qty} shares of {stock_symbol}"
                logger.info(log_message)
                hedge_log.append(log_message)
                
                fill_status = await trade.fillEvent
                log_message = f"Order filled: {fill_status}"
                logger.info(log_message)
                hedge_log.append(log_message)
            else:
                log_message = f"No hedging action needed at this time. Delta difference ({delta_diff}) is not greater than threshold ({delta_change})."
                logger.info(log_message)
                hedge_log.append(log_message)

        except Exception as e:
            log_message = f"An error occurred during hedging: {e}"
            logger.error(log_message)
            hedge_log.append(log_message)

        await asyncio.sleep(60)

    log_message = "Auto-Hedger has been stopped."
    logger.info(log_message)
    hedge_log.append(log_message)

def stop_auto_hedger():
    """
    Stops the auto-hedger by setting the is_running flag to False.
    """
    global is_running, hedge_thread
    is_running = False
    log_message = "Auto-Hedger stop signal received. It will stop after the current iteration."
    logger.info(log_message)
    hedge_log.append(log_message)
    
    if hedge_thread:
        hedge_thread.join(timeout=65)  # Wait for up to 65 seconds (slightly more than the sleep time in the loop)
        if hedge_thread.is_alive():
            log_message = "Auto-Hedger thread did not stop in time. Forcing termination."
            logger.warning(log_message)
            hedge_log.append(log_message)
            # Here you might want to implement a more forceful termination if needed

def start_auto_hedger(stock_symbol, target_delta, delta_change, max_order_qty):
    """
    Starts the auto-hedger by running the monitor_and_hedge function.
    """
    global hedge_log, hedge_thread, is_running
    hedge_log = []
    is_running = True
    
    def run_hedger():
        asyncio.run(monitor_and_hedge(stock_symbol, target_delta, delta_change, max_order_qty))
    
    hedge_thread = threading.Thread(target=run_hedger)
    hedge_thread.start()

def get_hedge_log():
    """
    Returns the current hedge log.
    """
    global hedge_log
    return hedge_log

def is_hedger_running():
    """
    Returns the current status of the auto-hedger.
    """
    global is_running, hedge_thread
    return is_running and hedge_thread and hedge_thread.is_alive()
