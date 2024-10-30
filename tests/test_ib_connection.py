"""Tests for the IB connection module."""

import pytest
from unittest.mock import Mock, patch
from components.ib_connection import (
    connect_ib,
    get_portfolio_positions,
    define_stock_contract,
    get_market_price,
    get_delta
)
from ib_insync import IB, Stock, Position, Contract

@pytest.fixture
def mock_ib():
    """Mock IB connection fixture."""
    with patch('components.ib_connection.ib', autospec=True) as mock:
        yield mock

@pytest.mark.asyncio
async def test_connect_ib_success(mock_ib):
    """Test successful IB connection."""
    mock_ib.isConnected.return_value = False
    mock_ib.connectAsync.return_value = None
    
    result = await connect_ib()
    assert result is True
    mock_ib.connectAsync.assert_called_once()

@pytest.mark.asyncio
async def test_connect_ib_already_connected(mock_ib):
    """Test when IB is already connected."""
    mock_ib.isConnected.return_value = True
    
    result = await connect_ib()
    assert result is True
    mock_ib.connectAsync.assert_not_called()

def test_define_stock_contract():
    """Test stock contract creation."""
    contract = define_stock_contract('AAPL')
    assert isinstance(contract, Stock)
    assert contract.symbol == 'AAPL'
    assert contract.currency == 'USD'
    assert contract.exchange == 'SMART'

def test_get_portfolio_positions_empty(mock_ib):
    """Test empty portfolio positions."""
    mock_ib.isConnected.return_value = True
    mock_ib.positions.return_value = []
    
    result = get_portfolio_positions()
    assert result == []
    mock_ib.positions.assert_called_once()

def test_get_market_price(mock_ib):
    """Test market price retrieval."""
    mock_contract = Mock(symbol='AAPL', secType='STK')
    mock_portfolio_item = Mock(
        contract=mock_contract,
        marketPrice=150.0,
        marketValue=15000.0,
        unrealizedPNL=1000.0
    )
    mock_ib.portfolio.return_value = [mock_portfolio_item]
    
    price, value, pnl = get_market_price(mock_contract)
    assert price == 150.0
    assert value == 15000.0
    assert pnl == 1000.0

def test_get_delta_stock():
    """Test delta calculation for stock position."""
    mock_contract = Mock(secType='STK')
    mock_position = Mock(contract=mock_contract, position=100)
    mock_ib = Mock()
    
    delta = get_delta(mock_position, mock_ib)
    assert delta == 100.0

def test_get_delta_call_option():
    """Test delta calculation for call option."""
    mock_contract = Mock(
        symbol='AAPL',
        secType='OPT',
        right='C',
        lastTradeDateOrContractMonth='20240321',
        strike=150.0
    )
    mock_position = Mock(contract=mock_contract, position=1)
    mock_portfolio_item = Mock(
        contract=mock_contract
    )
    mock_ib = Mock()
    mock_ib.portfolio.return_value = [mock_portfolio_item]
    
    delta = get_delta(mock_position, mock_ib)
    assert delta == 0.5  # Test the approximate delta calculation