import argparse
import asyncio
import csv
from dataclasses import asdict, dataclass
from datetime import datetime
import os
from typing import Any, Dict, List, Optional, Tuple

import pytz
from dotenv import load_dotenv

from deriv_client import DerivClient
from strategy import HybridAdaptiveStrategy, Signal


@dataclass
class ReplayTrade:
    direction: str
    entry_epoch: int
    exit_epoch: int
    entry_price: float
    exit_price: float
    result: str
    profit: float
    confidence: float
    market_mode: str
    mae: float
    mfe: float
    t_mae: int
    t_mfe: int


def _bisect_last_leq_epoch(candles: List[Dict[str, Any]], epoch: int) -> Optional[int]:
    lo, hi = 0, len(candles) - 1
    idx: Optional[int] = None
    while lo <= hi:
        mid = (lo + hi) // 2
        if int(candles[mid]["epoch"]) <= epoch:
            idx = mid
            lo = mid + 1
        else:
            hi = mid - 1
    return idx


def _slice_between_epochs(candles: List[Dict[str, Any]], start_epoch: int, end_epoch: int) -> List[Dict[str, Any]]:
    if not candles:
        return []
    start_idx = _bisect_last_leq_epoch(candles, start_epoch)
    if start_idx is None:
        start_idx = 0
    end_idx = _bisect_last_leq_epoch(candles, end_epoch)
    if end_idx is None:
        return []
    if end_idx < start_idx:
        return []
    return candles[start_idx : end_idx + 1]


def _settle_rise_fall(direction: str, entry_price: float, exit_price: float, payout_rate: float) -> Tuple[str, float]:
    if exit_price == entry_price:
        return "TIE", 0.0

    is_win = (exit_price > entry_price) if direction == "CALL" else (exit_price < entry_price)
    if is_win:
        return "WIN", payout_rate

    return "LOSS", -1.0


def _compute_mae_mfe(direction: str, entry_price: float, candles_m1_between: List[Dict[str, Any]]) -> Tuple[float, float, int, int]:
    mae = 0.0
    mfe = 0.0
    t_mae = 0
    t_mfe = 0

    if not candles_m1_between:
        return mae, mfe, t_mae, t_mfe

    if direction == "CALL":
        best = float("-inf")
        worst = float("inf")
        for c in candles_m1_between:
            high = float(c["high"])
            low = float(c["low"])
            if high > best:
                best = high
                mfe = best - entry_price
                t_mfe = int(c["epoch"])
            if low < worst:
                worst = low
                mae = worst - entry_price
                t_mae = int(c["epoch"])
        return mae, mfe, t_mae, t_mfe

    best = float("inf")
    worst = float("-inf")
    for c in candles_m1_between:
        high = float(c["high"])
        low = float(c["low"])
        if low < best:
            best = low
            mfe = entry_price - best
            t_mfe = int(c["epoch"])
        if high > worst:
            worst = high
            mae = entry_price - worst
            t_mae = int(c["epoch"])

    return mae, mfe, t_mae, t_mfe


