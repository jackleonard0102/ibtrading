import numpy as np
from scipy.stats import norm
from ib_insync import Stock, Option
from components.ib_connection import ib

def get_iv(symbol):
    """
    Calculate IV using the stock and option data fetched from IB API.
    """
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)
    
    stock_data = ib.reqMktData(stock)
    ib.sleep(2)  # Allow time for data to arrive

    if not stock_data.marketPrice():
        raise ValueError(f"Unable to fetch market price for {symbol}")
    
    # Simulate fetching option and calculating IV here
    # Use Black-Scholes for calculating implied volatility
    # ...

    return 0.25  # Placeholder return value for IV

def get_stock_list():
    try:
        positions = ib.positions()
        stock_symbols = list(set([p.contract.symbol for p in positions if p.contract.secType == 'STK']))
        return sorted(stock_symbols)
    except Exception as e:
        print(f"Error in get_stock_list: {e}")
        return ["AAPL", "MSFT", "AMZN"]
