from ib_insync import IB, Stock, Option

ib = IB()

def connect_ib(port=7497):
    try:
        ib.connect('127.0.0.1', port, clientId=1)
        print("Connected to IBKR!")
        return True
    except Exception as e:
        print(f"Error connecting to IBKR: {e}")
        return False

def define_stock_contract(symbol, exchange='SMART', currency='USD'):
    contract = Stock(symbol, exchange, currency)
    ib.qualifyContracts(contract)
    return contract

def get_portfolio_positions():
    return ib.positions()

def fetch_market_data_for_stock(contract):
    try:
        ib.qualifyContracts(contract)
        market_data = ib.reqMktData(contract, '', False, False)
        ib.sleep(2)  # Wait for data to populate
        return market_data
    except Exception as e:
        print(f"Error fetching market data for {contract.symbol}: {e}")
        return None

def get_delta(position):
    """
    Calculate delta for both stock and option positions.
    """
    contract = position.contract
    try:
        if contract.secType == 'STK':
            # Delta is 1 per share for stocks
            return position.position * 1
        elif contract.secType == 'OPT':
            ib.qualifyContracts(contract)
            # Request option market data with Greeks
            ib.reqMarketDataType(4)  # Use delayed-frozen data if real-time data is not available
            market_data = ib.reqMktData(contract, '', False, False)
            ib.sleep(2)  # Wait for data to populate
            if market_data.modelGreeks:
                # Delta for options is per contract; multiply by position size and 100 (shares per contract)
                delta = position.position * market_data.modelGreeks.delta * 100
                return delta
            else:
                print(f"No Greeks available for option {contract.localSymbol}")
                return 0
        else:
            return 0
    except Exception as e:
        print(f"Error fetching delta for {contract.symbol}: {e}")
        return 0