class LiveReplayBacktester:
    def __init__(
        self,
        api_token: str,
        symbol: str,
        trade_duration_s: int,
        payout_rate: float,
        warmup_m1: int,
        min_trade_interval_s: int,
        max_trades: int,
    ):
        self.client = DerivClient(api_token)
        self.strategy = HybridAdaptiveStrategy()
        self.symbol = symbol
        self.trade_duration_s = int(trade_duration_s)
        self.payout_rate = float(payout_rate)
        self.warmup_m1 = int(warmup_m1)
        self.min_trade_interval_s = int(min_trade_interval_s)
        self.max_trades = int(max_trades)

        self.trades: List[ReplayTrade] = []

    async def fetch_candles(self, granularity_s: int, count: int) -> List[Dict[str, Any]]:
        request = {
            "ticks_history": self.symbol,
            "adjust_start_time": 1,
            "count": int(count),
            "end": "latest",
            "granularity": int(granularity_s),
            "style": "candles",
        }
        resp = await self.client._send(request)
        if resp.get("error"):
            raise RuntimeError(str(resp["error"]))
        candles = resp.get("candles", [])
        parsed: List[Dict[str, Any]] = []
        for c in candles:
            parsed.append(
                {
                    "epoch": int(c["epoch"]),
                    "open": float(c["open"]),
                    "high": float(c["high"]),
                    "low": float(c["low"]),
                    "close": float(c["close"]),
                }
            )
        parsed.sort(key=lambda x: x["epoch"])
        return parsed

    async def run(self, m1_count: int) -> None:
        await self.client.connect()
        try:
            m1 = await self.fetch_candles(60, m1_count)
            if len(m1) < self.warmup_m1 + 10:
                raise RuntimeError(f"Not enough M1 candles fetched: {len(m1)}")

            m5_needed = max(300, m1_count // 5)
            m15_needed = max(300, m1_count // 15)

            m5 = await self.fetch_candles(300, m5_needed)
            m15 = await self.fetch_candles(900, m15_needed)

            last_trade_epoch: Optional[int] = None

            for i in range(self.warmup_m1, len(m1)):
                if self.max_trades > 0 and len(self.trades) >= self.max_trades:
                    break

                m1_window = m1[: i + 1]
                current_epoch = int(m1_window[-1]["epoch"])

                if last_trade_epoch is not None:
                    if current_epoch - last_trade_epoch < self.min_trade_interval_s:
                        continue

                m5_idx = _bisect_last_leq_epoch(m5, current_epoch)
                m15_idx = _bisect_last_leq_epoch(m15, current_epoch)
                if m5_idx is None or m15_idx is None:
                    continue

                m5_window = m5[: m5_idx + 1]
                m15_window = m15[: m15_idx + 1]

                if len(m5_window) < 60 or len(m15_window) < 60:
                    continue

                signal = self.strategy.analyze(m1_window, m5_window, m15_window)
                if signal.signal == Signal.NONE:
                    continue

                direction = "CALL" if signal.signal == Signal.RISE else "PUT"
                entry_price = float(m1_window[-1]["close"])
                entry_epoch = current_epoch
                exit_epoch = entry_epoch + self.trade_duration_s

                exit_idx = _bisect_last_leq_epoch(m1, exit_epoch)
                if exit_idx is None:
                    continue

                exit_price = float(m1[exit_idx]["close"])

                m1_between = _slice_between_epochs(m1, entry_epoch, exit_epoch)
                mae, mfe, t_mae, t_mfe = _compute_mae_mfe(direction, entry_price, m1_between)

                result, profit_mult = _settle_rise_fall(direction, entry_price, exit_price, self.payout_rate)
                profit = profit_mult

                self.trades.append(
                    ReplayTrade(
                        direction=direction,
                        entry_epoch=entry_epoch,
                        exit_epoch=int(m1[exit_idx]["epoch"]),
                        entry_price=entry_price,
                        exit_price=exit_price,
                        result=result,
                        profit=profit,
                        confidence=float(signal.confidence),
                        market_mode=str(getattr(signal, "market_mode", "")),
                        mae=float(mae),
                        mfe=float(mfe),
                        t_mae=int(t_mae),
                        t_mfe=int(t_mfe),
                    )
                )

                last_trade_epoch = entry_epoch

        finally:
            await self.client.disconnect()

    def summary(self) -> Dict[str, Any]:
        total = len(self.trades)
        wins = sum(1 for t in self.trades if t.result == "WIN")
        losses = sum(1 for t in self.trades if t.result == "LOSS")
        ties = sum(1 for t in self.trades if t.result == "TIE")

        avg_mae = sum(t.mae for t in self.trades) / total if total else 0.0
        avg_mfe = sum(t.mfe for t in self.trades) / total if total else 0.0

        mode_counts: Dict[str, int] = {}
        for t in self.trades:
            mode_counts[t.market_mode] = mode_counts.get(t.market_mode, 0) + 1

        return {
            "symbol": self.symbol,
            "trade_duration_s": self.trade_duration_s,
            "payout_rate": self.payout_rate,
            "total_trades": total,
            "wins": wins,
            "losses": losses,
            "ties": ties,
            "win_rate": (wins / total) if total else 0.0,
            "avg_mae": avg_mae,
            "avg_mfe": avg_mfe,
            "modes": mode_counts,
        }

    def write_csv(self, out_path: str) -> None:
        if not self.trades:
            return
        fieldnames = list(asdict(self.trades[0]).keys())
        with open(out_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for t in self.trades:
                writer.writerow(asdict(t))


async def _amain() -> int:
    load_dotenv()
    api_token = os.getenv("DERIV_API_TOKEN")
    if not api_token:
        raise RuntimeError("DERIV_API_TOKEN is missing (set it in backend/.env)")

    parser = argparse.ArgumentParser()
    parser.add_argument("--symbol", default=os.getenv("BACKTEST_SYMBOL", os.getenv("SYMBOL", "1HZ75V")))
    parser.add_argument("--m1-count", type=int, default=int(os.getenv("BACKTEST_M1_COUNT", "5000")))
    parser.add_argument("--duration", type=int, default=int(os.getenv("TRADE_DURATION", "300")))
    parser.add_argument("--payout", type=float, default=float(os.getenv("BACKTEST_PAYOUT", "0.95")))
    parser.add_argument("--warmup", type=int, default=int(os.getenv("BACKTEST_WARMUP", "250")))
    parser.add_argument("--min-interval", type=int, default=int(os.getenv("BACKTEST_MIN_INTERVAL", "60")))
    parser.add_argument("--max-trades", type=int, default=int(os.getenv("BACKTEST_MAX_TRADES", "200")))
    args = parser.parse_args()

    bt = LiveReplayBacktester(
        api_token=api_token,
        symbol=str(args.symbol),
        trade_duration_s=int(args.duration),
        payout_rate=float(args.payout),
        warmup_m1=int(args.warmup),
        min_trade_interval_s=int(args.min_interval),
        max_trades=int(args.max_trades),
    )

    await bt.run(m1_count=int(args.m1_count))

    s = bt.summary()
    print("\n=== LIVE REPLAY BACKTEST SUMMARY ===")
    for k, v in s.items():
        print(f"{k}: {v}")

    ts = datetime.now(pytz.UTC).strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(os.path.dirname(__file__), f"backtest_live_replay_{args.symbol}_{ts}.csv")
    bt.write_csv(out_path)
    print(f"\nCSV saved: {out_path}")

    return 0


def main() -> int:
    return asyncio.run(_amain())


if __name__ == "__main__":
    raise SystemExit(main())
