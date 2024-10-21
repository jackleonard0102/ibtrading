from ib_insync import IB, Stock, MarketOrder

ib = IB()
ib.connect('127.0.0.1', 7497, clientId=2)  # Use a different clientId

contract = Stock('AMZN', 'SMART', 'USD')
ib.qualifyContracts(contract)

order = MarketOrder('BUY', 1)
trade = ib.placeOrder(contract, order)

while not trade.isDone():
    ib.sleep(1)

print(f"Order status: {trade.orderStatus.status}")
