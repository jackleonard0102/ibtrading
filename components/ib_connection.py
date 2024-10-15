from ib_insync import IB, Stock

ib = IB()

def connect_ib(port=7497):
    try:
        ib.connect('127.0.0.1', port, clientId=1)
        print("Connected to IBKR!")
        return True
    except Exception as e:
        print(f"Error connecting to IBKR: {e}")
        return False

def define_stock_contract(symbol, exchange='SMART', currency='USD'):
    return Stock(symbol, exchange, currency)

def get_portfolio_positions():
    return ib.positions()

def fetch_market_data_for_stock(stock_contract):
    try:
        ib.qualifyContracts(stock_contract)
        return ib.reqMktData(stock_contract)
    except Exception as e:
        print(f"Error fetching market data for {stock_contract.symbol}: {e}")
        return None

def get_delta(stock_contract):
    try:
        market_data = ib.reqMktData(stock_contract)
        if market_data:
            return market_data.delta if market_data.delta else 0
    except Exception as e:
        print(f"Error fetching delta for {stock_contract.symbol}: {e}")
        return 0
