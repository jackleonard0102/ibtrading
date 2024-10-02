import time
from ib_insync import Stock, MarketOrder
from components.ib_connection import ib
import asyncio

async def monitor_and_hedge(stock_symbol, target_delta, max_order_qty):
    """
    Monitor the aggregate delta for the selected stock position and hedge as needed.
    """
    stock = Stock(stock_symbol, 'SMART', 'USD')
    await ib.qualifyContractsAsync(stock)  # Use async to qualify the contract

    while True:
        # Fetch the portfolio positions
        positions = ib.positions()
        aggregate_delta = sum([p.position for p in positions if p.contract.symbol == stock_symbol])

        # Determine how much delta adjustment is needed
        delta_diff = target_delta - aggregate_delta
        if abs(delta_diff) > 50:  # Threshold to trigger a hedge
            hedge_qty = min(abs(delta_diff), max_order_qty)
            order = MarketOrder('BUY' if delta_diff > 0 else 'SELL', hedge_qty)
            trade = ib.placeOrder(stock, order)
            print(f"Hedged {hedge_qty} shares of {stock_symbol}")

        await asyncio.sleep(60)  # Sleep asynchronously for 60 seconds
