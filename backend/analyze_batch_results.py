import pandas as pd
import sys

csv_file = sys.argv[1] if len(sys.argv) > 1 else 'backend/batch_backtest_results_20251215_150045.csv'
df = pd.read_csv(csv_file)

print('=' * 80)
print('COMPREHENSIVE BACKTEST RESULTS - ALL SYMBOLS & DURATIONS')
print('=' * 80)
print()

# Show all results sorted by win_rate
print('ALL CONFIGURATIONS (sorted by win-rate):')
print()
df_display = df[['symbol', 'duration_m', 'total_trades', 'wins', 'losses', 'win_rate', 'max_loss_streak', 'avg_mae', 'avg_mfe']]
df_display['win_rate_pct'] = df_display['win_rate'].apply(lambda x: f'{x:.1%}')
print(df_display.to_string(index=False))
print()

print('=' * 80)
print('TOP 10 BEST CONFIGURATIONS')
print('=' * 80)
for idx, row in df.head(10).iterrows():
    print(f"{idx+1:2d}. {row['symbol']:8s} @ {row['duration_m']}min: "
          f"{row['win_rate']:.1%} win-rate ({row['wins']}W/{row['losses']}L), "
          f"MAE: {row['avg_mae']:.2f}, MFE: {row['avg_mfe']:.2f}")
print()

print('=' * 80)
print('ANALYSIS BY SYMBOL')
print('=' * 80)
symbol_stats = df.groupby('symbol').agg({
    'win_rate': ['mean', 'min', 'max'],
    'total_trades': 'mean',
    'max_loss_streak': 'max'
}).round(3)
symbol_stats.columns = ['Avg_WinRate', 'Min_WinRate', 'Max_WinRate', 'Avg_Trades', 'Max_Streak']
print(symbol_stats)
print()

print('=' * 80)
print('ANALYSIS BY DURATION')
print('=' * 80)
duration_stats = df.groupby('duration_m').agg({
    'win_rate': ['mean', 'min', 'max'],
    'total_trades': 'mean',
    'max_loss_streak': 'max'
}).round(3)
duration_stats.columns = ['Avg_WinRate', 'Min_WinRate', 'Max_WinRate', 'Avg_Trades', 'Max_Streak']
print(duration_stats)
print()

print('=' * 80)
print('RECOMMENDATIONS FOR MARTINGALE')
print('=' * 80)
print()

# Find best overall
best = df.iloc[0]
print(f"🏆 BEST OVERALL CONFIGURATION:")
print(f"   Symbol: {best['symbol']}")
print(f"   Duration: {best['duration_m']} minutes ({best['duration_s']} seconds)")
print(f"   Win-rate: {best['win_rate']:.1%}")
print(f"   Trades: {best['total_trades']}")
print(f"   Max loss streak: {best['max_loss_streak']} ✅")
print()

# Find most consistent symbol
symbol_consistency = df.groupby('symbol')['win_rate'].agg(['mean', 'std'])
most_consistent = symbol_consistency.sort_values(['mean', 'std'], ascending=[False, True]).iloc[0]
most_consistent_symbol = symbol_consistency.sort_values(['mean', 'std'], ascending=[False, True]).index[0]
print(f"🎯 MOST CONSISTENT SYMBOL:")
print(f"   Symbol: {most_consistent_symbol}")
print(f"   Average win-rate: {most_consistent['mean']:.1%}")
print(f"   Std deviation: {most_consistent['std']:.3f}")
print()

# Best by symbol
print("📊 BEST DURATION FOR EACH SYMBOL:")
for symbol in df['symbol'].unique():
    symbol_df = df[df['symbol'] == symbol]
    best_for_symbol = symbol_df.iloc[0]
    print(f"   {symbol:8s}: {best_for_symbol['duration_m']}min @ {best_for_symbol['win_rate']:.1%}")
print()

print('=' * 80)
print('MARTINGALE SAFETY VERIFICATION')
print('=' * 80)
all_safe = df['max_loss_streak'].max() <= 3
print(f"All configurations maintain max_loss_streak <= 3: {'✅ YES' if all_safe else '❌ NO'}")
print(f"Maximum loss streak observed: {df['max_loss_streak'].max()}")
print()

if all_safe:
    print("✅ ALL CONFIGURATIONS ARE MARTINGALE-SAFE!")
    print()
    print("Recommended configuration for live trading:")
    print(f"  SYMBOL={best['symbol']}")
    print(f"  DURATION={best['duration_s']}")
    print(f"  Expected win-rate: {best['win_rate']:.1%}")
    print(f"  Expected trades/day: ~{int(best['total_trades'] * 24 / 8)} (assuming 8h trading)")
else:
    print("⚠️ WARNING: Some configurations exceeded max loss streak!")

print('=' * 80)
