"""Backtest Hybrid Adaptive Strategy using historical Deriv data."""

import asyncio
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import List, Dict, Optional
import argparse

import pandas as pd
import pytz

from deriv_client import DerivClient
from strategy import HybridAdaptiveStrategy, Signal
from risk_manager import RiskManager, TradeRecord as RiskTradeRecord, TradeResult

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@dataclass
class BacktestTrade:
    direction: str  # "CALL" or "PUT"
    entry_epoch: int
    exit_epoch: int
    entry_price: float
    exit_price: float
    stake: float
    payout: float
    profit: float
    result: str
    confidence: float
    market_mode: str


class HybridBacktester:
    """Backtest trading strategy on historical data."""
    
    def __init__(
        self,
        api_token: str,
        initial_balance: float = 1000.0,
        initial_stake: float = 10.0,
        payout_rate: float = 0.95,
        use_live_proposal_payout: bool = False,
        proposal_throttle_ms: int = 0,
        trade_duration_seconds: int = 180,
        min_trade_interval_seconds: int = 60,
        fill_at: str = "close",
    ):
        self.client = DerivClient(api_token)
        self.strategy = HybridAdaptiveStrategy()
        self.risk_manager = RiskManager(
            initial_balance=initial_balance,
            initial_stake=initial_stake,
            risk_percent=2.0,
            max_martingale_steps=0,
            max_daily_trades=10_000,
            max_daily_loss_percent=100.0,
            max_daily_profit_target=1e18,
            max_session_loss=1e18,
            payout_rate=payout_rate,
        )

        self.trade_duration_seconds = int(trade_duration_seconds)
        self.min_trade_interval_seconds = int(min_trade_interval_seconds)
        self.fill_at = fill_at
        self.use_live_proposal_payout = bool(use_live_proposal_payout)
        self.proposal_throttle_ms = int(proposal_throttle_ms)
        self.trades: List[BacktestTrade] = []

        self.results = {
            'total_steps': 0,
            'call_signals': 0,
            'put_signals': 0,
            'no_signals': 0,
            'executed_trades': 0,
            'market_modes': {
                'trending_up': 0,
                'trending_down': 0,
                'ranging': 0,
                'uncertain': 0
            }
        }
    
    async def fetch_historical_candles(self, symbol: str, count: int = 2000) -> List[Dict]:
        """
        Fetch historical candles from Deriv API.
        
        Args:
            symbol: Trading symbol (e.g., R_10)
            count: Number of candles to fetch
            
        Returns:
            List of candle dictionaries
        """
        logger.info(f"Fetching {count} historical candles for {symbol}...")
        
        await self.client.connect()
        
        # Request candles via ticks_history API
        request = {
            "ticks_history": symbol,
            "adjust_start_time": 1,
            "count": count,
            "end": "latest",
            "granularity": 60,  # 1-minute candles
            "style": "candles"
        }
        
        response = await self.client._send(request)
        
        if response.get('error'):
            logger.error(f"Error fetching candles: {response['error']}")
            return []
        
        candles_data = response.get('candles', [])
        
        # Convert to our format
        candles = []
        for candle in candles_data:
            candles.append({
                'epoch': int(candle['epoch']),
                'open': float(candle['open']),
                'high': float(candle['high']),
                'low': float(candle['low']),
                'close': float(candle['close'])
            })
        
        logger.info(f"Fetched {len(candles)} candles from {datetime.fromtimestamp(candles[0]['epoch'])} to {datetime.fromtimestamp(candles[-1]['epoch'])}")
        
        return candles
    
    def _resample_candles(self, candles: List[Dict], timeframe: str) -> List[Dict]:
        """Resample candles to specified timeframe using pandas."""
        if not candles:
            return []
        
        df = pd.DataFrame(candles)
        df['epoch'] = pd.to_datetime(df['epoch'], unit='s', utc=True)
        df.set_index('epoch', inplace=True)
        
        agg = df.resample(timeframe).agg({
            'open': 'first',
            'high': 'max',
            'low': 'min',
            'close': 'last'
        }).dropna()
        
        resampled = []
        for idx, row in agg.iterrows():
            resampled.append({
                'epoch': int(idx.timestamp()),
                'open': float(row['open']),
                'high': float(row['high']),
                'low': float(row['low']),
                'close': float(row['close'])
            })
        
        return resampled

    def _candle_price_for_fill(self, candle: Dict) -> float:
        if self.fill_at == "open":
            return float(candle["open"])
        return float(candle["close"])

    def _lookup_exit_candle(self, candles_m1: List[Dict], entry_epoch: int, exit_epoch: int) -> Optional[Dict]:
        # Candle epochs are at the candle start time. For a duration like 180s,
        # we treat settlement at the close of the candle containing exit_epoch.
        # Find the latest candle whose epoch <= exit_epoch.
        idx = None
        lo, hi = 0, len(candles_m1) - 1
        while lo <= hi:
            mid = (lo + hi) // 2
            if candles_m1[mid]["epoch"] <= exit_epoch:
                idx = mid
                lo = mid + 1
            else:
                hi = mid - 1
        if idx is None:
            return None
        return candles_m1[idx]

    def _settle_rise_fall(self, direction: str, entry_price: float, exit_price: float, stake: float) -> tuple[str, float, float]:
        payout_rate = float(self.risk_manager.payout_rate)
        if exit_price == entry_price:
            return TradeResult.TIE.value, 0.0, stake

        is_win = (exit_price > entry_price) if direction == "CALL" else (exit_price < entry_price)
        if is_win:
            profit = stake * payout_rate
            payout = stake + profit
            return TradeResult.WIN.value, profit, payout

        return TradeResult.LOSS.value, -stake, 0.0

    async def _get_live_proposal_payout(self, symbol: str, contract_type: str, stake: float) -> Optional[float]:
        if not self.client.is_connected or not self.client.is_authorized:
            return None

        if self.proposal_throttle_ms > 0:
            await asyncio.sleep(self.proposal_throttle_ms / 1000)

        try:
            resp = await self.client._send({
                "proposal": 1,
                "amount": stake,
                "basis": "stake",
                "contract_type": contract_type,
                "currency": self.client.currency,
                "duration": self.trade_duration_seconds,
                "duration_unit": "s",
                "symbol": symbol,
            })
            proposal = resp.get("proposal")
            if not proposal:
                return None
            return float(proposal.get("payout", 0.0))
        except Exception as e:
            logger.warning(f"Failed to fetch live proposal payout: {e}")
            return None

    async def run_backtest(self, symbol: str = "R_10", candles_count: int = 2000):
        """
        Run backtest on historical data.
        
        Args:
            symbol: Trading symbol
            candles_count: Number of historical candles to analyze
        """
        logger.info(f"Starting backtest for {symbol}...")
        
        # Fetch historical data
        all_candles = await self.fetch_historical_candles(symbol, candles_count)
        
        if len(all_candles) < 200:
            logger.error("Insufficient historical data")
            return
        
        # Analyze each candle window (need 100+ candles for indicators)
        window_size = 200
        
        # Prepare higher timeframe candles
        candles_m5 = self._resample_candles(all_candles, '5min')
        candles_m15 = self._resample_candles(all_candles, '15min')
        
        last_trade_epoch: Optional[int] = None

        for i in range(window_size, len(all_candles)):
            candles_window = all_candles[i-window_size:i]
            
            # Align m5/m15 candles up to current time
            current_epoch = candles_window[-1]['epoch']
            m5_window = [c for c in candles_m5 if c['epoch'] <= current_epoch][-window_size:]
            m15_window = [c for c in candles_m15 if c['epoch'] <= current_epoch][-window_size:]
            
            if len(m5_window) < 50 or len(m15_window) < 50:
                continue
            
            # Analyze with strategy
            signal = self.strategy.analyze(candles_window, m5_window, m15_window)
            
            self.results['total_steps'] += 1
            
            # Track market mode
            mode = getattr(signal, 'market_mode', 'uncertain')
            if mode not in self.results['market_modes']:
                mode = 'uncertain'
            self.results['market_modes'][mode] += 1
            
            if signal.signal == Signal.RISE:
                self.results['call_signals'] += 1
            elif signal.signal == Signal.FALL:
                self.results['put_signals'] += 1
            else:
                self.results['no_signals'] += 1

            if signal.signal in (Signal.RISE, Signal.FALL):
                if last_trade_epoch is not None and (current_epoch - last_trade_epoch) < self.min_trade_interval_seconds:
                    continue

                can_trade, _reason = self.risk_manager.can_trade()
                if not can_trade:
                    continue

                entry_candle = candles_window[-1]
                entry_price = self._candle_price_for_fill(entry_candle)
                entry_epoch = int(entry_candle["epoch"])

                exit_epoch = entry_epoch + self.trade_duration_seconds
                exit_candle = self._lookup_exit_candle(all_candles, entry_epoch=entry_epoch, exit_epoch=exit_epoch)
                if not exit_candle:
                    continue

                exit_price = float(exit_candle["close"])
                stake = float(self.risk_manager.calculate_stake())

                direction = signal.signal.value

                payout: float
                result: str
                profit: float

                live_payout = None
                if self.use_live_proposal_payout:
                    live_payout = await self._get_live_proposal_payout(symbol=symbol, contract_type=direction, stake=stake)

                if live_payout is not None and live_payout > 0:
                    if exit_price == entry_price:
                        result = TradeResult.TIE.value
                        payout = stake
                        profit = 0.0
                    else:
                        is_win = (exit_price > entry_price) if direction == "CALL" else (exit_price < entry_price)
                        if is_win:
                            payout = float(live_payout)
                            profit = payout - stake
                            result = TradeResult.WIN.value
                        else:
                            payout = 0.0
                            profit = -stake
                            result = TradeResult.LOSS.value
                else:
                    result, profit, payout = self._settle_rise_fall(direction, entry_price, exit_price, stake)

                risk_trade = RiskTradeRecord(
                    id=f"bt_{symbol}_{entry_epoch}",
                    timestamp=datetime.fromtimestamp(entry_epoch, tz=pytz.UTC),
                    symbol=symbol,
                    direction=direction,
                    stake=stake,
                    payout=payout,
                    result=TradeResult(result),
                    profit=profit,
                    entry_price=entry_price,
                    exit_price=exit_price,
                    indicators=getattr(signal, "indicators", {}) or {},
                )
                self.risk_manager.record_trade(risk_trade)

                self.trades.append(
                    BacktestTrade(
                        direction=direction,
                        entry_epoch=entry_epoch,
                        exit_epoch=exit_epoch,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        stake=stake,
                        payout=payout,
                        profit=profit,
                        result=result,
                        confidence=float(getattr(signal, "confidence", 0.0)),
                        market_mode=str(getattr(signal, "market_mode", "unknown")),
                    )
                )

                self.results['executed_trades'] += 1
                last_trade_epoch = entry_epoch
        
        await self.client.disconnect()
        
        # Print results
        self.print_results()
    
    def print_results(self):
        """Print backtest results."""
        logger.info("\n" + "="*80)
        logger.info("HYBRID ADAPTIVE STRATEGY BACKTEST RESULTS")
        logger.info("="*80)
        total_steps = self.results['total_steps']
        logger.info(f"Total candles analyzed: {total_steps}")
        logger.info(f"CALL signals: {self.results['call_signals']} ({(self.results['call_signals']/total_steps*100) if total_steps else 0:.1f}%)")
        logger.info(f"PUT signals: {self.results['put_signals']} ({(self.results['put_signals']/total_steps*100) if total_steps else 0:.1f}%)")
        logger.info(f"NO signals: {self.results['no_signals']} ({(self.results['no_signals']/total_steps*100) if total_steps else 0:.1f}%)")
        logger.info(f"Executed trades: {self.results['executed_trades']}")

        stats = self.risk_manager.get_statistics()
        logger.info("\nPnL Summary:")
        logger.info(f"  Start balance: {self.risk_manager.initial_balance:.2f}")
        logger.info(f"  End balance: {stats.get('current_balance', 0.0):.2f}")
        logger.info(f"  Total profit: {stats.get('total_profit', 0.0):.2f}")
        logger.info(f"  Win rate: {stats.get('win_rate', 0.0):.2f}%")
        logger.info(f"  Profit factor: {stats.get('profit_factor', 0.0):.2f}")
        logger.info(f"  Max drawdown: {stats.get('max_drawdown', 0.0):.2f}%")
        
        logger.info(f"\nMarket Mode Distribution:")
        for mode, count in self.results['market_modes'].items():
            label = mode.replace('_', ' ').title()
            percentage = (count / total_steps * 100) if total_steps else 0
            logger.info(f"  {label}: {count} ({percentage:.1f}%)")
        
        logger.info("="*80)
        
        if self.trades:
            logger.info("\nSample trades:")
            for t in self.trades[:10]:
                ts = datetime.fromtimestamp(t.entry_epoch, tz=pytz.UTC).isoformat()
                logger.info(f"  {ts} - {t.direction} stake={t.stake:.2f} result={t.result} profit={t.profit:.2f} entry={t.entry_price:.2f} exit={t.exit_price:.2f} mode={t.market_mode}")
        
        # Save to file
        with open('backtest_hybrid_results.json', 'w') as f:
            payload = {
                **self.results,
                "trade_duration_seconds": self.trade_duration_seconds,
                "min_trade_interval_seconds": self.min_trade_interval_seconds,
                "fill_at": self.fill_at,
                "use_live_proposal_payout": self.use_live_proposal_payout,
                "proposal_throttle_ms": self.proposal_throttle_ms,
                "payout_rate": self.risk_manager.payout_rate,
                "statistics": self.risk_manager.get_statistics(),
                "trades": [t.__dict__ for t in self.trades],
            }
            json.dump(payload, f, indent=2, default=str)
        logger.info("\nFull results saved to backtest_hybrid_results.json")


