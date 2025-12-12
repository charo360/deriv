"""Main trading bot orchestrator."""

import asyncio
import logging
from datetime import datetime
from typing import Optional, Callable
import uuid
import pytz

from deriv_client import DerivClient, ContractResult
from strategy import MeanReversionStrategy, Signal, TradeSignal
from risk_manager import RiskManager, TradeRecord, TradeResult
from config import trading_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TradingBot:
    """
    Main trading bot that orchestrates:
    - Deriv API connection
    - Strategy signal generation
    - Risk management
    - Trade execution
    """
    
    def __init__(
        self,
        api_token: str,
        initial_balance: float = 1000.0,
        on_state_update: Optional[Callable] = None
    ):
        self.api_token = api_token
        self.initial_balance = initial_balance
        self.on_state_update = on_state_update
        
        # Components
        self.client: Optional[DerivClient] = None
        self.strategy = MeanReversionStrategy()
        self.risk_manager = RiskManager(
            initial_balance=initial_balance,
            initial_stake=trading_config.initial_stake,
            risk_percent=trading_config.risk_percent,
            max_martingale_steps=trading_config.max_martingale_steps,
            max_daily_trades=trading_config.max_daily_trades,
            max_daily_loss_percent=trading_config.max_daily_loss_percent
        )
        
        # State
        self.is_running = False
        self.is_trading_enabled = False
        self.current_signal: Optional[TradeSignal] = None
        self.last_trade_time: Optional[datetime] = None
        self.pending_contract_id: Optional[str] = None
        self.trade_in_progress = False  # Lock to prevent multiple trades
        self.trade_lock_time: Optional[datetime] = None  # Timestamp when lock set
        
        # Settings
        self.symbol = trading_config.symbol
        self.trade_duration = trading_config.trade_duration
        self.trade_duration_unit = trading_config.trade_duration_unit
        self.min_trade_interval = 60  # Minimum seconds between trades
    
    async def start(self):
        """Start the trading bot."""
        logger.info("Starting trading bot...")
        
        # Initialize Deriv client
        self.client = DerivClient(
            api_token=self.api_token,
            app_id=trading_config.app_id,
            on_tick=self._on_tick,
            on_candle=self._on_candle,
            on_balance=self._on_balance,
            on_contract_update=self._on_contract_update
        )
        
        try:
            # Connect and authorize
            await self.client.connect()
            
            # Update balance from account
            self.risk_manager.current_balance = self.client.balance
            self.risk_manager.initial_balance = self.client.balance
            self.risk_manager.session_start_balance = self.client.balance
            
            # Subscribe to market data
            await self.client.subscribe_ticks(self.symbol)
            await self.client.subscribe_candles(self.symbol, 60)   # M1
            await self.client.subscribe_candles(self.symbol, 300)  # M5
            await self.client.subscribe_candles(self.symbol, 900)  # M15
            
            self.is_running = True
            logger.info("Trading bot started successfully")
            
            # Start analysis loop
            asyncio.create_task(self._analysis_loop())
            
            await self._broadcast_state()
            
        except Exception as e:
            logger.error(f"Failed to start bot: {e}")
            raise
    
    async def stop(self):
        """Stop the trading bot."""
        logger.info("Stopping trading bot...")
        self.is_running = False
        self.is_trading_enabled = False
        
        if self.client:
            await self.client.disconnect()
        
        await self._broadcast_state()
    
    def enable_trading(self):
        """Enable automated trading."""
        self.is_trading_enabled = True
        logger.info("Trading enabled")
    
    def disable_trading(self):
        """Disable automated trading."""
        self.is_trading_enabled = False
        logger.info("Trading disabled")
    
    async def _analysis_loop(self):
        """Main analysis loop - runs every second."""
        while self.is_running:
            try:
                await self._analyze_and_trade()
            except Exception as e:
                logger.error(f"Analysis error: {e}")
            
            await asyncio.sleep(1)
    
    async def _analyze_and_trade(self):
        """Analyze market and execute trades if conditions met."""
        if not self.client or not self.client.is_authorized:
            return
        
        # Get candles
        candles_m1 = self.client.get_candles("m1")
        candles_m5 = self.client.get_candles("m5")
        candles_m15 = self.client.get_candles("m15")
        
        if not all([candles_m1, candles_m5, candles_m15]):
            return
        
        # Generate signal
        signal = self.strategy.analyze(candles_m1, candles_m5, candles_m15)
        self.current_signal = signal
        
        # Check if we should trade
        if not self.is_trading_enabled:
            await self._broadcast_state()
            return
        
        if signal.signal == Signal.NONE:
            await self._broadcast_state()
            return
        
        # Check risk limits
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            logger.warning(f"Cannot trade: {reason}")
            await self._broadcast_state()
            return
        
        # Check trade interval
        if self.last_trade_time:
            elapsed = (datetime.now(pytz.UTC) - self.last_trade_time).total_seconds()
            if elapsed < self.min_trade_interval:
                return
        
        # Reset stale trade lock (e.g., manual trade canceled mid-way)
        if self.trade_in_progress and not self.pending_contract_id:
            if self.trade_lock_time:
                lock_age = (datetime.now(pytz.UTC) - self.trade_lock_time).total_seconds()
                if lock_age > 5:
                    logger.warning("Trade lock stale for %.1fs, resetting", lock_age)
                    self.trade_in_progress = False
                    self.trade_lock_time = None

        # Check if we have a pending contract or trade in progress
        if self.pending_contract_id or self.trade_in_progress:
            logger.debug("Trade already in progress, skipping")
            return
        
        # Execute trade
        await self._execute_trade(signal)
    
    async def _execute_trade(self, signal: TradeSignal):
        """Execute a trade based on the signal."""
        # Set lock immediately to prevent duplicate trades
        self.trade_in_progress = True
        self.trade_lock_time = datetime.now(pytz.UTC)
        
        stake = self.risk_manager.calculate_stake()
        contract_type = signal.signal.value  # "CALL" or "PUT"
        
        logger.info(f"Executing {contract_type} trade: ${stake} stake, {signal.confidence}% confidence")
        logger.info(f"Confluence: {', '.join(signal.confluence_factors)}")
        
        try:
            result = await self.client.buy_contract(
                symbol=self.symbol,
                contract_type=contract_type,
                amount=stake,
                duration=self.trade_duration,
                duration_unit=self.trade_duration_unit
            )
            
            self.pending_contract_id = result["contract_id"]
            self.last_trade_time = datetime.now(pytz.UTC)
            
            logger.info(f"Contract purchased: {result['contract_id']}, Payout: {result['payout']}")
            
            await self._broadcast_state()
            
        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            # Release lock on failure so bot can try again
            self.trade_in_progress = False
            self.trade_lock_time = None
    
    async def _on_tick(self, tick: dict):
        """Handle incoming tick."""
        # Broadcast state update
        await self._broadcast_state()
    
    async def _on_candle(self, data: dict):
        """Handle incoming candle."""
        pass  # Candles are stored in client
    
    async def _on_balance(self, data: dict):
        """Handle balance update."""
        self.risk_manager.current_balance = data["balance"]
        await self._broadcast_state()
    
    async def _on_contract_update(self, result: ContractResult):
        """Handle contract completion."""
        # Skip if this contract was already processed
        if result.contract_id != self.pending_contract_id:
            logger.debug(f"Ignoring update for contract {result.contract_id} (pending: {self.pending_contract_id})")
            return
        
        logger.info(f"Contract {result.contract_id} completed: {'WIN' if result.is_win else 'LOSS'}, Profit: {result.profit}")
        
        # Record trade
        trade = TradeRecord(
            id=result.contract_id,
            timestamp=datetime.now(pytz.UTC),
            symbol=self.symbol,
            direction=self.current_signal.signal.value if self.current_signal else "UNKNOWN",
            stake=result.buy_price,
            payout=result.sell_price,
            result=TradeResult.WIN if result.is_win else TradeResult.LOSS,
            profit=result.profit,
            entry_price=result.entry_spot,
            exit_price=result.exit_spot,
            indicators=self.current_signal.indicators if self.current_signal else {}
        )
        
        self.risk_manager.record_trade(trade)
        self.pending_contract_id = None
        self.trade_in_progress = False  # Release lock when contract completes
        self.trade_lock_time = None
        
        logger.info("Trade completed, ready for next signal")
        await self._broadcast_state()
    
    async def _broadcast_state(self):
        """Broadcast current state to listeners."""
        if self.on_state_update:
            state = self.get_state()
            await self.on_state_update(state)
    
    def get_state(self) -> dict:
        """Get current bot state."""
        account = self.client.get_account_status() if self.client else {}
        stats = self.risk_manager.get_statistics()
        
        signal_data = None
        if self.current_signal:
            signal_data = {
                "signal": self.current_signal.signal.value,
                "confidence": self.current_signal.confidence,
                "timestamp": self.current_signal.timestamp.isoformat(),
                "price": self.current_signal.price,
                "confluence_factors": self.current_signal.confluence_factors,
                "m1_confirmed": self.current_signal.m1_confirmed,
                "m5_confirmed": self.current_signal.m5_confirmed,
                "m15_confirmed": self.current_signal.m15_confirmed,
                "indicators": self.current_signal.indicators
            }
        
        return {
            "is_running": self.is_running,
            "is_trading_enabled": self.is_trading_enabled,
            "symbol": self.symbol,
            "account": account,
            "statistics": stats,
            "current_signal": signal_data,
            "pending_contract": self.pending_contract_id,
            "trade_history": self.risk_manager.get_trade_history(20),
            "settings": {
                "initial_stake": trading_config.initial_stake,
                "risk_percent": trading_config.risk_percent,
                "max_martingale_steps": trading_config.max_martingale_steps,
                "trade_duration": trading_config.trade_duration,
                "trade_duration_unit": trading_config.trade_duration_unit
            }
        }
    
    async def manual_trade(self, direction: str) -> dict:
        """
        Execute a manual trade.
        
        Args:
            direction: "CALL" or "PUT"
            
        Returns:
            Trade result
        """
        if not self.client or not self.client.is_authorized:
            raise Exception("Not connected to Deriv")
        
        can_trade, reason = self.risk_manager.can_trade()
        if not can_trade:
            raise Exception(reason)
        
        stake = self.risk_manager.calculate_stake()
        
        result = await self.client.buy_contract(
            symbol=self.symbol,
            contract_type=direction,
            amount=stake,
            duration=self.trade_duration,
            duration_unit=self.trade_duration_unit
        )
        
        self.pending_contract_id = result["contract_id"]
        self.last_trade_time = datetime.now(pytz.UTC)
        
        return result
