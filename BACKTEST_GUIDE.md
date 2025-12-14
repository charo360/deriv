# How to Run a Backtest

This guide will help you test your trading strategy on historical data from Deriv.

## Prerequisites

1. Make sure you have a Deriv API token in your `.env` file:
   ```
   DERIV_API_TOKEN=your_token_here
   ```

2. Install required dependencies (if not already done):
   ```powershell
   pip install pandas pytz websockets python-dotenv pydantic
   ```

## Simple Backtest (Recommended for First Time)

Open PowerShell in your project folder and run:

```powershell
python backend/backtest_hybrid.py
```

This will:
- Fetch 2000 candles from Deriv for R_10 symbol
- Test your strategy on historical data
- Show you win rate, profit/loss, and other metrics
- Save detailed results to `backtest_hybrid_results.json`

## Custom Backtest Options

### Test Different Symbol
```powershell
python backend/backtest_hybrid.py --symbol R_75
```

### Test More Historical Data
```powershell
python backend/backtest_hybrid.py --candles 10000
```

### Change Starting Balance
```powershell
python backend/backtest_hybrid.py --initial-balance 5000 --initial-stake 20
```

### Use Live Deriv Payouts (More Realistic but Slower)
```powershell
python backend/backtest_hybrid.py --use-live-proposal-payout
```

### Full Custom Example
```powershell
python backend/backtest_hybrid.py --symbol R_10 --candles 5000 --initial-balance 1000 --initial-stake 10 --duration 180 --payout-rate 0.95
```

## Understanding the Results

After the backtest runs, you'll see:

- **Total candles analyzed**: How many price bars were checked
- **CALL/PUT signals**: How many buy/sell signals were generated
- **Executed trades**: How many trades were actually placed
- **Win rate**: Percentage of winning trades
- **Total profit**: Net profit/loss from all trades
- **Profit factor**: Ratio of gross wins to gross losses (>1 is good)
- **Max drawdown**: Largest peak-to-valley loss (lower is better)

## Common Options Explained

| Option | What it does | Example |
|--------|-------------|---------|
| `--symbol` | Which market to test | `R_10`, `R_25`, `R_50`, `R_75`, `R_100` |
| `--candles` | How much history to fetch | `2000` (default), `5000`, `10000` |
| `--initial-balance` | Starting account balance | `1000` (default) |
| `--initial-stake` | Base trade size | `10` (default) |
| `--duration` | Contract duration in seconds | `180` (3 minutes, default) |
| `--payout-rate` | Fixed payout rate for wins | `0.95` (95% profit on win) |
| `--use-live-proposal-payout` | Fetch real Deriv payouts | Slower but more accurate |

## Troubleshooting

**Error: "DERIV_API_TOKEN not found"**
- Add your Deriv API token to the `.env` file

**Error: "Connection failed"**
- Check your internet connection
- Verify your API token is valid

**Backtest runs but shows 0 trades**
- Your strategy might be too strict
- Try testing with more candles: `--candles 10000`
- Check the signal counts in the output

## Next Steps

1. Run a simple backtest first to see how it works
2. Experiment with different symbols and time periods
3. Compare results with different settings
4. Use the JSON output file for detailed analysis in Excel/Python
