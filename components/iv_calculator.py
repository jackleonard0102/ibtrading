"""Interactive Brokers IV calculator module with improved async handling."""

import numpy as np
from scipy.stats import norm
from datetime import datetime
import asyncio
from ib_insync import Stock, Option, util
from components.ib_connection import ib
import logging
import sys

# Configure module logger
logger = logging.getLogger(__name__)

async def get_market_data_async(contract, timeout=5, max_retries=3):
    """Get market data asynchronously with proper timeout and cleanup."""
    ticker = None
    for attempt in range(max_retries):
        try:
            ticker = ib.reqMktData(contract)
            
            # Wait for initial data
            for _ in range(50):  # Try for 5 seconds
                await asyncio.sleep(0.1)
                
                if hasattr(ticker, 'bid') and ticker.bid is not None and ticker.ask is not None:
                    price = (ticker.bid + ticker.ask) / 2
                    if price > 0:
                        logger.info(f"Got market data for {contract.symbol}: bid={ticker.bid}, ask={ticker.ask}, mid={price}")
                        return price
                elif hasattr(ticker, 'last') and ticker.last is not None and ticker.last > 0:
                    logger.info(f"Got market data for {contract.symbol}: last={ticker.last}")
                    return ticker.last
                elif hasattr(ticker, 'close') and ticker.close is not None and ticker.close > 0:
                    logger.info(f"Got market data for {contract.symbol}: close={ticker.close}")
                    return ticker.close
                    
            if attempt < max_retries - 1:
                logger.info(f"Retrying market data request for {contract.symbol} (attempt {attempt + 2})")
                
        except Exception as e:
            logger.error(f"Error getting market data for {contract.symbol} (attempt {attempt + 1}): {str(e)}")
        finally:
            if ticker:
                ib.cancelMktData(contract)
                await asyncio.sleep(0.1)
                
    logger.error(f"Failed to get market data for {contract.symbol} after {max_retries} attempts")
    return None

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
        
        # Check for boundary conditions
        price_low = black_scholes(S, K, T, r, sigma_low, option_type)
        price_high = black_scholes(S, K, T, r, sigma_high, option_type)
        
        if price_low is None or price_high is None:
            return None
            
        if option_price <= price_low:
            return sigma_low
        if option_price >= price_high:
            return sigma_high
            
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
                
        return (sigma_low + sigma_high) / 2
    except Exception as e:
        logger.error(f"Error calculating implied volatility: {str(e)}")
        return None

def parse_option_symbol(symbol):
    """Parse IB option symbol format."""
    try:
        if not isinstance(symbol, str):
            return None
            
        # Special case for simple stock symbols
        if len(symbol.strip().split()) == 1 and symbol.strip().isalpha():
            return None
            
        # Remove extra spaces and split
        symbol = " ".join(symbol.split())
        parts = symbol.split()
        
        if len(parts) != 2:
            return None
            
        underlying = parts[0]
        details = parts[1]
        
        if len(details) < 15 or not details[6] in ['P', 'C']:
            return None
            
        expiry = f"20{details[:6]}"
        right = details[6]
        strike = float(details[7:]) / 1000.0
        
        return {
            'underlying': underlying,
            'expiry': expiry,
            'right': right,
            'strike': strike
        }
    except Exception as e:
        logger.error(f"Error parsing option symbol {symbol}: {str(e)}")
        return None

async def get_next_valid_expiration(chains):
    """Get next valid expiration date."""
    try:
        today = datetime.now()
        min_days = 7  # Minimum days to expiration
        
        for expiration in sorted(chains[0].expirations):
            expiry_date = datetime.strptime(expiration, '%Y%m%d')
            days_to_expiry = (expiry_date - today).days
            if days_to_expiry >= min_days:
                return expiration
                
        return None
    except Exception as e:
        logger.error(f"Error getting next expiration: {str(e)}")
        return None

