import numpy as np
import pandas as pd
from ib_insync import Stock
from components.ib_connection import ib
from datetime import datetime, timedelta

def calculate_realized_volatility(price_data):
    """
    Calculate the Realized Volatility (RV) based on historical price data.
    """
    prices = pd.Series(price_data)
    log_returns = np.log(prices / prices.shift(1)).dropna()
    rv = log_returns.std() * np.sqrt(252)  # Annualize the volatility
    return rv

def get_latest_rv(symbol, window_minutes):
    """
    Get the latest Realized Volatility value for the given stock.
    """
    try:
        stock = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(stock)

        # Calculate the duration string based on the window
        duration = f"{int(window_minutes)} M"

        bars = ib.reqHistoricalData(
            stock,
            endDateTime='',
            durationStr=duration,
            barSizeSetting='1 min',
            whatToShow='TRADES',
            useRTH=False
        )
        if not bars or len(bars) < window_minutes:
            raise ValueError("Not enough historical data retrieved.")

        price_data = [bar.close for bar in bars]
        rv = calculate_realized_volatility(price_data)
        return rv
    except Exception as e:
        print(f"Error fetching RV for {symbol}: {str(e)}")
        return None
