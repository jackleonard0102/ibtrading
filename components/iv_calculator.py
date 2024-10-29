import numpy as np
from scipy.stats import norm
from datetime import datetime
from ib_insync import Stock, Option
from components.ib_connection import ib
import nest_asyncio

nest_asyncio.apply()

def get_market_data(contract, timeout=5):
    """Get market data for a contract with improved timeout"""
    try:
        # Request market data
        ticker = ib.reqMktData(contract)
        ib.sleep(timeout)  # Increased wait time for data arrival
        
        # Get price with more comprehensive checks
        price = None
        if hasattr(ticker, 'last') and ticker.last and ticker.last > 0:
            price = ticker.last
        elif hasattr(ticker, 'close') and ticker.close and ticker.close > 0:
            price = ticker.close
        elif hasattr(ticker, 'bid') and hasattr(ticker, 'ask') and ticker.bid and ticker.ask and ticker.bid > 0 and ticker.ask > 0:
            price = (ticker.bid + ticker.ask) / 2
            
        # Cancel market data subscription
        ib.cancelMktData(contract)
        
        if price and price > 0:
            return price
        return None
    except Exception as e:
        print(f"Error getting market data: {str(e)}")
        return None

def black_scholes(S, K, T, r, sigma, option_type="C"):
    """Calculate option price using Black-Scholes model with improved validation"""
    try:
        # Improved validation
        if not all(isinstance(x, (int, float)) for x in [S, K, T, r, sigma]):
            return None
        if any(x <= 0 for x in [S, K, T, sigma]) or not (0 <= r <= 1):
            return None
            
        # Calculate d1 and d2
        d1 = (np.log(S/K) + (r + 0.5 * sigma**2) * T) / (sigma * np.sqrt(T))
        d2 = d1 - sigma * np.sqrt(T)
        
        if option_type == "C":
            price = S * norm.cdf(d1) - K * np.exp(-r*T) * norm.cdf(d2)
        else:
            price = K * np.exp(-r*T) * norm.cdf(-d2) - S * norm.cdf(-d1)
        
        return float(price) if np.isfinite(price) and price >= 0 else None
    except Exception as e:
        print(f"Error in Black-Scholes calculation: {str(e)}")
        return None

def calculate_iv(option_price, S, K, T, r, option_type="C"):
    """Calculate implied volatility using binary search with improved bounds and convergence"""
    try:
        # Improved validation
        if not all(isinstance(x, (int, float)) for x in [option_price, S, K, T, r]):
            return None
        if any(x <= 0 for x in [option_price, S, K, T]) or not (0 <= r <= 1):
            return None
            
        # Wider bounds for high volatility scenarios
        sigma_low = 0.0001
        sigma_high = 10.0  # Increased upper bound
        tolerance = 0.00001  # Tighter tolerance
        max_iterations = 200  # More iterations for better convergence
        
        for i in range(max_iterations):
            sigma = (sigma_low + sigma_high) / 2
            price = black_scholes(S, K, T, r, sigma, option_type)
            
            if price is None:
                return None
                
            diff = price - option_price
            
            if abs(diff) < tolerance:
                # Additional validation for the result
                if 0 <= sigma <= 10.0:
                    return sigma
                return None
            elif diff > 0:
                sigma_high = sigma
            else:
                sigma_low = sigma
                
            # Check if bounds are getting too close
            if abs(sigma_high - sigma_low) < 1e-8:
                break
        
        return None  # Failed to converge
    except Exception as e:
        print(f"Error calculating implied volatility: {str(e)}")
        return None

def get_iv(symbol):
    """Calculate implied volatility for a symbol with improved error handling and data validation"""
    try:
        # Create and qualify stock contract
        stock = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(stock)
        
        # Get current stock price with longer timeout
        S = get_market_data(stock, timeout=5)
        if S is None:
            print(f"Could not get valid stock price for {symbol}")
            return None
        
        # Get option chain
        chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
        if not chains:
            print(f"Could not get option chain for {symbol}")
            return None
            
        # Get SMART exchange chain
        chain = next((c for c in chains if c.exchange == 'SMART'), None)
        if not chain:
            print(f"No SMART exchange options for {symbol}")
            return None
        
        # Get ATM strikes with wider range for better accuracy
        strikes = [strike for strike in chain.strikes
                  if 0.7 * S <= strike <= 1.3 * S]  # Wider strike range
        if not strikes:
            print(f"No suitable strikes found for {symbol}")
            return None
        
        # Get nearest expiration
        expirations = sorted(chain.expirations)
        if not expirations:
            print(f"No expirations found for {symbol}")
            return None
            
        expiration = expirations[0]
        atm_strike = min(strikes, key=lambda x: abs(x - S))
        
        # Create ATM call and put options
        call = Option(symbol, expiration, atm_strike, 'C', 'SMART', '100', 'USD')
        put = Option(symbol, expiration, atm_strike, 'P', 'SMART', '100', 'USD')
        
        # Qualify contracts
        ib.qualifyContracts(call, put)
        
        # Get option prices with longer timeout
        call_price = get_market_data(call, timeout=5)
        put_price = get_market_data(put, timeout=5)
        
        if not call_price and not put_price:
            print(f"Could not get valid option prices for {symbol}")
            return None
        
        # Calculate time to expiration with improved precision
        expiry_date = datetime.strptime(expiration, '%Y%m%d')
        T = max((expiry_date - datetime.now()).days / 365.0, 0.000001)
        
        # Use current risk-free rate (approximate)
        r = 0.03  # Updated to current approximate risk-free rate
        
        # Calculate IV for both options with validation
        call_iv = put_iv = None
        if call_price:
            call_iv = calculate_iv(call_price, S, atm_strike, T, r, "C")
        if put_price:
            put_iv = calculate_iv(put_price, S, atm_strike, T, r, "P")
        
        # Return average IV if both available, otherwise return the one available
        if call_iv is not None and put_iv is not None:
            return (call_iv + put_iv) / 2
        return call_iv if call_iv is not None else put_iv
        
    except Exception as e:
        print(f"Error calculating IV for {symbol}: {str(e)}")
        return None
    finally:
        # Ensure market data subscriptions are cancelled
        try:
            ib.sleep(0)  # Allow pending callbacks to be processed
        except:
            pass
