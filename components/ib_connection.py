from ib_insync import IB, Stock

ib = IB()

def connect_ib(port=7497):
    """
    Connect to IB Gateway or TWS on the specified port.
    """
    try:
        ib.connect('127.0.0.1', port, clientId=1)
        print("Connected to IBKR!")
        return True
    except Exception as e:
        print(f"Error connecting to IBKR: {e}")
        print("Ensure that TWS or IB Gateway is running and configured to accept API connections.")
        return False

def define_stock_contract(symbol, exchange='SMART', currency='USD'):
    """
    Define a stock contract with more explicit details to ensure qualification.
    """
    return Stock(symbol, exchange, currency)

def get_portfolio_positions():
    """
    Fetch all portfolio positions dynamically.
    """
    return ib.positions()

def fetch_market_data_for_stock(stock_contract):
    """
    Fetch market data for the given stock contract after ensuring it's qualified.
    """
    try:
        ib.qualifyContracts(stock_contract)
        print(f"Qualified contract for {stock_contract.symbol}")
        return ib.reqMktData(stock_contract)
    except Exception as e:
        print(f"Error qualifying contract or fetching market data for {stock_contract.symbol}: {e}")
        return None