async def main():
    """Main backtest entry point."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    
    api_token = os.getenv('DERIV_API_TOKEN')
    if not api_token:
        logger.error("DERIV_API_TOKEN not found in environment")
        return
    
    parser = argparse.ArgumentParser(description="Backtest Hybrid Adaptive Strategy")
    parser.add_argument("--symbol", default=os.getenv("BACKTEST_SYMBOL", "R_10"),
                        help="Symbol to backtest (e.g., R_10, R_75)")
    parser.add_argument("--candles", type=int, default=int(os.getenv("BACKTEST_CANDLES", "2000")),
                        help="Number of candles to fetch (default 2000)")
    parser.add_argument("--initial-balance", type=float, default=float(os.getenv("BACKTEST_INITIAL_BALANCE", "1000")))
    parser.add_argument("--initial-stake", type=float, default=float(os.getenv("BACKTEST_INITIAL_STAKE", "10")))
    parser.add_argument("--payout-rate", type=float, default=float(os.getenv("BACKTEST_PAYOUT_RATE", "0.95")))
    parser.add_argument("--duration", type=int, default=int(os.getenv("BACKTEST_DURATION_SECONDS", "180")),
                        help="Contract duration in seconds (default 180)")
    parser.add_argument("--min-interval", type=int, default=int(os.getenv("BACKTEST_MIN_INTERVAL_SECONDS", "60")),
                        help="Minimum seconds between trades (default 60)")
    parser.add_argument("--fill-at", choices=["close", "open"], default=os.getenv("BACKTEST_FILL_AT", "close"),
                        help="Whether to enter at candle close or open")
    parser.add_argument("--use-live-proposal-payout", action="store_true",
                        help="Fetch Deriv proposal payout at runtime for each executed trade (not historical; slower)")
    parser.add_argument("--proposal-throttle-ms", type=int, default=int(os.getenv("BACKTEST_PROPOSAL_THROTTLE_MS", "0")),
                        help="Optional sleep between proposal requests (ms) to reduce API load")
    args = parser.parse_args()

    backtester = HybridBacktester(
        api_token=api_token,
        initial_balance=args.initial_balance,
        initial_stake=args.initial_stake,
        payout_rate=args.payout_rate,
        use_live_proposal_payout=args.use_live_proposal_payout,
        proposal_throttle_ms=args.proposal_throttle_ms,
        trade_duration_seconds=args.duration,
        min_trade_interval_seconds=args.min_interval,
        fill_at=args.fill_at,
    )
    
    await backtester.run_backtest(symbol=args.symbol, candles_count=args.candles)


if __name__ == "__main__":
    asyncio.run(main())
