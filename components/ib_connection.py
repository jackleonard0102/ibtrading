"""Interactive Brokers connection management module."""

from ib_insync import IB, Stock, Option, util
import asyncio
import logging
from config import config
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any
from datetime import datetime, timedelta

# Configure module logger
logger = logging.getLogger(__name__)

# Initialize IB connection
ib = IB()

# Cache for market data
market_data_cache = {}
last_market_data_request = {}
MARKET_DATA_CACHE_TIME = 5  # seconds

async def connect_ib() -> bool:
    """
    Connect to Interactive Brokers with retry mechanism.
    
    Returns:
        bool: True if connection successful, False otherwise.
    """
    for attempt in range(config.ib.retry_count):
        try:
            if not ib.isConnected():
                logger.info(f"Attempting to connect to IBKR (Attempt {attempt + 1}/{config.ib.retry_count})")
                await ib.connectAsync(config.ib.host, config.ib.port, clientId=config.ib.client_id)
                await asyncio.sleep(1)  # Give connection time to stabilize
                
                if ib.isConnected():
                    logger.info("Successfully connected to IBKR")
                    ib.reqMarketDataType(3)  # Use delayed frozen data for more reliability
                    return True
            else:
                logger.info("Already connected to IBKR")
                return True
                
        except Exception as e:
            logger.error(f"Connection attempt {attempt + 1} failed: {str(e)}")
            if attempt < config.ib.retry_count - 1:  # Don't sleep on last attempt
                await asyncio.sleep(config.ib.retry_delay)
                
    logger.error("Failed to connect to IBKR after all attempts")
    return False
    
def get_portfolio_positions() -> List[Any]:
    """
    Get current portfolio positions.
    
    Returns:
        List[Any]: List of portfolio positions.
    """
    try:
        if not ib.isConnected():
            logger.error("Cannot fetch positions: Not connected to IBKR")
            return []
            
        positions = ib.positions()
        logger.debug(f"Fetched {len(positions)} positions")  # Changed to debug level
        return positions
        
    except Exception as e:
        logger.error(f"Error fetching positions: {e}")
        return []

def define_stock_contract(
    symbol: str,
    exchange: str = config.trading.default_exchange,
    currency: str = config.trading.default_currency
) -> Optional[Stock]:
    """
    Create a stock contract object.
    
    Args:
        symbol: Stock symbol.
        exchange: Exchange name (default: SMART).
        currency: Currency code (default: USD).
        
    Returns:
        Optional[Stock]: Stock contract object if successful, None otherwise.
    """
    try:
        contract = Stock(symbol, exchange, currency)
        logger.debug(f"Created stock contract for {symbol}")
        return contract
    except Exception as e:
        logger.error(f"Error creating stock contract for {symbol}: {e}")
        return None

def get_market_price(contract: Stock) -> Tuple[Optional[float], Optional[float], Optional[float]]:
    """
    Get market price from portfolio data.
    
    Args:
        contract: Stock contract object.
        
    Returns:
        Tuple[Optional[float], Optional[float], Optional[float]]: 
            (market_price, market_value, unrealized_pnl) if successful, (None, None, None) otherwise.
    """
    try:
        portfolio = ib.portfolio()
        for item in portfolio:
            if (item.contract.symbol == contract.symbol and 
                item.contract.secType == contract.secType):
                return item.marketPrice, item.marketValue, item.unrealizedPNL
    except Exception as e:
        logger.error(f"Error getting market price for {contract.symbol}: {e}")
    return None, None, None

def can_request_market_data(contract_id: int) -> bool:
    """Check if we can request market data for a contract based on cache time"""
    now = datetime.now()
    if contract_id in last_market_data_request:
        last_request = last_market_data_request[contract_id]
        if now - last_request < timedelta(seconds=MARKET_DATA_CACHE_TIME):
            return False
    last_market_data_request[contract_id] = now
    return True

