"""Batch backtest runner for testing multiple symbols and durations."""
import asyncio
import subprocess
import pandas as pd
from datetime import datetime
import pytz

# Test configurations
SYMBOLS = ['1HZ10V', '1HZ25V', '1HZ50V', '1HZ75V', '1HZ100V']
DURATIONS = [180, 240, 300, 360, 420]  # 3, 4, 5, 6, 7 minutes
M1_COUNT = 3000
MAX_TRADES = 100
MAX_CONSECUTIVE_LOSSES = 3
LOSS_COOLDOWN_SECONDS = 600

results = []

print("=" * 70)
print("COMPREHENSIVE MARTINGALE STRATEGY BACKTEST")
print("=" * 70)
print(f"Testing {len(SYMBOLS)} symbols × {len(DURATIONS)} durations = {len(SYMBOLS) * len(DURATIONS)} configurations")
print()

for symbol in SYMBOLS:
    for duration in DURATIONS:
        print(f"\n{'='*70}")
        print(f"Testing: {symbol} with {duration}s duration ({duration//60} minutes)")
        print(f"{'='*70}")
        
        cmd = [
            'python', 'backend/backtest_live_replay.py',
            '--symbol', symbol,
            '--m1-count', str(M1_COUNT),
            '--duration', str(duration),
            '--max-trades', str(MAX_TRADES),
            '--max-consecutive-losses', str(MAX_CONSECUTIVE_LOSSES),
            '--loss-cooldown-seconds', str(LOSS_COOLDOWN_SECONDS)
        ]
        
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                # Parse summary from output
                output = result.stdout
                lines = output.split('\n')
                
                summary = {}
                for line in lines:
                    if 'total_trades:' in line:
                        summary['total_trades'] = int(line.split(':')[1].strip())
                    elif 'wins:' in line:
                        summary['wins'] = int(line.split(':')[1].strip())
                    elif 'losses:' in line:
                        summary['losses'] = int(line.split(':')[1].strip())
                    elif 'win_rate:' in line:
                        summary['win_rate'] = float(line.split(':')[1].strip())
                    elif 'max_loss_streak:' in line:
                        summary['max_loss_streak'] = int(line.split(':')[1].strip())
                    elif 'avg_mae:' in line:
                        summary['avg_mae'] = float(line.split(':')[1].strip())
                    elif 'avg_mfe:' in line:
                        summary['avg_mfe'] = float(line.split(':')[1].strip())
                
                if summary:
                    summary['symbol'] = symbol
                    summary['duration_s'] = duration
                    summary['duration_m'] = duration // 60
                    results.append(summary)
                    
                    print(f"✅ Completed: {summary.get('total_trades', 0)} trades, "
                          f"{summary.get('win_rate', 0):.1%} win-rate, "
                          f"max streak: {summary.get('max_loss_streak', 'N/A')}")
                else:
                    print(f"⚠️  No summary data found in output")
            else:
                print(f"❌ Failed with return code {result.returncode}")
                print(f"Error: {result.stderr[:200]}")
                
        except subprocess.TimeoutExpired:
            print(f"⏱️  Timeout after 5 minutes")
        except Exception as e:
            print(f"❌ Error: {e}")

# Create results DataFrame
if results:
    df = pd.DataFrame(results)
    
    # Sort by win_rate descending
    df = df.sort_values('win_rate', ascending=False)
    
    # Save to CSV
    timestamp = datetime.now(pytz.UTC).strftime("%Y%m%d_%H%M%S")
    csv_file = f'backend/batch_backtest_results_{timestamp}.csv'
    df.to_csv(csv_file, index=False)
    
    print("\n" + "=" * 70)
    print("BATCH BACKTEST RESULTS SUMMARY")
    print("=" * 70)
    print()
    
    # Top 5 configurations
    print("🏆 TOP 5 CONFIGURATIONS (by win-rate):")
    print()
    for idx, row in df.head(5).iterrows():
        print(f"{row['symbol']:8s} {row['duration_m']}min: "
              f"{row['win_rate']:.1%} win-rate, "
              f"{row['total_trades']:3d} trades, "
              f"max streak: {row['max_loss_streak']}")
    
    print()
    print("📊 STATISTICS BY SYMBOL:")
    print()
    symbol_stats = df.groupby('symbol').agg({
        'win_rate': 'mean',
        'total_trades': 'mean',
        'max_loss_streak': 'max'
    }).round(3)
    print(symbol_stats)
    
    print()
    print("📊 STATISTICS BY DURATION:")
    print()
    duration_stats = df.groupby('duration_m').agg({
        'win_rate': 'mean',
        'total_trades': 'mean',
        'max_loss_streak': 'max'
    }).round(3)
    print(duration_stats)
    
    print()
    print(f"✅ Results saved to: {csv_file}")
    print("=" * 70)
else:
    print("\n❌ No results collected")
