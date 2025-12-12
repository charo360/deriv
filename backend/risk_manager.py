"""Risk management module with capped Martingale and position sizing."""

from dataclasses import dataclass, field
from datetime import datetime, date
from typing import List, Optional
from enum import Enum


class TradeResult(Enum):
    WIN = "win"
    LOSS = "loss"
    TIE = "tie"


@dataclass
class TradeRecord:
    """Record of a single trade."""
    
    id: str
    timestamp: datetime
    symbol: str
    direction: str  # "CALL" or "PUT"
    stake: float
    payout: float
    result: TradeResult
    profit: float
    entry_price: float
    exit_price: float
    indicators: dict = field(default_factory=dict)


class RiskManager:
    """
    Manages risk through position sizing and capped Martingale.
    
    Features:
    - Fixed fractional position sizing (1-2% risk per trade)
    - Capped Martingale (max 3 steps)
    - Daily loss limits
    - Trade frequency limits
    - Consecutive loss tracking
    """
    
    def __init__(
        self,
        initial_balance: float,
        initial_stake: float = 10.0,
        risk_percent: float = 2.0,
        max_martingale_steps: int = 3,
        max_daily_trades: int = 10,
        max_daily_loss_percent: float = 10.0,
        payout_rate: float = 0.95  # 95% payout
    ):
        self.initial_balance = initial_balance
        self.current_balance = initial_balance
        self.initial_stake = initial_stake
        self.risk_percent = risk_percent
        self.max_martingale_steps = max_martingale_steps
        self.max_daily_trades = max_daily_trades
        self.max_daily_loss_percent = max_daily_loss_percent
        self.payout_rate = payout_rate
        
        # State tracking
        self.consecutive_losses = 0
        self.current_martingale_step = 0
        self.daily_trades: List[TradeRecord] = []
        self.all_trades: List[TradeRecord] = []
        self.current_date = date.today()
        
        # Session stats
        self.session_start_balance = initial_balance
        self.total_wins = 0
        self.total_losses = 0
    
    def reset_daily_stats(self):
        """Reset daily tracking at start of new day."""
        self.daily_trades = []
        self.current_date = date.today()
    
    def calculate_stake(self) -> float:
        """
        Calculate next stake using capped Martingale.
        
        Martingale sequence: base -> base*2.2 -> base*5 -> reset
        This recovers losses while capping risk.
        """
        # Check if new day
        if date.today() != self.current_date:
            self.reset_daily_stats()
        
        base_stake = self.initial_stake
        
        # Fixed fractional adjustment based on balance
        balance_ratio = self.current_balance / self.initial_balance
        if balance_ratio > 1.5:
            base_stake = self.initial_stake * 1.5
        elif balance_ratio < 0.5:
            base_stake = self.initial_stake * 0.5
        
        # Martingale multipliers (designed to recover previous losses + profit)
        martingale_multipliers = [1.0, 2.2, 5.0]
        
        if self.current_martingale_step >= self.max_martingale_steps:
            # Reset after max steps
            self.current_martingale_step = 0
            return base_stake
        
        multiplier = martingale_multipliers[min(self.current_martingale_step, len(martingale_multipliers) - 1)]
        stake = base_stake * multiplier
        
        # Cap stake at risk percent of balance
        max_stake = self.current_balance * (self.risk_percent / 100) * 3
        stake = min(stake, max_stake)
        
        # Minimum stake
        stake = max(stake, 1.0)
        
        return round(stake, 2)
    
    def can_trade(self) -> tuple[bool, str]:
        """
        Check if trading is allowed based on risk limits.
        
        Returns:
            (can_trade: bool, reason: str)
        """
        # Check if new day
        if date.today() != self.current_date:
            self.reset_daily_stats()
        
        # Daily trade limit
        if len(self.daily_trades) >= self.max_daily_trades:
            return False, f"Daily trade limit reached ({self.max_daily_trades})"
        
        # Daily loss limit
        daily_pnl = sum(t.profit for t in self.daily_trades)
        max_daily_loss = self.session_start_balance * (self.max_daily_loss_percent / 100)
        if daily_pnl < -max_daily_loss:
            return False, f"Daily loss limit reached ({self.max_daily_loss_percent}%)"
        
        # Balance too low
        min_stake = self.initial_stake
        if self.current_balance < min_stake:
            return False, "Insufficient balance for minimum stake"
        
        # Consecutive loss limit (pause after 5 losses)
        if self.consecutive_losses >= 5:
            return False, "Consecutive loss limit reached (5). Consider pausing."
        
        return True, "OK"
    
    def record_trade(self, trade: TradeRecord):
        """Record a completed trade and update state."""
        self.all_trades.append(trade)
        self.daily_trades.append(trade)
        
        # Update balance
        self.current_balance += trade.profit
        
        # Update win/loss tracking
        if trade.result == TradeResult.WIN:
            self.total_wins += 1
            self.consecutive_losses = 0
            self.current_martingale_step = 0  # Reset on win
        elif trade.result == TradeResult.LOSS:
            self.total_losses += 1
            self.consecutive_losses += 1
            self.current_martingale_step += 1  # Advance Martingale
        # TIE doesn't affect Martingale
    
    def get_statistics(self) -> dict:
        """Get current trading statistics."""
        total_trades = len(self.all_trades)
        if total_trades == 0:
            return {
                'total_trades': 0,
                'win_rate': 0.0,
                'total_profit': 0.0,
                'profit_factor': 0.0,
                'expectancy': 0.0,
                'max_drawdown': 0.0,
                'current_balance': self.current_balance,
                'consecutive_losses': self.consecutive_losses,
                'martingale_step': self.current_martingale_step,
                'daily_trades': len(self.daily_trades),
                'daily_pnl': 0.0
            }
        
        wins = sum(1 for t in self.all_trades if t.result == TradeResult.WIN)
        losses = sum(1 for t in self.all_trades if t.result == TradeResult.LOSS)
        
        win_rate = (wins / total_trades) * 100 if total_trades > 0 else 0
        
        total_profit = sum(t.profit for t in self.all_trades)
        gross_wins = sum(t.profit for t in self.all_trades if t.profit > 0)
        gross_losses = abs(sum(t.profit for t in self.all_trades if t.profit < 0))
        
        profit_factor = gross_wins / gross_losses if gross_losses > 0 else float('inf')
        expectancy = total_profit / total_trades if total_trades > 0 else 0
        
        # Calculate max drawdown
        peak = self.initial_balance
        max_dd = 0
        running_balance = self.initial_balance
        for trade in self.all_trades:
            running_balance += trade.profit
            peak = max(peak, running_balance)
            dd = (peak - running_balance) / peak * 100
            max_dd = max(max_dd, dd)
        
        daily_pnl = sum(t.profit for t in self.daily_trades)
        
        return {
            'total_trades': total_trades,
            'wins': wins,
            'losses': losses,
            'win_rate': round(win_rate, 2),
            'total_profit': round(total_profit, 2),
            'profit_factor': round(profit_factor, 2),
            'expectancy': round(expectancy, 2),
            'max_drawdown': round(max_dd, 2),
            'current_balance': round(self.current_balance, 2),
            'consecutive_losses': self.consecutive_losses,
            'martingale_step': self.current_martingale_step,
            'daily_trades': len(self.daily_trades),
            'daily_pnl': round(daily_pnl, 2)
        }
    
    def get_trade_history(self, limit: int = 50) -> List[dict]:
        """Get recent trade history."""
        trades = self.all_trades[-limit:]
        return [
            {
                'id': t.id,
                'timestamp': t.timestamp.isoformat(),
                'symbol': t.symbol,
                'direction': t.direction,
                'stake': t.stake,
                'payout': t.payout,
                'result': t.result.value,
                'profit': round(t.profit, 2),
                'entry_price': t.entry_price,
                'exit_price': t.exit_price
            }
            for t in reversed(trades)
        ]
    
    def reset(self, new_balance: Optional[float] = None):
        """Reset the risk manager state."""
        if new_balance:
            self.initial_balance = new_balance
            self.current_balance = new_balance
            self.session_start_balance = new_balance
        
        self.consecutive_losses = 0
        self.current_martingale_step = 0
        self.daily_trades = []
        self.all_trades = []
        self.total_wins = 0
        self.total_losses = 0
        self.current_date = date.today()
