from ib_insync import Stock, Option
from components.ib_connection import ib
import math
from scipy.stats import norm

def calculate_iv(S, K, T, r, market_price, call_put='C'):
    # Helper functions to compute d1 and d2
    def d1(S, K, T, r, sigma):
        return (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    
    def d2(S, K, T, r, sigma):
        return d1(S, K, T, r, sigma) - sigma * math.sqrt(T)
    
    def option_price(S, K, T, r, sigma, call_put='C'):
        d_1 = d1(S, K, T, r, sigma)
        d_2 = d2(S, K, T, r, sigma)
        
        if call_put == 'C':  # Call option
            return S * norm.cdf(d_1) - K * math.exp(-r * T) * norm.cdf(d_2)
        elif call_put == 'P':  # Put option
            return K * math.exp(-r * T) * norm.cdf(-d_2) - S * norm.cdf(-d_1)

    # Initial guess for volatility
    sigma = 0.25
    tolerance = 0.0001
    max_iterations = 100

    for _ in range(max_iterations):
        option_price_est = option_price(S, K, T, r, sigma, call_put)
        vega = S * norm.pdf(d1(S, K, T, r, sigma)) * math.sqrt(T)

        # Update sigma using Newton-Raphson method
        sigma_diff = (option_price_est - market_price) / vega
        sigma = sigma - sigma_diff

        if abs(sigma_diff) < tolerance:
            return sigma

    return sigma

def get_nearest_option(stock, stock_price):
    """
    Retrieve the nearest option for the given stock symbol dynamically.
    We find the expiration date and strike closest to the current stock price.
    """
    # Request all option chains for the stock
    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
    if not chains:
        raise ValueError(f"No option chains found for {stock.symbol}")

    chain = chains[0]  # Use the first available chain
    expirations = sorted(chain.expirations)  # Sorted list of expiration dates
    strikes = sorted(chain.strikes)  # Sorted list of available strike prices

    # Find the nearest strike to the current stock price
    nearest_strike = min(strikes, key=lambda x: abs(x - stock_price))
    expiration = expirations[0]  # Use the nearest expiration

    # Return the option contract
    option_contract = Option(
        symbol=stock.symbol,
        lastTradeDateOrContractMonth=expiration,
        strike=nearest_strike,
        right="C",  # 'C' for Call
        exchange="SMART"
    )
    ib.qualifyContracts(option_contract)
    return option_contract

def get_iv(symbol):
    """
    Calculate the Implied Volatility (IV) for the given stock symbol using available option data and the Black-Scholes model.
    """
    try:
        # Define the stock and qualify its contract
        stock = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(stock)

        # Request market data for the stock
        stock_data = ib.reqMktData(stock)
        ib.sleep(2)

        if stock_data.bid is None or stock_data.ask is None:
            raise ValueError(f"Could not retrieve market data for {symbol}.")

        stock_price = stock_data.last or (stock_data.bid + stock_data.ask) / 2

        # Fetch nearest option dynamically
        option_contract = get_nearest_option(stock, stock_price)

        # Fetch option data
        option_data = ib.reqMktData(option_contract)
        ib.sleep(2)

        if option_data.last is None:
            raise ValueError(f"Could not retrieve option price for {symbol}.")

        # Parameters for Black-Scholes model
        K = option_contract.strike
        T = 1 / 12  # Time to expiration in years (e.g., 1 month = 1/12 years)
        r = 0.01  # Assumed risk-free rate (1%)
        market_price = option_data.last

        # Calculate IV using Black-Scholes
        iv = calculate_iv(stock_price, K, T, r, market_price, call_put='C')
        return iv
    except Exception as e:
        print(f"Error fetching IV for {symbol}: {str(e)}")
        return 0.0


def get_stock_list():
    try:
        positions = ib.positions()
        stock_symbols = list(set([p.contract.symbol for p in positions if p.contract.secType == 'STK']))
        return sorted(stock_symbols)
    except Exception as e:
        print(f"Error in get_stock_list: {e}")
        return []
