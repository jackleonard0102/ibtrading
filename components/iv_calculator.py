import numpy as np
from scipy.stats import norm
import scipy.optimize

def calculate_iv(S, K, T, r, market_price):
    """
    Calculate Implied Volatility (IV) using the Black-Scholes model.
    
    Parameters:
    - S: Stock price
    - K: Strike price
    - T: Time to expiration (in years)
    - r: Risk-free interest rate
    - market_price: Current market price of the option
    
    Returns:
    - Implied volatility
    """
    def bs_price(vol):
        d1 = (np.log(S / K) + (r + 0.5 * vol ** 2) * T) / (vol * np.sqrt(T))
        d2 = d1 - vol * np.sqrt(T)
        call_price = S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)
        return call_price

    # Minimize the difference between the market price and Black-Scholes price
    iv = scipy.optimize.brentq(lambda vol: bs_price(vol) - market_price, 0.001, 5.0)
    return iv
