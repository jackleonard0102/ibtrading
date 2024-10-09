from ib_insync import IB, Stock, Option
import datetime

ib = IB()

def connect_ib(port=7497):
    """
    Connect to IB Gateway or TWS on the specified port.
    """
    try:
        ib.connect('127.0.0.1', port, clientId=1)
        print("Connected to IBKR!")
        return True
    except Exception as e:
        print(f"Error connecting to IBKR: {e}")
        print("Please ensure that TWS or IB Gateway is running and configured to accept API connections.")
        print(f"Check if the port {port} is correct and matches the one configured in TWS or IB Gateway.")
        return False

def get_portfolio_positions():
    """
    Fetch all portfolio positions dynamically.
    """
    return ib.positions()

def get_market_data_for_iv(symbol):
    """
    Fetch the current market data and option chain for the specified symbol.
    """
    stock = Stock(symbol, 'SMART', 'USD')
    ib.qualifyContracts(stock)

    stock_data = ib.reqMktData(stock)
    ib.sleep(2)  # Wait longer for market data to arrive

    if stock_data.marketPrice() is None or stock_data.marketPrice() == 0:
        error_msg = f"Unable to fetch valid market price for {symbol}. "
        error_msg += f"Last price: {stock_data.last}, Close price: {stock_data.close}, "
        error_msg += f"Bid: {stock_data.bid}, Ask: {stock_data.ask}"
        raise ValueError(error_msg)

    market_price = stock_data.marketPrice()

    # Fetch option chain for the symbol
    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
    if not chains:
        raise ValueError(f"No option chain available for {symbol}")
    
    chain = chains[0]

    # Choose a valid strike price near the current stock price
    strikes = [strike for strike in chain.strikes if abs(strike - market_price) / market_price < 0.1]
    if not strikes:
        raise ValueError(f"No valid strikes available for {symbol} near price {market_price}")
    
    # Get the closest valid strike
    closest_strike = min(strikes, key=lambda x: abs(x - market_price))

    # Choose the nearest expiration date
    expirations = sorted(chain.expirations)
    if not expirations:
        raise ValueError("No valid expirations available")

    nearest_expiry = expirations[0]

    # Define the option contract (Call Option example)
    option = Option(symbol, nearest_expiry, closest_strike, 'C', 'SMART')

    # Qualify the option contract
    ib.qualifyContracts(option)

    # Fetch option market data
    option_data = ib.reqMktData(option)
    ib.sleep(2)  # Wait longer for market data to arrive

    if option_data.marketPrice() is None or option_data.marketPrice() == 0:
        error_msg = f"Unable to fetch valid option market price for {symbol}. "
        error_msg += f"Last price: {option_data.last}, Close price: {option_data.close}, "
        error_msg += f"Bid: {option_data.bid}, Ask: {option_data.ask}"
        raise ValueError(error_msg)

    return stock_data, option_data

def get_historical_data_for_rv(symbol, duration='1 D', bar_size='1 min'):
    """
    Fetch historical price data for the specified symbol.
    This is used for calculating Realized Volatility (RV).
    """
    stock = Stock(symbol, 'SMART', 'USD')

    # Fetch historical data (e.g., 'MIDPOINT' or 'TRADES')
    bars = ib.reqHistoricalData(
        stock,
        endDateTime='',
        durationStr=duration,  # 1 day by default
        barSizeSetting=bar_size,  # 1-minute bars
        whatToShow='MIDPOINT',  # Fetch the midpoint price
        useRTH=True  # Only use Regular Trading Hours
    )

    # Extract the closing prices
    prices = [bar.close for bar in bars]
    return prices
