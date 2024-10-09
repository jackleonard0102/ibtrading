import numpy as np
from scipy.stats import norm
import scipy.optimize
import datetime
from ib_insync import Stock, Option, ib, Index, Contract

def calculate_iv(S, K, T, r, market_price, option_type='call'):
    """
    Calculate Implied Volatility (IV) using the Black-Scholes model.
    """
    # ... (keep the existing implementation)

def get_iv(symbol):
    """
    Calculate IV using the stock and option data fetched from IB API.
    """
    # ... (keep the existing implementation)

def get_stock_list():
    """
    Fetch the list of stock symbols from IB API.
    """
    try:
        # Use the positions to get the stock list
        positions = ib.positions()
        stock_symbols = list(set([p.contract.symbol for p in positions if p.contract.secType == 'STK']))
        return sorted(stock_symbols)
    except Exception as e:
        print(f"Error in get_stock_list: {e}")
        # Return a default list of popular stocks as a fallback
        return ["AAPL", "MSFT", "AMZN", "GOOGL", "FB", "TSLA", "NVDA", "JPM", "JNJ", "V"]

# Make sure to initialize the IB connection before using these functions
# ib = IB()
# ib.connect('127.0.0.1', 7497, clientId=1)
