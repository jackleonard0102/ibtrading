import numpy as np
from scipy.stats import norm
import scipy.optimize
import datetime
from ib_insync import Stock, Option, ib, Index

def calculate_iv(S, K, T, r, market_price, option_type='call'):
    """
    Calculate Implied Volatility (IV) using the Black-Scholes model.
    
    Parameters:
    - S: Stock price
    - K: Strike price
    - T: Time to expiration (in years)
    - r: Risk-free interest rate
    - market_price: Current market price of the option
    - option_type: 'call' or 'put'
    
    Returns:
    - Implied volatility
    """
    def bs_price(vol):
        d1 = (np.log(S / K) + (r + 0.5 * vol ** 2) * T) / (vol * np.sqrt(T))
        d2 = d1 - vol * np.sqrt(T)
        if option_type == 'call':
            price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        else:  # put
            price = K * np.exp(-r * T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        return price - market_price

    try:
        iv = scipy.optimize.brentq(bs_price, 1e-6, 5.0, xtol=1e-6)
        return iv
    except ValueError:
        print(f"Could not find IV for given parameters: S={S}, K={K}, T={T}, r={r}, market_price={market_price}")
        return None

def get_iv(symbol):
    """
    Calculate IV using the stock and option data fetched from IB API.
    """
    # Fetch stock data
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)
    stock_data = ib.reqMktData(stock)
    ib.sleep(2)  # Wait for market data to arrive

    S = stock_data.marketPrice()
    if S is None:
        raise ValueError(f"Unable to fetch market price for {symbol}")

    # Fetch option chain
    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
    if not chains:
        raise ValueError(f"No option chain available for {symbol}")
    
    chain = next(c for c in chains if c.exchange == 'SMART')
    strikes = [strike for strike in chain.strikes
               if 0.8 * S < strike < 1.2 * S]
    expirations = sorted(exp for exp in chain.expirations)[:3]  # Get the first 3 expiration dates

    # Find ATM option
    closest_strike = min(strikes, key=lambda x: abs(x - S))
    expiration = expirations[0]

    # Create Option contract
    option = Option(symbol, expiration, closest_strike, 'C', 'SMART')
    ib.qualifyContracts(option)

    # Fetch option data
    option_data = ib.reqMktData(option)
    ib.sleep(2)  # Wait for market data to arrive

    K = option.strike
    now = datetime.datetime.now()
    expiry = datetime.datetime.strptime(option.lastTradeDateOrContractMonth, "%Y%m%d")
    T = max((expiry - now).days / 365, 1/365)  # Ensure T is at least 1 day
    r = 0.01  # Assume 1% risk-free rate, you may want to fetch this dynamically
    market_price = option_data.marketPrice()
    option_type = 'call' if option.right == 'C' else 'put'

    if S is None or K is None or T is None or market_price is None:
        raise ValueError(f"Invalid data for IV calculation: S={S}, K={K}, T={T}, market_price={market_price}")

    iv = calculate_iv(S, K, T, r, market_price, option_type)
    if iv is None:
        raise ValueError(f"Unable to calculate IV for {symbol}")
    return iv

def get_stock_list():
    """
    Fetch the list of stock symbols from IB API.
    """
    # Fetch S&P 500 stocks
    spx = Index('SPX', 'CBOE')
    ib.qualifyContracts(spx)
    
    # Request S&P 500 components
    sp500 = ib.reqMktData(spx)
    ib.sleep(2)  # Wait for market data to arrive
    
    if not sp500 or not sp500.secType:
        raise ValueError("Failed to fetch S&P 500 data")
    
    # Get the components of S&P 500
    components = ib.reqSecDefOptParams(spx.symbol, '', spx.secType, spx.conId)
    
    if not components:
        raise ValueError("Failed to fetch S&P 500 components")
    
    # Extract stock symbols from components
    stock_symbols = [comp.tradingClass for comp in components if comp.tradingClass]
    
    return stock_symbols

# Make sure to initialize the IB connection before using these functions
# ib = IB()
# ib.connect('127.0.0.1', 7497, clientId=1)
