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
        # Request market data
        market_data = ib.reqMktData(stock_contract, '', False, False)
        ib.sleep(2)  # Wait for market data

        # Check if the contract is an option
        if stock_contract.secType == 'OPT':
            if market_data and hasattr(market_data, 'modelGreeks'):
                # Return the delta from modelGreeks
                return market_data.modelGreeks.delta if market_data.modelGreeks else 0
            else:
                return 0
        else:
            return 0  # No delta for stocks

    except Exception as e:
        print(f"Error fetching delta for {stock_contract.symbol}: {e}")
        return 0
