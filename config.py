"""Configuration settings for the IB Trading application."""

from dataclasses import dataclass
from typing import Dict, Any
import logging
from pathlib import Path

@dataclass
class IBConfig:
    """Interactive Brokers connection configuration."""
    host: str = '127.0.0.1'
    port: int = 7497
    client_id: int = 1
    retry_count: int = 3
    retry_delay: int = 2

@dataclass
class TradingConfig:
    """Trading-related configuration."""
    default_currency: str = 'USD'
    default_exchange: str = 'SMART'
    trading_days_per_year: int = 252
    risk_free_rate: float = 0.03
    max_volatility: float = 10.0
    min_data_points_ratio: float = 0.8

@dataclass
class UIConfig:
    """User interface configuration."""
    window_size: str = "1200x800"
    refresh_interval: int = 5000  # milliseconds
    portfolio_update_interval: int = 5000  # milliseconds
    hedger_status_update_interval: int = 1000  # milliseconds

class AppConfig:
    """Application configuration manager."""
    
    def __init__(self):
        self.ib = IBConfig()
        self.trading = TradingConfig()
        self.ui = UIConfig()
        self.setup_logging()
    
    @staticmethod
    def setup_logging():
        """Configure logging for the application."""
        log_dir = Path('logs')
        log_dir.mkdir(exist_ok=True)
        
        # Configure file handler
        file_handler = logging.FileHandler(log_dir / 'app.log')
        file_handler.setLevel(logging.INFO)
        file_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(file_formatter)
        
        # Configure console handler
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)
        console_formatter = logging.Formatter(
            '%(levelname)s: %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        
        # Configure root logger
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        root_logger.addHandler(file_handler)
        root_logger.addHandler(console_handler)

# Create global config instance
config = AppConfig()