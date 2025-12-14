# Backtest Results Summary

## What Happened

I successfully ran your backtest on **5,000 historical candles** from Deriv (R_10 symbol, ~3.5 days of data).

### Results
- ✅ Backtest ran successfully
- ✅ Fetched data from Deriv API
- ✅ Analyzed 4,264 candles
- ❌ **0 trades executed** (no signals generated)

## Why No Trades?

Your strategy is **very strict** and requires perfect conditions:

### Current Requirements
1. **ADX must be > 27** (very strong trend) OR **< 18** (clear ranging)
2. **Both M5 and M15 timeframes must agree** on direction
3. **Minimum 60% confidence** required
4. **At least 2 out of 3 timeframes must confirm**

### What the Market Showed
- **100% of the time**: Market was "UNCERTAIN" (ADX between 18-27)
- **0% trending periods** (ADX > 27)
- **0% ranging periods** (ADX < 18)

The R_10 market during this period was **choppy/sideways** - not strong enough trends for your strategy.

## How to Fix This

You have 3 options:

### Option 1: Make Strategy Less Strict (Recommended)
Edit `backend/strategy.py`:

**Line 123** - Lower trending threshold:
```python
if adx > 22:  # Changed from 27
```

**Line 131** - Raise ranging threshold:
```python
elif adx < 20:  # Changed from 18
```

**Line 319** - Lower confidence requirement:
```python
if rise_adjusted > fall_adjusted and rise_adjusted >= 50 and rise_timeframes_agree >= 1:  # Changed from 60 and 2
```

### Option 2: Test Different Market Conditions
Try different symbols or time periods:
```powershell
# Test R_75 (higher volatility)
python backend/backtest_hybrid.py --symbol R_75 --candles 5000

# Test R_100 (even higher volatility)
python backend/backtest_hybrid.py --symbol R_100 --candles 5000
```

### Option 3: Test More Data
Sometimes you need more data to catch trending periods:
```powershell
python backend/backtest_hybrid.py --candles 10000
```

## Quick Start Commands

### Run basic backtest (what we just did):
```powershell
python backend/backtest_hybrid.py --candles 5000
```

### Test with relaxed settings (after editing strategy.py):
```powershell
python backend/backtest_hybrid.py --candles 5000
```

### Test different market:
```powershell
python backend/backtest_hybrid.py --symbol R_75 --candles 5000
```

## What the Files Do

- **`backend/backtest_hybrid.py`** - Main backtest script (fetches from Deriv, runs strategy, shows results)
- **`backend/strategy.py`** - Your trading rules (this is what needs adjusting)
- **`backtest_hybrid_results.json`** - Detailed results saved after each run
- **`BACKTEST_GUIDE.md`** - Full guide with all options

## Next Steps

1. **Either**: Edit `backend/strategy.py` to lower thresholds (see Option 1 above)
2. **Or**: Test a different symbol like R_75 or R_100
3. Run the backtest again
4. Check if you get signals and trades

## Need Help?

The backtest is working perfectly - it's just showing you that your strategy is very conservative and needs the right market conditions. This is actually good to know before live trading!

Let me know if you want me to:
- Adjust the strategy thresholds for you
- Test different symbols
- Explain any part in more detail
