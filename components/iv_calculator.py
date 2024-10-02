import numpy as np
from scipy.stats import norm
import scipy.optimize

def calculate_iv(S, K, T, r, market_price):
    def bs_price(vol):
        d1 = (np.log(S / K) + (r + 0.5 * vol**2) * T) / (vol * np.sqrt(T))
        d2 = d1 - vol * np.sqrt(T)
        return S * norm.cdf(d1) - K * np.exp(-r * T) * norm.cdf(d2)

    return scipy.optimize.brentq(lambda vol: bs_price(vol) - market_price, 0.01, 2.0)
