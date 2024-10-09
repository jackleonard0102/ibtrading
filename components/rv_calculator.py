import numpy as np
import pandas as pd
from ib_insync import Stock, ib

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

def get_latest_rv(symbol, window):
    """
    Get the latest realized volatility value.
    
    Parameters:
    - symbol: Stock symbol
    - window: Number of periods to use for calculation
    
    Returns:
    - Latest realized volatility value
    """
    # Fetch historical data from IB API
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
    
    if not bars:
        raise ValueError(f"No historical data available for {symbol}")
    
    price_data = [bar.close for bar in bars]
    rv_values = calculate_realized_volatility(price_data, window)
    return rv_values[-1] if rv_values else None

def get_stock_list():
    """
    Fetch the list of stock symbols from IB API.
    """
    # This is a placeholder. You need to implement the actual API call to fetch the stock list.
    # For example, you might fetch all stocks in a particular market or index.
    # Here's a dummy implementation:
    stocks = ib.reqContractDetails(Stock('', 'SMART', 'USD'))
    return [stock.contract.symbol for stock in stocks if stock.contract.symbol]

# Make sure to initialize the IB connection before using these functions
# ib = IB()
# ib.connect('127.0.0.1', 7497, clientId=1)
