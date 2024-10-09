import numpy as np
from scipy.stats import norm
import scipy.optimize
import datetime

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

def get_iv(stock_data, option_data):
    """
    Calculate IV using the stock and option data.
    """
    S = stock_data.marketPrice()
    K = option_data.contract.strike
    now = datetime.datetime.now()
    expiry = option_data.contract.lastTradeDateOrContractMonth
    if isinstance(expiry, str):
        expiry = datetime.datetime.strptime(expiry, "%Y%m%d")
    T = max((expiry - now).days / 365, 1/365)  # Ensure T is at least 1 day
    r = 0.01  # Assume 1% risk-free rate, you may want to fetch this dynamically
    market_price = option_data.marketPrice()
    option_type = 'call' if option_data.contract.right == 'C' else 'put'

    if S is None or K is None or T is None or market_price is None:
        raise ValueError(f"Invalid data for IV calculation: S={S}, K={K}, T={T}, market_price={market_price}")

    iv = calculate_iv(S, K, T, r, market_price, option_type)
    if iv is None:
        raise ValueError(f"Unable to calculate IV for {option_data.contract.symbol}")
    return iv
