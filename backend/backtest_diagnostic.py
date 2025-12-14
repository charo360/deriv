"""Diagnostic backtest to show what the strategy is seeing."""

import asyncio
import logging
from datetime import datetime
import pandas as pd

from deriv_client import DerivClient
from strategy import HybridAdaptiveStrategy
from indicators import TechnicalIndicators

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def diagnostic_backtest():
    """Run diagnostic to see market conditions."""
    import os
    from dotenv import load_dotenv
    
    load_dotenv()
    api_token = os.getenv('DERIV_API_TOKEN')
    
    client = DerivClient(api_token)
    strategy = HybridAdaptiveStrategy()
    
    # Fetch data
    logger.info("Fetching historical data...")
    await client.connect()
    
    response = await client._send({
        "ticks_history": "R_10",
        "adjust_start_time": 1,
        "count": 3000,
        "end": "latest",
        "granularity": 60,
        "style": "candles"
    })
    
    candles_data = response.get('candles', [])
    candles_m1 = [
        {
            'epoch': int(c['epoch']),
            'open': float(c['open']),
            'high': float(c['high']),
            'low': float(c['low']),
            'close': float(c['close'])
        }
        for c in candles_data
    ]
    
    await client.disconnect()
    
    logger.info(f"Fetched {len(candles_m1)} candles")
    
    # Resample
    df = pd.DataFrame(candles_m1)
    df['epoch'] = pd.to_datetime(df['epoch'], unit='s', utc=True)
    df.set_index('epoch', inplace=True)
    
    candles_m5 = []
    for idx, row in df.resample('5min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna().iterrows():
        candles_m5.append({'epoch': int(idx.timestamp()), 'open': float(row['open']), 'high': float(row['high']), 'low': float(row['low']), 'close': float(row['close'])})
    
    candles_m15 = []
    for idx, row in df.resample('15min').agg({'open': 'first', 'high': 'max', 'low': 'min', 'close': 'last'}).dropna().iterrows():
        candles_m15.append({'epoch': int(idx.timestamp()), 'open': float(row['open']), 'high': float(row['high']), 'low': float(row['low']), 'close': float(row['close'])})
    
    # Analyze market conditions
    indicators = TechnicalIndicators()
    
    logger.info("\n" + "="*80)
    logger.info("MARKET CONDITION DIAGNOSTIC")
    logger.info("="*80)
    
    # Sample last 500 candles
    window_size = 250
    adx_values = []
    rsi_values = []
    market_modes = {'TRENDING_UP': 0, 'TRENDING_DOWN': 0, 'RANGING': 0, 'UNCERTAIN': 0}
    
    for i in range(window_size, min(len(candles_m1), 1000)):
        m1_window = candles_m1[i-window_size:i]
        current_epoch = m1_window[-1]['epoch']
        m5_window = [c for c in candles_m5 if c['epoch'] <= current_epoch][-window_size:]
        m15_window = [c for c in candles_m15 if c['epoch'] <= current_epoch][-window_size:]
        
        if len(m5_window) < 50 or len(m15_window) < 50:
            continue
        
        ind_m5 = indicators.calculate(m5_window)
        if ind_m5:
            adx_values.append(ind_m5.adx)
            rsi_values.append(ind_m5.rsi)
            
            # Detect mode
            if ind_m5.adx > 27:
                if ind_m5.trend_up:
                    market_modes['TRENDING_UP'] += 1
                elif ind_m5.trend_down:
                    market_modes['TRENDING_DOWN'] += 1
                else:
                    market_modes['UNCERTAIN'] += 1
            elif ind_m5.adx < 18:
                market_modes['RANGING'] += 1
            else:
                market_modes['UNCERTAIN'] += 1
    
    if adx_values:
        logger.info(f"\nADX Statistics (M5):")
        logger.info(f"  Average: {sum(adx_values)/len(adx_values):.2f}")
        logger.info(f"  Min: {min(adx_values):.2f}")
        logger.info(f"  Max: {max(adx_values):.2f}")
        logger.info(f"  Times > 27 (trending threshold): {sum(1 for v in adx_values if v > 27)} ({sum(1 for v in adx_values if v > 27)/len(adx_values)*100:.1f}%)")
        logger.info(f"  Times < 18 (ranging threshold): {sum(1 for v in adx_values if v < 18)} ({sum(1 for v in adx_values if v < 18)/len(adx_values)*100:.1f}%)")
        logger.info(f"  Times 18-27 (uncertain): {sum(1 for v in adx_values if 18 <= v <= 27)} ({sum(1 for v in adx_values if 18 <= v <= 27)/len(adx_values)*100:.1f}%)")
    
    if rsi_values:
        logger.info(f"\nRSI Statistics (M5):")
        logger.info(f"  Average: {sum(rsi_values)/len(rsi_values):.2f}")
        logger.info(f"  Min: {min(rsi_values):.2f}")
        logger.info(f"  Max: {max(rsi_values):.2f}")
    
    total = sum(market_modes.values())
    if total > 0:
        logger.info(f"\nMarket Mode Distribution:")
        for mode, count in market_modes.items():
            logger.info(f"  {mode}: {count} ({count/total*100:.1f}%)")
    
    logger.info("\n" + "="*80)
    logger.info("RECOMMENDATIONS:")
    logger.info("="*80)
    
    avg_adx = sum(adx_values)/len(adx_values) if adx_values else 0
    
    if avg_adx < 20:
        logger.info("✗ Market is mostly ranging/uncertain (low ADX)")
        logger.info("  → Your strategy requires ADX > 27 for trending or < 18 for ranging")
        logger.info("  → Consider lowering ADX thresholds in strategy.py:")
        logger.info("     - Line 123: Change 'adx > 27' to 'adx > 22'")
        logger.info("     - Line 131: Change 'adx < 18' to 'adx < 20'")
    else:
        logger.info("✓ Market has some trending periods")
    
    if market_modes['UNCERTAIN'] / total > 0.7:
        logger.info("\n✗ 70%+ of time is UNCERTAIN (ADX between 18-27)")
        logger.info("  → Widen the ADX range or lower thresholds")
    
    logger.info("\nTo make strategy less strict:")
    logger.info("1. Lower ADX trending threshold (line 123): 27 → 22")
    logger.info("2. Raise ADX ranging threshold (line 131): 18 → 20")
    logger.info("3. Lower confidence requirement (line 319): 60 → 50")
    logger.info("4. Reduce timeframe agreement (line 319): 2/3 → 1/3")


if __name__ == "__main__":
    asyncio.run(diagnostic_backtest())
