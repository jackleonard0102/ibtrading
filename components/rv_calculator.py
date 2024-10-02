import numpy as np
import pandas as pd

def calculate_realized_volatility(price_data, window):
    """
    Calculate Realized Volatility (RV) based on historical price data.
    """
    if not price_data or len(price_data) < window:
        raise ValueError("Not enough historical price data for RV calculation.")

    prices = pd.Series(price_data)
    log_returns = np.log(prices / prices.shift(1))
    rolling_vol = log_returns.rolling(window=window).std()

    # Ensure there's enough data to access the last rolling window value
    if len(rolling_vol) < window:
        raise ValueError(f"Not enough data to calculate RV for the selected window ({window} mins).")

    realized_vol = rolling_vol.iloc[-1] * np.sqrt(252) if not rolling_vol.isna().all() else np.nan
    return realized_vol
