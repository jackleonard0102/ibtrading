# Auto Hedger and IV/RV Calculator

This project is a desktop application built using **Python** and **Tkinter** to monitor and hedge stock portfolio positions based on target delta, while also calculating **Implied Volatility (IV)** and **Realized Volatility (RV)** for selected stocks. The project connects to **IBKR (Interactive Brokers)** via their API to fetch live market data and execute trades.

## Features:
- **Auto-Hedger**: Automatically adjusts the delta for selected stock positions to reach a target delta.
- **IV Calculator**: Calculates **Implied Volatility** using the Black-Scholes model for options.
- **RV Calculator**: Calculates **Realized Volatility** based on historical stock data.
- **Activity Logs**: Displays log messages of hedging actions, including trades and delta adjustments.

---

## Table of Contents
- [Prerequisites](#prerequisites)
- [Installation](#installation)
  - [Windows](#windows-installation)
  - [Ubuntu](#ubuntu-installation)
- [Running the Project](#running-the-project)
- [Project Structure](#project-structure)
- [Usage](#usage)

---

## Prerequisites

Before setting up the project, ensure the following prerequisites are met:

1. **Interactive Brokers API**: Ensure you have an **IBKR account** and have downloaded either **TWS (Trader Workstation)** or **IB Gateway**. Enable the API in **IBKR TWS** or **IB Gateway** to allow connections from the app.
   
   - TWS can be downloaded [here](https://www.interactivebrokers.com/en/trading/tws.php).
   - Enable the API in **TWS**: Go to **File > Global Configuration > API > Settings** and check **Enable ActiveX and Socket Clients**.

2. **Python 3.8+**: The project requires **Python 3.8+** to work properly.

3. **IBKR Market Data Subscription**: Ensure your IBKR account has the necessary **market data subscriptions** for the stocks and options you want to trade.

---

## Installation

### Windows Installation

1. **Install Python**:
   - Download and install **Python 3.8+** from [python.org](https://www.python.org/downloads/windows/).
   - During installation, check **"Add Python to PATH"**.

2. **Install Pip**:
   - Pip is usually installed by default with Python. Verify by opening **Command Prompt** and running:
     ```bash
     python -m ensurepip --upgrade
     ```

3. **Install Git** (Optional, if you need to clone the project from a repository):
   - Download and install **Git** from [git-scm.com](https://git-scm.com/download/win).

4. **Clone the Project**:
   - Navigate to the folder where you want to clone the project, then run:
     ```bash
     git clone <repository-url>
     ```

5. **Install Project Dependencies**:
   - Navigate to the project folder:
     ```bash
     cd <project-folder>
     ```
   - Create a virtual environment:
     ```bash
     python -m venv .venv
     ```
   - Activate the virtual environment:
     ```bash
     .venv\Scripts\activate
     ```
   - Install the required dependencies from the `requirements.txt` file:
     ```bash
     pip install -r requirements.txt
     ```

### Ubuntu Installation

1. **Install Python**:
   - Open a terminal and run the following commands:
     ```bash
     sudo apt update
     sudo apt install python3 python3-venv python3-pip
     ```

2. **Install Git** (Optional, if you need to clone the project from a repository):
   ```bash
   sudo apt install git
   ```

3. **Clone the Project**:
   - Navigate to the directory where you want to clone the project, then run:
     ```bash
     git clone <repository-url>
     ```

4. **Install Project Dependencies**:
   - Navigate to the project folder:
     ```bash
     cd <project-folder>
     ```
   - Create a virtual environment:
     ```bash
     python3 -m venv .venv
     ```
   - Activate the virtual environment:
     ```bash
     source .venv/bin/activate
     ```
   - Install the required dependencies from the `requirements.txt` file:
     ```bash
     pip install -r requirements.txt
     ```

---

## Running the Project

1. **Start IBKR TWS or IB Gateway**:
   - Open **Trader Workstation (TWS)** or **IB Gateway** and ensure the API is enabled and running.

2. **Run the Application**:
   - After activating the virtual environment, run the `app.py` file:
     ```bash
     python app.py
     ```

   This will launch the **Auto-Hedger and IV/RV Calculator** GUI.

3. **Interactive Brokers Connection**:
   - The app will attempt to connect to **IBKR** via the API. Ensure the **API port** in **IBKR TWS** or **IB Gateway** is set to `7497` for paper trading or `7496` for live trading.
   - If successfully connected, the app will allow you to select stocks and monitor delta, implied volatility, and realized volatility.

---

## Project Structure

```bash
AUTOHEDGER_APP/
├── app.py              # Main application entry point
├── components/
│   ├── auto_hedger.py      # Delta hedging logic
│   ├── ib_connection.py    # IBKR API connection logic
│   ├── iv_calculator.py    # Implied Volatility calculation
│   ├── rv_calculator.py    # Realized Volatility calculation
├── ui/
│   ├── dashboard.py        # Tkinter GUI logic for the dashboard
├── logs/
│   └── hedger.log          # Log files for hedging activities
├── requirements.txt        # List of dependencies
├── README.md               # Project setup and usage guide
```

---

## Usage

### Portfolio / Auto Hedger Section:
- **Select Stock Symbol**: Choose a stock symbol from your portfolio.
- **Target Delta**: Set the target delta for the auto-hedger.
- **Max Order Qty**: Set the maximum order quantity for hedging.
- **Run Auto-Hedger**: Click this button to start the auto-hedger, which will monitor your portfolio's delta and adjust positions based on the target delta.

### IV / RV Calculator Section:
- **Select Stock Symbol (for IV/RV)**: Choose a stock symbol for which you want to calculate implied and realized volatility.
- **Implied Volatility (IV)**: Displays the calculated IV based on the Black-Scholes model.
- **Realized Volatility (RV)**: Displays the calculated RV based on historical stock prices.
- **Update Data**: Click to fetch the latest IV and RV values for the selected stock.
- **Show RV Graph**: Displays a graph of realized volatility over time.

### Activity Logs:
- This section shows log messages for each action taken by the auto-hedger, including executed trades and delta adjustments.

---

## Troubleshooting

- **Connection Issues**: If you encounter errors connecting to **IBKR**, make sure:
  - Only one session (TWS or IB Gateway) is running.
  - The API is enabled and the correct port (`7497` for paper, `7496` for live) is being used.
  
- **Market Data Issues**: Ensure that your **IBKR account** has access to market data for the selected stocks. If using a paper trading account, market data might be delayed or restricted.

- **Permission Errors**: If you receive "No security definition" errors, check that your IBKR account has permissions for the selected stocks and options.

##
If you have any questions or issues, please contact us at fazeenlancer@gmail.com