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
        return False

def get_portfolio_positions():
    """
    Fetch all portfolio positions dynamically.
    """
    return ib.positions()