def get_cached_market_data(contract_id: int) -> Optional[float]:
    """Get cached market data if available and not expired"""
    if contract_id in market_data_cache:
        data, timestamp = market_data_cache[contract_id]
        if datetime.now() - timestamp < timedelta(seconds=MARKET_DATA_CACHE_TIME):
            return data
    return None

def calculate_theoretical_delta(contract: Option, market_price: float) -> float:
    """Calculate theoretical option delta based on moneyness"""
    try:
        strike = float(contract.strike)
        moneyness = (market_price - strike) / strike

        if contract.right == 'C':
            if moneyness > 0:  # ITM call
                base_delta = 0.85
                adj = min(0.15, moneyness * 0.3)  # More ITM = higher delta
                return base_delta + adj
            elif moneyness < 0:  # OTM call
                base_delta = 0.15
                adj = max(-0.1, moneyness * 0.3)  # More OTM = lower delta
                return base_delta + adj
            else:  # ATM call
                return 0.5
        else:  # Put
            if moneyness < 0:  # ITM put
                base_delta = -0.85
                adj = max(-0.15, moneyness * 0.3)  # More ITM = more negative delta
                return base_delta + adj
            elif moneyness > 0:  # OTM put
                base_delta = -0.15
                adj = min(0.1, moneyness * 0.3)  # More OTM = less negative delta
                return base_delta + adj
            else:  # ATM put
                return -0.5
    except Exception as e:
        logger.error(f"Error calculating theoretical delta: {e}")
        return 0.0

def get_delta(position: Any, ib_instance: IB) -> float:
    """
    Calculate delta for a position.
    
    Args:
        position: Position object.
        ib_instance: IB connection instance.
        
    Returns:
        float: Position delta.
    """
    try:
        contract = position.contract
        pos_size = float(position.position)

        # For stocks, delta is just the position size
        if contract.secType == 'STK':
            return pos_size

        # For options, calculate delta based on position and contract
        elif contract.secType == 'OPT':
            # Try to get cached market data first
            cached_delta = None
            if hasattr(contract, 'conId'):
                cached_delta = get_cached_market_data(contract.conId)
            
            contract_delta = None
            if cached_delta is not None:
                contract_delta = cached_delta
                logger.debug(f"Using cached delta for {contract.localSymbol}")
            else:
                # Only request new market data if cache expired
                if hasattr(contract, 'conId') and can_request_market_data(contract.conId):
                    # Get current stock price from portfolio
                    portfolio = [item for item in ib.portfolio() if item.contract.symbol == contract.symbol]
                    if portfolio:
                        stock_price = portfolio[0].marketPrice
                        # Calculate theoretical delta
                        contract_delta = calculate_theoretical_delta(contract, stock_price)
                        # Cache the result
                        market_data_cache[contract.conId] = (contract_delta, datetime.now())
                        logger.debug(f"Calculated new delta for {contract.localSymbol}: {contract_delta}")
            
            if contract_delta is None:
                # Use very conservative delta estimate if all else fails
                contract_delta = 0.5 if contract.right == 'C' else -0.5
                logger.debug(f"Using default delta for {contract.localSymbol}: {contract_delta}")

            # Calculate final position delta
            multiplier = float(contract.multiplier) if hasattr(contract, "multiplier") else 100.0
            position_delta = pos_size * contract_delta * multiplier
            logger.debug(f"Final position delta for {contract.localSymbol}: {position_delta}")
            return position_delta

        return 0.0

    except Exception as e:
        logger.error(f"Error calculating delta for {contract.symbol}: {e}")
        return 0.0

async def disconnect_ib() -> bool:
    """
    Safely disconnect from Interactive Brokers.
    
    Returns:
        bool: True if disconnection successful, False otherwise.
    """
    try:
        if ib.isConnected():
            ib.disconnect()
            logger.info("Disconnected from IBKR")
            return True
    except Exception as e:
        logger.error(f"Error disconnecting from IBKR: {e}")
        return False
