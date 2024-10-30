"""Interactive Brokers IV calculator module with improved async handling."""

import numpy as np
from scipy.stats import norm
from datetime import datetime
import asyncio
from ib_insync import Stock, Option, util
from components.ib_connection import ib
import logging
import nest_asyncio

# Configure module logger
logger = logging.getLogger(__name__)

nest_asyncio.apply()

async def get_market_data_async(contract, timeout=5):
    """Get market data asynchronously with proper timeout and cleanup."""
    ticker = None
    try:
        ticker = ib.reqMktData(contract)
        end_time = datetime.now().timestamp() + timeout
        
        while datetime.now().timestamp() < end_time:
            if ticker.last or ticker.close or (ticker.bid and ticker.ask):
                break
            await asyncio.sleep(0.1)
        
        price = None
        if hasattr(ticker, 'last') and ticker.last and ticker.last > 0:
            price = ticker.last
        elif hasattr(ticker, 'close') and ticker.close and ticker.close > 0:
            price = ticker.close
        elif hasattr(ticker, 'bid') and hasattr(ticker, 'ask') and ticker.bid and ticker.ask:
            price = (ticker.bid + ticker.ask) / 2
            
        return price
        
    except Exception as e:
        logger.error(f"Error getting market data: {str(e)}")
        return None
    finally:
        if ticker:
            ib.cancelMktData(contract)

def black_scholes(S, K, T, r, sigma, option_type="C"):
    """Calculate option price using Black-Scholes model."""
    try:
        if not all(isinstance(x, (int, float)) for x in [S, K, T, r, sigma]):
            return None
        if any(x <= 0 for x in [S, K, T, sigma]) or not (0 <= r <= 1):
            return None
            
        d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == "C":
            price = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
            
        return float(price) if np.isfinite(price) and price >= 0 else None
    except Exception as e:
        logger.error(f"Error in Black-Scholes calculation: {str(e)}")
        return None

def calculate_iv(option_price, S, K, T, r, option_type="C"):
    """Calculate implied volatility using binary search."""
    try:
        if not all(isinstance(x, (int, float)) for x in [option_price, S, K, T, r]):
            return None
        if any(x <= 0 for x in [option_price, S, K, T]) or not (0 <= r <= 1):
            return None
            
        sigma_low = 0.0001
        sigma_high = 5.0
        tolerance = 0.00001
        max_iterations = 100
        
        for _ in range(max_iterations):
            sigma = (sigma_low + sigma_high) / 2
            price = black_scholes(S, K, T, r, sigma, option_type)
            
            if price is None:
                return None
                
            diff = price - option_price
            
            if abs(diff) < tolerance:
                if 0 <= sigma <= 5.0:
                    return sigma
                return None
            elif diff > 0:
                sigma_high = sigma
            else:
                sigma_low = sigma
                
            if abs(sigma_high - sigma_low) < 1e-7:
                break
                
        return None
    except Exception as e:
        logger.error(f"Error calculating implied volatility: {str(e)}")
        return None

async def get_iv(symbol):
    """Calculate implied volatility for a symbol with improved async handling."""
    try:
        # Create stock contract
        stock = Stock(symbol, 'SMART', 'USD')
        await ib.qualifyContractsAsync(stock)
        
        # Get current stock price
        S = await get_market_data_async(stock, timeout=5)
        if S is None:
            logger.error(f"Could not get valid stock price for {symbol}")
            return None
            
        # Get option chain
        chains = await ib.reqSecDefOptParamsAsync(stock.symbol, '', stock.secType, stock.conId)
        if not chains:
            logger.error(f"Could not get option chain for {symbol}")
            return None
            
        chain = next((c for c in chains if c.exchange == 'SMART'), None)
        if not chain:
            logger.error(f"No SMART exchange options for {symbol}")
            return None
            
        # Get ATM strikes
        strikes = sorted([strike for strike in chain.strikes
                        if 0.8 * S <= strike <= 1.2 * S])
        if not strikes:
            logger.error(f"No suitable strikes found for {symbol}")
            return None
            
        # Get nearest expiration
        expirations = sorted(exp for exp in chain.expirations)
        if not expirations:
            logger.error(f"No expirations found for {symbol}")
            return None
            
        expiration = expirations[0]
        atm_strike = min(strikes, key=lambda x: abs(x - S))
        
        # Create ATM call and put options
        call = Option(symbol, expiration, atm_strike, 'C', 'SMART')
        put = Option(symbol, expiration, atm_strike, 'P', 'SMART')
        
        await ib.qualifyContractsAsync(call, put)
        
        # Get option prices asynchronously
        tasks = [
            get_market_data_async(call, timeout=5),
            get_market_data_async(put, timeout=5)
        ]
        call_price, put_price = await asyncio.gather(*tasks)
        
        if not call_price and not put_price:
            logger.error(f"Could not get valid option prices for {symbol}")
            return None
            
        # Calculate time to expiration
        expiry_date = datetime.strptime(expiration, '%Y%m%d')
        T = max((expiry_date - datetime.now()).days / 365.0, 0.000001)
        
        r = 0.05  # Current approximate risk-free rate
        
        # Calculate IV for both options
        call_iv = put_iv = None
        if call_price:
            call_iv = calculate_iv(call_price, S, atm_strike, T, r, "C")
        if put_price:
            put_iv = calculate_iv(put_price, S, atm_strike, T, r, "P")
            
        if call_iv and put_iv:
            return (call_iv + put_iv) / 2
        return call_iv if call_iv is not None else put_iv
            
    except Exception as e:
        logger.error(f"Error calculating IV for {symbol}: {str(e)}")
        return None
    finally:
        await asyncio.sleep(0)
