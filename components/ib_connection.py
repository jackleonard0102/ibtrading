from ib_insync import IB, Stock, Option

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

    # Fetch option chain for the symbol
    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
    chain = chains[0]

    # Choose a valid strike price near the current stock price
    strikes = sorted([strike for strike in chain.strikes if abs(strike - stock_data.marketPrice()) < stock_data.marketPrice() * 0.5])
    if not strikes:
        raise ValueError(f"No valid strikes available for {symbol} near price {stock_data.marketPrice()}")
    
    # Get the closest valid strike
    closest_strike = min(strikes, key=lambda x: abs(x - stock_data.marketPrice()))

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
