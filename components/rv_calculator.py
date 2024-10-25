import numpy as np
from datetime import datetime, timedelta
from ib_insync import Stock
from components.ib_connection import ib
import threading

def get_historical_data(symbol, duration='30 D', bar_size='1 day'):
    """Get historical price data for a symbol"""
    try:
        contract = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(contract)
        
        # Request historical data
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',  # Empty string means now
            durationStr=duration,
            barSizeSetting=bar_size,
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )
        
        if not bars:
            print(f"No historical data available for {symbol}")
            return None
        
        # Extract closing prices and timestamps
        prices = np.array([bar.close for bar in bars])
        timestamps = [bar.date for bar in bars]
        
        return prices, timestamps
        
    except Exception as e:
        print(f"Error fetching historical data for {symbol}: {str(e)}")
        return None

def calculate_returns(prices):
    """Calculate log returns from price series"""
    if len(prices) < 2:
        return None
    return np.log(prices[1:] / prices[:-1])

def annualize_volatility(volatility, time_period='daily'):
    """Convert volatility to annualized value based on observation frequency"""
    if time_period == 'daily':
        return volatility * np.sqrt(252)
    elif time_period == 'hourly':
        return volatility * np.sqrt(252 * 6.5)  # Assuming 6.5 trading hours per day
    elif time_period == 'minute':
        return volatility * np.sqrt(252 * 6.5 * 60)
    return volatility

def calculate_realized_volatility(symbol, window_days=30, method='standard'):
    """Calculate realized volatility using different methods"""
    try:
        # Get historical data
        data = get_historical_data(symbol, f"{window_days} D", "1 day")
        if data is None:
            return None
            
        prices, timestamps = data
        returns = calculate_returns(prices)
        
        if returns is None or len(returns) == 0:
            return None

        if method == 'standard':
            # Standard deviation of returns
            volatility = np.std(returns, ddof=1)
        elif method == 'exponential':
            # Exponentially weighted standard deviation
            volatility = np.sqrt(np.var(returns, ddof=1))
        elif method == 'parkinson':
            # Parkinson volatility estimator using high-low ranges
            high_low_data = get_historical_data(symbol, f"{window_days} D", "1 day")
            if high_low_data is None:
                return None
                
            highs = np.array([bar.high for bar in high_low_data[0]])
            lows = np.array([bar.low for bar in high_low_data[0]])
            ranges = np.log(highs/lows)
            volatility = np.sqrt(1/(4*np.log(2)) * np.mean(ranges**2))
        else:
            raise ValueError(f"Unknown volatility calculation method: {method}")

        # Annualize volatility
        return annualize_volatility(volatility, 'daily')

    except Exception as e:
        print(f"Error calculating realized volatility for {symbol}: {str(e)}")
        return None

def calculate_rolling_rv(symbol, window_days=30, method='standard'):
    """Calculate rolling realized volatility"""
    try:
        # Get more historical data than the window to calculate rolling values
        data = get_historical_data(symbol, f"{window_days*2} D", "1 day")
        if data is None:
            return None
            
        prices, timestamps = data
        returns = calculate_returns(prices)
        
        if returns is None or len(returns) < window_days:
            return None

        # Calculate rolling volatility
        rolling_vol = []
        for i in range(len(returns) - window_days + 1):
            window_returns = returns[i:i+window_days]
            vol = np.std(window_returns, ddof=1)
            rolling_vol.append(annualize_volatility(vol, 'daily'))

        return rolling_vol, timestamps[-len(rolling_vol):]

    except Exception as e:
        print(f"Error calculating rolling realized volatility for {symbol}: {str(e)}")
        return None

def get_latest_rv(symbol, window_days=30, method='standard'):
    """Get the latest realized volatility for a symbol"""
    try:
        result = [None]  # Use a list to store result from thread
        
        def run_calculation():
            result[0] = calculate_realized_volatility(symbol, window_days, method)
            
        # Run calculation in a separate thread
        thread = threading.Thread(target=run_calculation)
        thread.daemon = True
        thread.start()
        thread.join(timeout=10)  # Wait up to 10 seconds for the calculation
        
        return result[0]
        
    except Exception as e:
        print(f"Error calculating RV for {symbol}: {str(e)}")
        return None
