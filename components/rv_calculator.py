import numpy as np
import pandas as pd

def calculate_realized_volatility(price_data, window):
    """
    Calculate Realized Volatility (RV) based on historical price data.
    
    Parameters:
    - price_data: List or array of historical prices
    - window: Number of periods to use for calculation
    
    Returns:
    - List of realized volatility values
    """
    if len(price_data) < window + 1:
        raise ValueError("Not enough historical price data for RV calculation.")

    prices = pd.Series(price_data)
    log_returns = np.log(prices / prices.shift(1))
    
    # Calculate rolling standard deviation
    rolling_std = log_returns.rolling(window=window).std()
    
    # Annualize the volatility (assuming daily data)
    rv_values = rolling_std * np.sqrt(252)
    
    return rv_values.dropna().tolist()

def get_latest_rv(price_data, window):
    """
    Get the latest realized volatility value.
    
    Parameters:
    - price_data: List or array of historical prices
    - window: Number of periods to use for calculation
    
    Returns:
    - Latest realized volatility value
    """
    rv_values = calculate_realized_volatility(price_data, window)
    return rv_values[-1] if rv_values else None
