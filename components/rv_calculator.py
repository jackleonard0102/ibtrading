import numpy as np
from datetime import datetime
from ib_insync import Stock
from components.ib_connection import ib
import nest_asyncio

nest_asyncio.apply()

def reqHistoricalDataAsync(contract, window_days=30):
    """Get historical data safely with proper cleanup"""
    try:
        # Request historical data with more comprehensive parameters
        data = ib.reqHistoricalData(
            contract=contract,
            endDateTime='',
            durationStr=f'{window_days} D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1,
            timeout=30  # Add timeout parameter
        )
        
        if not data:
            print(f"No historical data received for {contract.symbol}")
            return None
            
        return data
    except Exception as e:
        print(f"Error requesting historical data: {str(e)}")
        return None
    finally:
        try:
            ib.sleep(0)  # Allow pending callbacks to be processed
        except:
            pass

def get_historical_data(symbol, window_days=30):
    """Get historical price data for a symbol with improved validation"""
    try:
        if not isinstance(window_days, int) or window_days <= 0:
            print("Invalid window_days parameter")
            return None
            
        contract = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(contract)
        
        # Get historical data with timeout
        data = reqHistoricalDataAsync(contract, window_days)
        if not data:
            return None
        
        # Extract and validate price data
        closes = np.array([bar.close for bar in data if hasattr(bar, 'close') and bar.close > 0])
        
        if len(closes) < window_days * 0.8:  # Require at least 80% of expected data points
            print(f"Insufficient historical data for {symbol}: got {len(closes)} days, expected {window_days}")
            return None
            
        return closes
        
    except Exception as e:
        print(f"Error fetching historical data for {symbol}: {str(e)}")
        return None

def calculate_returns(prices):
    """Calculate log returns from price series with improved validation"""
    try:
        if not isinstance(prices, np.ndarray):
            prices = np.array(prices)
            
        # Remove any zero or negative prices
        valid_prices = prices[prices > 0]
        if len(valid_prices) < 2:
            print("Insufficient valid prices for return calculation")
            return None
            
        # Calculate log returns
        returns = np.log(valid_prices[1:] / valid_prices[:-1])
        
        # Remove any infinite or NaN values
        returns = returns[np.isfinite(returns)]
        if len(returns) == 0:
            print("No valid returns after filtering")
            return None
            
        # Check for extreme values
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        valid_returns = returns[np.abs(returns - mean_return) <= 4 * std_return]  # Remove outliers
        
        if len(valid_returns) < len(returns) * 0.8:  # Ensure we haven't removed too many points
            print("Too many outliers in return data")
            return None
            
        return valid_returns
        
    except Exception as e:
        print(f"Error calculating returns: {str(e)}")
        return None

def annualize_volatility(daily_vol, trading_days=252):
    """Convert daily volatility to annualized value with improved validation"""
    try:
        if not isinstance(daily_vol, (int, float)) or not np.isfinite(daily_vol) or daily_vol < 0:
            print("Invalid daily volatility value")
            return None
            
        if not isinstance(trading_days, int) or trading_days <= 0:
            print("Invalid trading days parameter")
            return None
            
        # Standard annualization
        annual_vol = daily_vol * np.sqrt(trading_days)
        
        # Sanity check on the result
        if not np.isfinite(annual_vol) or annual_vol < 0 or annual_vol > 10:  # 1000% vol cap
            print("Annualized volatility out of reasonable range")
            return None
            
        return annual_vol
        
    except Exception as e:
        print(f"Error annualizing volatility: {str(e)}")
        return None

def calculate_realized_volatility(symbol, window_days=30):
    """Calculate realized volatility with comprehensive validation"""
    try:
        # Input validation
        if not isinstance(window_days, int) or window_days <= 0:
            print("Invalid window_days parameter")
            return None
            
        # Get historical prices
        prices = get_historical_data(symbol, window_days)
        if prices is None or len(prices) < 2:
            return None
            
        # Calculate returns
        returns = calculate_returns(prices)
        if returns is None or len(returns) < window_days * 0.5:  # Require at least 50% of expected data
            return None
            
        # Calculate daily volatility with validation
        if len(returns) >= 2:
            daily_vol = np.std(returns, ddof=1)
            if not np.isfinite(daily_vol) or daily_vol <= 0:
                print("Invalid daily volatility calculation")
                return None
                
            # Annualize volatility
            rv = annualize_volatility(daily_vol)
            if rv is None:
                return None
                
            return rv
        else:
            print("Insufficient data for volatility calculation")
            return None
            
    except Exception as e:
        print(f"Error calculating realized volatility: {str(e)}")
        return None

def get_latest_rv(symbol, window_days=30):
    """Get the latest realized volatility for a symbol with error handling"""
    try:
        rv = calculate_realized_volatility(symbol, window_days)
        return rv
    except Exception as e:
        print(f"Error getting RV for {symbol}: {str(e)}")
        return None
    finally:
        try:
            ib.sleep(0)  # Allow pending callbacks to be processed
        except:
            pass