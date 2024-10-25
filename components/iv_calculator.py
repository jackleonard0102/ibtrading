import numpy as np
from scipy.stats import norm
from datetime import datetime
from ib_insync import Stock, Option
from components.ib_connection import ib
import threading

def black_scholes(S, K, T, r, sigma, option_type="C"):
    """Calculate option price using Black-Scholes model
    
    Parameters:
    S: Current stock price
    K: Strike price
    T: Time to maturity (in years)
    r: Risk-free interest rate
    sigma: Volatility
    option_type: "C" for Call, "P" for Put
    """
    
    try:
        # Calculate d1 and d2
        d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
        d2 = d1 - sigma*np.sqrt(T)
        
        if option_type == "C":
            price = S*norm.cdf(d1) - K*np.exp(-r*T)*norm.cdf(d2)
        else:
            price = K*np.exp(-r*T)*norm.cdf(-d2) - S*norm.cdf(-d1)
        
        return price
    except Exception as e:
        print(f"Error in Black-Scholes calculation: {str(e)}")
        return None

def newton_implied_vol(target_price, S, K, T, r, option_type="C", max_iter=100, precision=1e-5):
    """Calculate implied volatility using Newton-Raphson method"""
    
    try:
        # Initial guess for volatility
        sigma = 0.3
        
        for i in range(max_iter):
            price = black_scholes(S, K, T, r, sigma, option_type)
            if price is None:
                return None
                
            # Calculate vega
            d1 = (np.log(S/K) + (r + sigma**2/2)*T) / (sigma*np.sqrt(T))
            vega = S * np.sqrt(T) * norm.pdf(d1)
            
            diff = target_price - price
            
            if abs(diff) < precision:
                return sigma
            
            # Update volatility estimate
            sigma = sigma + diff/vega
            
            # Ensure volatility stays within reasonable bounds
            if sigma <= 0 or sigma > 5:
                return None
        
        return None
    except Exception as e:
        print(f"Error in Newton-Raphson calculation: {str(e)}")
        return None

def get_option_market_data(option_contract):
    """Get market data for an option contract"""
    try:
        ticker = ib.reqMktData(option_contract)
        ib.sleep(2)  # Wait for market data
        
        if ticker.last or ticker.close:
            return ticker.last or ticker.close
            
        # If no last or close price, try mid price
        if ticker.bid and ticker.ask:
            return (ticker.bid + ticker.ask) / 2
            
        return None
    finally:
        ib.cancelMktData(option_contract)

def calculate_iv(symbol):
    """Calculate implied volatility using Black-Scholes model"""
    try:
        # Create stock contract and get current price
        stock = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(stock)
        
        stock_ticker = ib.reqMktData(stock)
        ib.sleep(1)
        
        S = stock_ticker.last or stock_ticker.close
        if not S:
            print(f"Could not get current price for {symbol}")
            return None
            
        ib.cancelMktData(stock)
        
        # Get option chain
        chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
        chain = next(c for c in chains if c.exchange == 'SMART')
        
        # Get ATM options
        strikes = [strike for strike in chain.strikes
                  if 0.8 * S < strike < 1.2 * S]
                  
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
        call = Option(symbol, expiration, atm_strike, 'C', 'SMART')
        put = Option(symbol, expiration, atm_strike, 'P', 'SMART')
        
        ib.qualifyContracts(call, put)
        
        # Get option prices
        call_price = get_option_market_data(call)
        put_price = get_option_market_data(put)
        
        if not (call_price or put_price):
            print(f"Could not get option prices for {symbol}")
            return None
        
        # Calculate time to expiration
        expiry_date = datetime.strptime(expiration, '%Y%m%d')
        T = (expiry_date - datetime.now()).days / 365.0
        
        # Use risk-free rate (approximate with 3-month Treasury rate)
        r = 0.05  # This should ideally be fetched from a reliable source
        
        # Calculate IV for both call and put
        call_iv = put_iv = None
        if call_price:
            call_iv = newton_implied_vol(call_price, S, atm_strike, T, r, "C")
        if put_price:
            put_iv = newton_implied_vol(put_price, S, atm_strike, T, r, "P")
        
        # Return average IV if both available, otherwise return the one available
        if call_iv is not None and put_iv is not None:
            return (call_iv + put_iv) / 2
        return call_iv if call_iv is not None else put_iv
        
    except Exception as e:
        print(f"Error calculating IV for {symbol}: {str(e)}")
        return None

def get_iv(symbol):
    """Get implied volatility for a symbol"""
    try:
        result = [None]  # Use a list to store result from thread
        
        def run_calculation():
            result[0] = calculate_iv(symbol)
        
        # Run calculation in a separate thread
        thread = threading.Thread(target=run_calculation)
        thread.daemon = True
        thread.start()
        thread.join(timeout=10)  # Wait up to 10 seconds for the calculation
        
        return result[0]
    except Exception as e:
        print(f"Error calculating IV for {symbol}: {str(e)}")
        return None
