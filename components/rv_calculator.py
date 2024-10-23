import numpy as np
import pandas as pd
from ib_insync import Stock
from components.ib_connection import ib

def calculate_realized_volatility(price_data, window):
    """
    Calculate the Realized Volatility (RV) based on historical price data.
    """
    if len(price_data) < window + 1:
        raise ValueError("Not enough historical price data for RV calculation.")

    prices = pd.Series(price_data)
    log_returns = np.log(prices / prices.shift(1))
    
    rolling_std = log_returns.rolling(window=window).std()
    rv_values = rolling_std * np.sqrt(252)  # Annualize the volatility

    return rv_values.dropna().tolist()

def get_latest_rv(symbol, window):
    """
    Get the latest Realized Volatility value for the given stock.
    """
    try:
        stock = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(stock)

        bars = ib.reqHistoricalData(
            stock,
            endDateTime='',
            durationStr='1 Y',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True
        )
        price_data = [bar.close for bar in bars]
        rv_values = calculate_realized_volatility(price_data, window)
        return rv_values[-1] if rv_values else None
    except Exception as e:
        print(f"Error fetching RV for {symbol}: {str(e)}")
        return None
