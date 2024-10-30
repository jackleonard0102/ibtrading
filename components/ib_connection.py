"""Interactive Brokers connection management module."""

from ib_insync import IB, Stock, Option, util
import asyncio
import logging
from config import config
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

# Configure module logger
logger = logging.getLogger(__name__)

# Initialize IB connection
ib = IB()

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
                    ib.reqMarketDataType(1)  # Use real-time market data when available
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
        logger.info(f"Fetched {len(positions)} positions")
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
        logger.info(f"Created stock contract for {symbol}")
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

def get_delta(position: Any, ib_instance: IB) -> float:
    """
    Calculate delta for a position.
    
    Args:
        position: Position object.
        ib_instance: IB connection instance.
        
    Returns:
        float: Position delta.
    """
    contract = position.contract
    try:
        if contract.secType == 'STK':
            return float(position.position)
        elif contract.secType == 'OPT':
            # For options, use portfolio data to calculate delta
            portfolio = ib_instance.portfolio()
            for item in portfolio:
                if (item.contract.symbol == contract.symbol and 
                    item.contract.secType == contract.secType and
                    item.contract.lastTradeDateOrContractMonth == contract.lastTradeDateOrContractMonth and
                    item.contract.strike == contract.strike and
                    item.contract.right == contract.right):
                    # Approximate delta calculation for put/call options
                    if contract.right == 'C':
                        return float(position.position) * 0.5  # Approximate delta for calls
                    else:
                        return float(position.position) * -0.5  # Approximate delta for puts
            
            logger.warning(f"No portfolio data found for option {contract.localSymbol}")
            return 0.0
        else:
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
