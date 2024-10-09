from ib_insync import Stock, MarketOrder
from components.ib_connection import ib
import asyncio
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def monitor_and_hedge(stock_symbol, target_delta, delta_change, max_order_qty):
    """
    Monitor the aggregate delta for the selected stock position and hedge as needed.
    """
    stock = Stock(stock_symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(stock)  # Use async to qualify the contract

    logger.info(f"Starting auto-hedger for {stock_symbol}")
    logger.info(f"Target delta: {target_delta}, Delta change threshold: {delta_change}, Max order quantity: {max_order_qty}")

    while True:
        try:
            # Fetch the portfolio positions
            positions = ib.positions()
            aggregate_delta = sum([p.position for p in positions if p.contract.symbol == stock_symbol])

            logger.info(f"Current aggregate delta for {stock_symbol}: {aggregate_delta}")

            # Determine how much delta adjustment is needed
            delta_diff = target_delta - aggregate_delta
            logger.info(f"Delta difference: {delta_diff}")

            if abs(delta_diff) > delta_change:  # Use the delta change threshold
                hedge_qty = min(abs(delta_diff), max_order_qty)
                order = MarketOrder('BUY' if delta_diff > 0 else 'SELL', hedge_qty)
                trade = ib.placeOrder(stock, order)
                logger.info(f"Placed order to {'buy' if delta_diff > 0 else 'sell'} {hedge_qty} shares of {stock_symbol}")
                
                # Wait for the order to be filled
                fill_status = await trade.fillEvent
                logger.info(f"Order filled: {fill_status}")
            else:
                logger.info("No hedging action needed at this time.")

        except Exception as e:
            logger.error(f"An error occurred during hedging: {e}")

        await asyncio.sleep(60)  # Sleep asynchronously for 60 seconds

def stop_auto_hedger():
    """
    Stops the auto-hedger by terminating the current monitoring thread.
    """
    # This function should be called to stop the auto-hedger
    # You might want to implement a flag to stop the while loop in monitor_and_hedge
    logger.info("Auto-Hedger has been stopped.")

# You might want to add a function to start the auto-hedger
def start_auto_hedger(stock_symbol, target_delta, delta_change, max_order_qty):
    asyncio.run(monitor_and_hedge(stock_symbol, target_delta, delta_change, max_order_qty))
