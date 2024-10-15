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
    """
    Fetch delta for options, return 0 for stocks.
    """
    try:
        market_data = ib.reqMktData(stock_contract, '', False, False)
        ib.sleep(2)  # Wait for the market data to populate

        if stock_contract.secType == 'OPT':
            return market_data.modelGreeks.delta if hasattr(market_data.modelGreeks, 'delta') else 0
        else:
            return 0  # For stocks, delta doesn't apply

    except Exception as e:
        print(f"Error fetching delta for {stock_contract.symbol}: {e}")
        return 0