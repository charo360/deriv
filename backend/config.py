"""Configuration management for the trading bot."""

import os
from dotenv import load_dotenv
from pydantic import BaseModel
from typing import Literal

load_dotenv()


class TradingConfig(BaseModel):
    """Trading configuration parameters."""
    
    # Deriv API
    api_token: str = os.getenv("DERIV_API_TOKEN", "")
    app_id: int = int(os.getenv("DERIV_APP_ID", "1089"))
    
    # Symbol Configuration
    symbol: str = os.getenv("SYMBOL", "R_10")  # R_10 = Volatility 10 Index
    
    # Trade Parameters
    initial_stake: float = float(os.getenv("INITIAL_STAKE", "10"))
    risk_percent: float = float(os.getenv("RISK_PERCENT", "2"))
    trade_duration: int = int(os.getenv("TRADE_DURATION", "180"))  # 3 minutes
    trade_duration_unit: Literal["s", "m", "h", "d"] = os.getenv("TRADE_DURATION_UNIT", "s")
    
    # Risk Management
    max_martingale_steps: int = int(os.getenv("MAX_MARTINGALE_STEPS", "3"))
    max_consecutive_losses: int = int(os.getenv("MAX_CONSECUTIVE_LOSSES", "3"))
    loss_cooldown_seconds: int = int(os.getenv("LOSS_COOLDOWN_SECONDS", "600"))
    max_daily_trades: int = int(os.getenv("MAX_DAILY_TRADES", "1000"))
    max_daily_loss_percent: float = float(os.getenv("MAX_DAILY_LOSS_PERCENT", "10.0"))
    max_daily_profit_target: float = float(os.getenv("MAX_DAILY_PROFIT_TARGET", "200.0"))  # Stop trading after this profit
    max_session_loss: float = float(os.getenv("MAX_SESSION_LOSS", "100.0"))  # Hard stop loss per session
    
    # Indicator Settings
    bollinger_period: int = 20
    bollinger_std: float = 2.0
    rsi_period: int = 14
    rsi_oversold: float = 30.0
    rsi_overbought: float = 70.0
    stochastic_k: int = 14
    stochastic_d: int = 3
    stochastic_smooth: int = 3
    stochastic_oversold: float = 20.0
    stochastic_overbought: float = 80.0
    ema_period: int = 100
    
    # Timeframes (in seconds)
    timeframe_trigger: int = 60      # M1
    timeframe_alert: int = 300       # M5
    timeframe_higher: int = 900      # M15
    
    # Server reset avoidance (UK time - GMT/BST)
    avoid_trading_start: str = "23:55"
    avoid_trading_end: str = "00:05"
    timezone: str = "Europe/London"  # UK time


class ServerConfig(BaseModel):
    """Server configuration."""
    
    host: str = os.getenv("API_HOST", "0.0.0.0")
    port: int = int(os.getenv("API_PORT", "8000"))
    debug: bool = os.getenv("DEBUG", "false").lower() == "true"


# Global config instances
trading_config = TradingConfig()
server_config = ServerConfig()
