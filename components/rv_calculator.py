import numpy as np
import pandas as pd

def calculate_realized_volatility(price_data, window):
    prices = pd.Series(price_data)
    log_returns = np.log(prices / prices.shift(1))
    rolling_vol = log_returns.rolling(window=window).std()
    return rolling_vol.iloc[-1] * np.sqrt(252)
