import numpy as np
from datetime import datetime, timedelta
from ib_insync import Stock
from components.ib_connection import ib
import nest_asyncio
import threading

nest_asyncio.apply()

def get_historical_data(symbol, window_days=30):
    """Get historical price data for a symbol"""
    try:
        contract = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(contract)
        
        # Request historical data
        bars = ib.reqHistoricalData(
            contract,
            endDateTime='',  # Empty string means now
            durationStr=f'{window_days} D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )
        
        if not bars:
            print(f"No historical data available for {symbol}")
            return None
        
        # Extract prices and timestamps
        prices = np.array([bar.close for bar in bars])
        highs = np.array([bar.high for bar in bars])
        lows = np.array([bar.low for bar in bars])
        timestamps = [bar.date for bar in bars]
        
        return {
            'prices': prices,
            'highs': highs,
            'lows': lows,
            'timestamps': timestamps
        }
        
    except Exception as e:
        print(f"Error fetching historical data for {symbol}: {str(e)}")
        return None

def calculate_returns(prices):
    """Calculate log returns from price series"""
    if len(prices) < 2:
        return None
    return np.log(prices[1:] / prices[:-1])

def annualize_volatility(volatility, time_period='daily'):
    """Convert volatility to annualized value"""
    if time_period == 'daily':
        return volatility * np.sqrt(252)  # Standard trading days in a year
    return volatility

def calculate_standard_volatility(returns):
    """Calculate standard volatility"""
    try:
        return np.std(returns, ddof=1)
    except Exception as e:
        print(f"Error calculating standard volatility: {str(e)}")
        return None

def calculate_parkinson_volatility(highs, lows):
    """Calculate Parkinson volatility estimator"""
    try:
        ranges = np.log(highs/lows)
        return np.sqrt(1/(4 * np.log(2)) * np.mean(ranges**2))
    except Exception as e:
        print(f"Error calculating Parkinson volatility: {str(e)}")
        return None

def calculate_realized_volatility(symbol, window_days=30):
    """Calculate realized volatility"""
    try:
        # Get historical data
        data = get_historical_data(symbol, window_days)
        if data is None:
            return None
            
        # Calculate returns
        returns = calculate_returns(data['prices'])
        if returns is None or len(returns) == 0:
            return None

        # Calculate standard volatility
        std_vol = calculate_standard_volatility(returns)
        if std_vol is None:
            return None

        # Calculate Parkinson volatility
        park_vol = calculate_parkinson_volatility(data['highs'][1:], data['lows'][1:])
        
        # Use average of both measures if available
        if park_vol is not None:
            vol = (std_vol + park_vol) / 2
        else:
            vol = std_vol

        # Annualize volatility
        return annualize_volatility(vol, 'daily')

    except Exception as e:
        print(f"Error calculating realized volatility for {symbol}: {str(e)}")
        return None

def get_latest_rv(symbol, window_days=30):
    """Get the latest realized volatility for a symbol"""
    try:
        result = [None]  # Use a list to store result from thread
        
        def run_calculation():
            result[0] = calculate_realized_volatility(symbol, window_days)
            
        # Run calculation in a separate thread
        thread = threading.Thread(target=run_calculation)
        thread.daemon = True
        thread.start()
        thread.join(timeout=10)  # Wait up to 10 seconds
        
        return result[0]
        
    except Exception as e:
        print(f"Error calculating RV for {symbol}: {str(e)}")
        return None