from ib_insync import Stock, MarketOrder, IB

ib = IB()

def auto_hedger(target_delta, stock_symbol='QQQ'):
    stock = Stock(stock_symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)

    positions = ib.positions()
    aggregate_delta = sum([p.position for p in positions if p.contract.symbol == stock_symbol])

    delta_diff = target_delta - aggregate_delta
    if abs(delta_diff) > 50:  # Threshold
        order = MarketOrder('BUY' if delta_diff > 0 else 'SELL', abs(delta_diff))
        trade = ib.placeOrder(stock, order)
        print(f"Hedged {delta_diff} shares of {stock_symbol}")
