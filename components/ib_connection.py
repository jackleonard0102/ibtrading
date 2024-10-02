from ib_insync import IB, Stock, Option

ib = IB()

def connect_ib(port=7497):
    """
    Connect to IB Gateway or TWS on the specified port.
    """
    try:
        ib.connect('127.0.0.1', port, clientId=1)
        print("Connected to IBKR!")
    except Exception as e:
        print(f"Error connecting to IBKR: {e}")

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

    chains = ib.reqSecDefOptParams(stock.symbol, '', stock.secType, stock.conId)
    chain = chains[0]

    closest_strike = min(chain.strikes, key=lambda x: abs(x - stock_data.marketPrice()))
    nearest_expiry = sorted(chain.expirations)[0]

    option = Option(symbol, nearest_expiry, closest_strike, 'C', 'SMART')
    ib.qualifyContracts(option)
    option_data = ib.reqMktData(option)

    return stock_data, option_data

def get_historical_data_for_rv(symbol):
    """
    Fetch historical price data for RV calculation.
    """
    stock = Stock(symbol, 'SMART', 'USD')
    bars = ib.reqHistoricalData(stock, endDateTime='', durationStr='1 D', barSizeSetting='1 min')
    return [bar.close for bar in bars]
