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
                    ib.reqMarketDataType(2)  # Use delayed market data, more reliable for Greeks
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

def get_theoretical_delta(contract: Option, price: float) -> float:
    """Calculate theoretical delta for an option based on its moneyness"""
    strike = float(contract.strike)
    moneyness = abs(price - strike) / strike

    # For calls:
    if contract.right == 'C':
        if price > strike:  # ITM
            return min(0.95, 0.7 + 0.25 * moneyness)  # 0.7 to 0.95 based on moneyness
        elif price < strike:  # OTM
            return max(0.05, 0.3 - 0.25 * moneyness)  # 0.05 to 0.3 based on moneyness
        else:  # ATM
            return 0.5
    # For puts:
    else:
        if price < strike:  # ITM
            return max(-0.95, -0.7 - 0.25 * moneyness)  # -0.95 to -0.7 based on moneyness
        elif price > strike:  # OTM
            return min(-0.05, -0.3 + 0.25 * moneyness)  # -0.3 to -0.05 based on moneyness
        else:  # ATM
            return -0.5

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

        if contract.secType == 'STK':
            # Stock delta is always 1 * position size
            return pos_size
            
        elif contract.secType == 'OPT':
            # Get option delta
            contract.exchange = 'SMART'
            contract.primaryExchange = 'AMEX'
            
            # First try to get real market data
            ticker = ib_instance.reqMktData(contract, '', False, False)
            ib_instance.sleep(1.0)  # Wait for market data
            
            if ticker and ticker.modelGreeks and ticker.modelGreeks.delta is not None:
                contract_delta = ticker.modelGreeks.delta
                logger.info(f"Got market data delta for {contract.localSymbol}: {contract_delta}")
            else:
                # If market data unavailable, calculate theoretical delta
                portfolio_items = [item for item in ib_instance.portfolio() if item.contract.conId == contract.conId]
                if portfolio_items:
                    price = portfolio_items[0].marketPrice
                    contract_delta = get_theoretical_delta(contract, price)
                    logger.info(f"Using theoretical delta for {contract.localSymbol}: {contract_delta}")
                else:
                    # Fallback to approximate ATM delta
                    contract_delta = 0.5 if contract.right == 'C' else -0.5
                    logger.info(f"Using fallback delta for {contract.localSymbol}: {contract_delta}")
            
            # Calculate total position delta
            multiplier = float(contract.multiplier) if hasattr(contract, "multiplier") else 100.0
            pos_delta = pos_size * contract_delta * multiplier
            logger.info(f"Final position delta for {contract.localSymbol}: {pos_delta}")
            return pos_delta
            
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
