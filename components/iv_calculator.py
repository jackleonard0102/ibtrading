# iv_calculator.py
from ib_insync import Stock, Option
from components.ib_connection import ib
import math
from scipy.stats import norm
from datetime import datetime

def get_stock_list():
    """
    Retrieve a list of stock symbols from the current portfolio.
    """
    try:
        positions = ib.positions()
        stock_symbols = list(set([p.contract.symbol for p in positions if p.contract.secType == 'STK']))
        return sorted(stock_symbols)
    except Exception as e:
        print(f"Error in get_stock_list: {e}")
        return []

def get_nearest_option(stock, stock_price):
    """
    Retrieve the nearest option for the given stock symbol dynamically.
    Finds the expiration date and strike closest to the current stock price.
    """
    # Request all option chains for the stock
    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
    if not chains:
        raise ValueError(f"No option chains found for {stock.symbol}")

    chain = next((c for c in chains if c.exchange == 'SMART'), chains[0])
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
        right="C",  # 'C' for Call option
        exchange="SMART"
    )
    ib.qualifyContracts(option_contract)
    return option_contract

def calculate_iv(S, K, T, r, market_price, call_put='C'):
    def d1(S, K, T, r, sigma):
        return (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
    
    def d2(S, K, T, r, sigma):
        return d1(S, K, T, r, sigma) - sigma * math.sqrt(T)
    
    def option_price(S, K, T, r, sigma, call_put='C'):
        d_1 = d1(S, K, T, r, sigma)
        d_2 = d2(S, K, T, r, sigma)
        
        if call_put == 'C':
            return S * norm.cdf(d_1) - K * math.exp(-r * T) * norm.cdf(d_2)
        else:
            return K * math.exp(-r * T) * norm.cdf(-d_2) - S * norm.cdf(-d_1)

    sigma = 0.25
    tolerance = 0.0001
    max_iterations = 100

    for _ in range(max_iterations):
        option_price_est = option_price(S, K, T, r, sigma, call_put)
        vega = S * norm.pdf(d1(S, K, T, r, sigma)) * math.sqrt(T)
        sigma_diff = (option_price_est - market_price) / vega
        sigma -= sigma_diff

        if abs(sigma_diff) < tolerance:
            return sigma

    return sigma

def get_iv(symbol):
    try:
        stock = Stock(symbol, 'SMART', 'USD')
        ib.qualifyContracts(stock)
        stock_data = ib.reqMktData(stock, '', False, False)
        ib.sleep(2)

        stock_price = stock_data.last or (stock_data.bid + stock_data.ask) / 2
        if stock_price is None or stock_price <= 0:
            raise ValueError(f"Invalid stock price for {symbol}: {stock_price}")

        option_contract = get_nearest_option(stock, stock_price)
        option_data = ib.reqMktData(option_contract, '', False, False)
        ib.sleep(2)

        K = option_contract.strike
        expiration_date = datetime.strptime(option_contract.lastTradeDateOrContractMonth, '%Y%m%d')
        T = (expiration_date - datetime.now()).days / 365.0
        r = 0.01
        market_price = option_data.last or (option_data.bid + option_data.ask) / 2
        if market_price is None or market_price <= 0:
            raise ValueError(f"Invalid option market price for {symbol}")

        iv = calculate_iv(stock_price, K, T, r, market_price, call_put='C')
        return iv
    except Exception as e:
        print(f"Error fetching IV for {symbol}: {str(e)}")
        return None
