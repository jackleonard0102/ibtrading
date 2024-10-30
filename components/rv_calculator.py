"""Interactive Brokers RV calculator module with improved async handling."""

import numpy as np
from datetime import datetime, timedelta
import asyncio
from ib_insync import Stock, util
from components.ib_connection import ib
import logging
import nest_asyncio
import pytz

# Configure module logger
logger = logging.getLogger(__name__)

nest_asyncio.apply()

def get_bar_size(minutes):
    """Get appropriate bar size based on time period."""
    if minutes <= 15:
        return '1 min'
    elif minutes <= 30:
        return '5 mins'
    elif minutes <= 60:
        return '10 mins'
    else:
        return '15 mins'

async def get_historical_data_async(contract, time_period_minutes=15):
    """Get historical data asynchronously with proper cleanup."""
    try:
        # Calculate duration in seconds based on time period
        # Multiply by 2 to ensure enough data and convert to seconds
        duration_secs = time_period_minutes * 2 * 60
        duration_str = f"{duration_secs} S"  # Duration in seconds
        
        bar_size = get_bar_size(time_period_minutes)
        
        # Use US/Eastern timezone for endDateTime
        eastern = pytz.timezone('US/Eastern')
        end_time = datetime.now(eastern)
        end_time = end_time.replace(second=0, microsecond=0)
        end_time_str = end_time.strftime('%Y%m%d %H:%M:%S US/Eastern')
        
        logger.info(f"Requesting {duration_secs}s of {bar_size} data for {contract.symbol}")
        
        data = await ib.reqHistoricalDataAsync(
            contract=contract,
            endDateTime=end_time_str,
            durationStr=duration_str,
            barSizeSetting=bar_size,
            whatToShow='TRADES',
            useRTH=True,
            formatDate=1,
            keepUpToDate=False
        )
        
        if not data:
            logger.error(f"No historical data received for {contract.symbol}")
            return None
            
        # Sort and validate data
        sorted_data = sorted(data, key=lambda x: x.date)
        
        if not sorted_data:
            logger.error(f"No valid data points for {contract.symbol}")
            return None
            
        logger.info(f"Got {len(sorted_data)} bars for {contract.symbol}")
        return sorted_data
        
    except Exception as e:
        logger.error(f"Error requesting historical data: {str(e)}")
        return None

async def get_underlying_symbol(symbol):
    """Get underlying symbol from either stock or option symbol."""
    try:
        # If it's an option, extract underlying
        if ' ' in symbol:
            underlying = symbol.split()[0]
            logger.info(f"Using underlying {underlying} from {symbol}")
            return underlying
        return symbol
    except Exception as e:
        logger.error(f"Error getting underlying symbol: {str(e)}")
        return None

async def get_historical_prices(symbol, time_period_minutes=15):
    """Get historical price data asynchronously with validation."""
    try:
        if not isinstance(time_period_minutes, int) or time_period_minutes <= 0:
            logger.error("Invalid time period")
            return None
            
        # Get underlying symbol
        underlying = await get_underlying_symbol(symbol)
        if not underlying:
            return None
            
        # Create and qualify stock contract
        contract = Stock(underlying, 'SMART', 'USD')
        if not await ib.qualifyContractsAsync(contract):
            logger.error(f"Could not qualify stock contract: {underlying}")
            return None
            
        # Get historical data
        data = await get_historical_data_async(contract, time_period_minutes)
        if not data:
            return None
            
        # Extract close prices
        prices = np.array([bar.close for bar in data if bar.close > 0])
        
        # Validate data points
        expected_bars = time_period_minutes // int(get_bar_size(time_period_minutes).split()[0])
        if len(prices) < expected_bars * 0.8:  # Need at least 80% of expected bars
            logger.error(f"Insufficient price data: got {len(prices)}, need {expected_bars}")
            return None
            
        # Use most recent data points
        prices = prices[-expected_bars:]
        logger.info(f"Using {len(prices)} price points for {underlying}")
        return prices
        
    except Exception as e:
        logger.error(f"Error getting historical prices: {str(e)}")
        return None

def calculate_returns(prices):
    """Calculate log returns with improved validation."""
    try:
        if len(prices) < 2:
            logger.error("Need at least 2 prices to calculate returns")
            return None
            
        # Calculate log returns
        returns = np.log(prices[1:] / prices[:-1])
        
        # Remove invalid returns
        valid_returns = returns[np.isfinite(returns)]
        if len(valid_returns) < len(returns) * 0.8:
            logger.error("Too many invalid returns")
            return None
            
        # Remove outliers
        mean = np.mean(valid_returns)
        std = np.std(valid_returns)
        clean_returns = valid_returns[np.abs(valid_returns - mean) <= 4 * std]
        
        if len(clean_returns) < len(valid_returns) * 0.8:
            logger.error("Too many outliers in return data")
            return None
            
        logger.info(f"Calculated {len(clean_returns)} valid returns")
        return clean_returns
        
    except Exception as e:
        logger.error(f"Error calculating returns: {str(e)}")
        return None

def annualize_volatility(vol, time_period_minutes):
    """Convert period volatility to annualized value."""
    try:
        if not np.isfinite(vol) or vol < 0:
            logger.error("Invalid volatility value")
            return None
            
        # Calculate annualization factor
        trading_minutes = 252 * 6.5 * 60  # Trading days * hours/day * minutes/hour
        factor = np.sqrt(trading_minutes / time_period_minutes)
        annual_vol = vol * factor
        
        if not np.isfinite(annual_vol) or annual_vol < 0:
            logger.error("Invalid annualized volatility")
            return None
            
        if annual_vol > 5.0:  # Cap at 500%
            logger.warning(f"Capping volatility at 500% (was {annual_vol:.2%})")
            return 5.0
            
        logger.info(f"Annualized volatility: {annual_vol:.2%}")
        return annual_vol
        
    except Exception as e:
        logger.error(f"Error annualizing volatility: {str(e)}")
        return None

async def calculate_realized_volatility(symbol, time_period_minutes=15):
    """Calculate realized volatility with improved async handling."""
    try:
        logger.info(f"Calculating RV for {symbol} over {time_period_minutes} minutes")
        
        # Get historical prices
        prices = await get_historical_prices(symbol, time_period_minutes)
        if prices is None:
            return None
            
        # Calculate returns
        returns = calculate_returns(prices)
        if returns is None:
            return None
            
        # Calculate period volatility
        period_vol = np.std(returns, ddof=1)
        if not np.isfinite(period_vol) or period_vol <= 0:
            logger.error("Invalid period volatility calculation")
            return None
            
        # Convert to annual volatility
        rv = annualize_volatility(period_vol, time_period_minutes)
        if rv is not None:
            logger.info(f"Final RV for {symbol}: {rv:.2%}")
            
        return rv
        
    except Exception as e:
        logger.error(f"Error calculating RV: {str(e)}")
        return None

async def get_latest_rv(symbol, time_period_minutes=15):
    """Get the latest realized volatility with proper async handling."""
    try:
        if not symbol:
            logger.error("No symbol provided")
            return None
            
        return await calculate_realized_volatility(symbol, time_period_minutes)
        
    except Exception as e:
        logger.error(f"Error getting RV: {str(e)}")
        return None