"""Interactive Brokers RV calculator module with improved async handling."""

import numpy as np
from datetime import datetime
import asyncio
from ib_insync import Stock, util
from components.ib_connection import ib
import logging
import nest_asyncio

# Configure module logger
logger = logging.getLogger(__name__)

nest_asyncio.apply()

async def get_historical_data_async(contract, window_days=30):
    """Get historical data asynchronously with proper cleanup."""
    try:
        data = await ib.reqHistoricalDataAsync(
            contract=contract,
            endDateTime='',
            durationStr=f'{window_days} D',
            barSizeSetting='1 day',
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1
        )
        
        if not data:
            logger.error(f"No historical data received for {contract.symbol}")
            return None
            
        return data
    except Exception as e:
        logger.error(f"Error requesting historical data: {str(e)}")
        return None

async def get_historical_prices(symbol, window_days=30):
    """Get historical price data asynchronously with validation."""
    try:
        if not isinstance(window_days, int) or window_days <= 0:
            logger.error("Invalid window_days parameter")
            return None
            
        contract = Stock(symbol, 'SMART', 'USD')
        await ib.qualifyContractsAsync(contract)
        
        data = await get_historical_data_async(contract, window_days)
        if not data:
            return None
            
        closes = np.array([bar.close for bar in data if hasattr(bar, 'close') and bar.close > 0])
        
        if len(closes) < window_days * 0.8:
            logger.error(f"Insufficient historical data for {symbol}")
            return None
            
        return closes
        
    except Exception as e:
        logger.error(f"Error fetching historical data for {symbol}: {str(e)}")
        return None

def calculate_returns(prices):
    """Calculate log returns with improved validation."""
    try:
        if not isinstance(prices, np.ndarray):
            prices = np.array(prices)
            
        valid_prices = prices[prices > 0]
        if len(valid_prices) < 2:
            logger.error("Insufficient valid prices for return calculation")
            return None
            
        returns = np.log(valid_prices[1:] / valid_prices[:-1])
        returns = returns[np.isfinite(returns)]
        
        if len(returns) == 0:
            logger.error("No valid returns after filtering")
            return None
            
        # Remove extreme values
        mean_return = np.mean(returns)
        std_return = np.std(returns)
        valid_returns = returns[np.abs(returns - mean_return) <= 4 * std_return]
        
        if len(valid_returns) < len(returns) * 0.8:
            logger.error("Too many outliers in return data")
            return None
            
        return valid_returns
        
    except Exception as e:
        logger.error(f"Error calculating returns: {str(e)}")
        return None

def annualize_volatility(daily_vol, trading_days=252):
    """Convert daily volatility to annualized value."""
    try:
        if not isinstance(daily_vol, (int, float)) or not np.isfinite(daily_vol) or daily_vol < 0:
            logger.error("Invalid daily volatility value")
            return None
            
        if not isinstance(trading_days, int) or trading_days <= 0:
            logger.error("Invalid trading days parameter")
            return None
            
        annual_vol = daily_vol * np.sqrt(trading_days)
        
        if not np.isfinite(annual_vol) or annual_vol < 0 or annual_vol > 5.0:  # 500% vol cap
            logger.error("Annualized volatility out of reasonable range")
            return None
            
        return annual_vol
        
    except Exception as e:
        logger.error(f"Error annualizing volatility: {str(e)}")
        return None

async def calculate_realized_volatility(symbol, window_days=30):
    """Calculate realized volatility with improved async handling."""
    try:
        if not isinstance(window_days, int) or window_days <= 0:
            logger.error("Invalid window_days parameter")
            return None
            
        prices = await get_historical_prices(symbol, window_days)
        if prices is None or len(prices) < 2:
            return None
            
        returns = calculate_returns(prices)
        if returns is None or len(returns) < window_days * 0.5:
            return None
            
        if len(returns) >= 2:
            daily_vol = np.std(returns, ddof=1)
            if not np.isfinite(daily_vol) or daily_vol <= 0:
                logger.error("Invalid daily volatility calculation")
                return None
                
            rv = annualize_volatility(daily_vol)
            if rv is None:
                return None
                
            return rv
        else:
            logger.error("Insufficient data for volatility calculation")
            return None
            
    except Exception as e:
        logger.error(f"Error calculating realized volatility: {str(e)}")
        return None

async def get_latest_rv(symbol, window_days=30):
    """Get the latest realized volatility with proper async handling."""
    try:
        rv = await calculate_realized_volatility(symbol, window_days)
        return rv
    except Exception as e:
        logger.error(f"Error getting RV for {symbol}: {str(e)}")
        return None
    finally:
        await asyncio.sleep(0)