async def get_iv(symbol):
    """Calculate implied volatility for a symbol."""
    try:
        # Wait for market data connection
        await asyncio.sleep(1)
        
        is_option = parse_option_symbol(symbol) is not None
        underlying = parse_option_symbol(symbol)['underlying'] if is_option else symbol
        
        # Step 1: Get underlying stock data
        stock = Stock(underlying, 'SMART', 'USD')
        if not await ib.qualifyContractsAsync(stock):
            logger.error(f"Could not qualify stock contract for {underlying}")
            return None
            
        S = await get_market_data_async(stock, max_retries=3)
        if S is None:
            logger.error(f"Could not get valid stock price for {underlying}")
            return None
            
        logger.info(f"Got stock price for {underlying}: {S}")
        
        # Step 2: Get option chain data
        chains = await ib.reqSecDefOptParamsAsync(underlying, '', 'STK', stock.conId)
        if not chains:
            logger.error(f"No option chains found for {underlying}")
            return None
            
        # Get chain for available exchange
        chain = next((c for c in chains if c.exchange == 'SMART'), None)
        if not chain:
            chain = next((c for c in chains if c.exchange == 'AMEX'), None)
            if not chain:
                logger.error(f"No suitable exchange found for {underlying}")
                return None
                
        exchange = chain.exchange
        logger.info(f"Using {exchange} exchange for options")
        
        if is_option:
            # Handle specific option contract
            option_data = parse_option_symbol(symbol)
            
            option = Option(
                symbol=underlying,
                lastTradeDateOrContractMonth=option_data['expiry'],
                strike=option_data['strike'],
                right=option_data['right'],
                exchange=exchange,
                multiplier='100',
                currency='USD'
            )
            
            if not await ib.qualifyContractsAsync(option):
                logger.error(f"Could not qualify option contract: {symbol}")
                return None
                
            option_price = await get_market_data_async(option, max_retries=3)
            if option_price is None:
                logger.error(f"Could not get valid option price for {symbol}")
                return None
                
            logger.info(f"Got option price: {option_price}")
            
            expiry_date = datetime.strptime(option_data['expiry'], '%Y%m%d')
            T = max((expiry_date - datetime.now()).days / 365.0, 0.000001)
            
            # Calculate IV for single option
            iv = calculate_iv(option_price, S, option_data['strike'], T, 0.05, option_data['right'])
            if iv is not None:
                logger.info(f"Calculated IV for {symbol}: {iv:.2%}")
            return iv
            
        else:
            # Handle stock symbol (use ATM options)
            # Get valid strikes near current price
            atm_strike = min(chain.strikes, key=lambda x: abs(x - S))
            strikes = [strike for strike in chain.strikes 
                      if 0.8 * S <= strike <= 1.2 * S]
            
            if not strikes:
                logger.error(f"No suitable strikes found for {symbol}")
                return None
                
            # Get valid expiration
            expiration = await get_next_valid_expiration(chains)
            if not expiration:
                logger.error(f"No valid expiration found for {symbol}")
                return None
                
            strikes.sort(key=lambda x: abs(x - S))
            for strike in strikes[:3]:  # Try 3 closest strikes
                call = Option(underlying, expiration, strike, 'C', exchange, '100', 'USD')
                put = Option(underlying, expiration, strike, 'P', exchange, '100', 'USD')
                
                if not await ib.qualifyContractsAsync(call, put):
                    continue
                    
                # Get prices
                call_price = await get_market_data_async(call, max_retries=2)
                put_price = await get_market_data_async(put, max_retries=2)
                
                if call_price is None and put_price is None:
                    continue
                    
                expiry_date = datetime.strptime(expiration, '%Y%m%d')
                T = max((expiry_date - datetime.now()).days / 365.0, 0.000001)
                
                # Calculate IV
                call_iv = put_iv = None
                if call_price:
                    call_iv = calculate_iv(call_price, S, strike, T, 0.05, "C")
                if put_price:
                    put_iv = calculate_iv(put_price, S, strike, T, 0.05, "P")
                    
                if call_iv and put_iv:
                    iv = (call_iv + put_iv) / 2
                    logger.info(f"Calculated IV for {symbol} at strike {strike}: {iv:.2%}")
                    return iv
                elif call_iv:
                    logger.info(f"Calculated IV for {symbol} using call: {call_iv:.2%}")
                    return call_iv
                elif put_iv:
                    logger.info(f"Calculated IV for {symbol} using put: {put_iv:.2%}")
                    return put_iv
                    
            logger.error(f"Could not calculate valid IV for {symbol}")
            return None
            
    except Exception as e:
        logger.error(f"Error calculating IV for {symbol}: {str(e)}")
        logger.error(f"Stack trace: {sys.exc_info()[2]}")
        return None
    finally:
        await asyncio.sleep(0)
