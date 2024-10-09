from ib_insync import Stock, MarketOrder
from components.ib_connection import ib
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

is_running = False
hedge_log = []

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

    while is_running:
        try:
            positions = ib.positions()
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
                order = MarketOrder('BUY' if delta_diff > 0 else 'SELL', hedge_qty)
                trade = ib.placeOrder(stock, order)
                log_message = f"Placed order to {'buy' if delta_diff > 0 else 'sell'} {hedge_qty} shares of {stock_symbol}"
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
    global is_running
    is_running = False
    log_message = "Auto-Hedger stop signal received. It will stop after the current iteration."
    logger.info(log_message)
    hedge_log.append(log_message)

def start_auto_hedger(stock_symbol, target_delta, delta_change, max_order_qty):
    """
    Starts the auto-hedger by running the monitor_and_hedge function.
    """
    global hedge_log
    hedge_log = []
    asyncio.run(monitor_and_hedge(stock_symbol, target_delta, delta_change, max_order_qty))

def get_hedge_log():
    """
    Returns the current hedge log.
    """
    global hedge_log
    return hedge_log
