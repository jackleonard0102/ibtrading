# IB Trading Platform

An automated trading platform built using Interactive Brokers API for options trading with delta hedging and volatility analytics.

## Features

- **Auto Hedger**: Automatically manages portfolio delta by executing hedging trades
- **IV Calculator**: Calculates implied volatility for options
- **RV Calculator**: Computes realized volatility for underlying assets
- **Portfolio Management**: Real-time portfolio monitoring and position tracking
- **Advanced Analytics**: Delta calculation and risk metrics

## Installation

1. Clone the repository:
```bash
git clone https://github.com/yourusername/ibtrading.git
cd ibtrading
```

2. Create and activate virtual environment:
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Unix/macOS
source .venv/bin/activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

## Prerequisites

- Python 3.8+
- Interactive Brokers Trader Workstation (TWS) or IB Gateway
- Active Interactive Brokers account

## Configuration

1. Start TWS or IB Gateway
2. Enable API connections in TWS/Gateway settings
3. Configure port number (default: 7497 for TWS, 4001 for Gateway)

## Usage

1. Start the application:
```bash
python app.py
```

2. Connect to Interactive Brokers:
- Application will automatically attempt to connect
- Ensure TWS/Gateway is running and API connections are enabled

3. Use the Dashboard:
- Monitor portfolio positions
- Set up auto-hedging parameters
- View IV/RV calculations

## Testing

Run tests using pytest:
```bash
pytest tests/
```

## Project Structure

```
ibtrading/
├── app.py                  # Main application entry point
├── components/            
│   ├── auto_hedger.py     # Auto hedging implementation
│   ├── ib_connection.py   # IB API connection management
│   ├── iv_calculator.py   # Implied volatility calculations
│   └── rv_calculator.py   # Realized volatility calculations
├── ui/
│   └── dashboard.py       # Main dashboard GUI
├── config.py              # Configuration settings
├── requirements.txt       # Project dependencies
└── tests/                 # Test suite
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Interactive Brokers API
- ib_insync library
- All contributors to the project