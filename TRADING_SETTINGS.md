# Trading Settings Configuration

This document explains the configurable trading settings available in the bot.

## Settings Overview

### Symbol Selection
Choose which Volatility Index to trade:

| Symbol | Name | Tick Frequency | Characteristics |
|--------|------|----------------|-----------------|
| **1HZ10V** | Volatility 10 (1s) Index | 1 second | Lower volatility, smoother price action |
| **1HZ25V** | Volatility 25 (1s) Index | 1 second | Medium volatility |
| **1HZ50V** | Volatility 50 (1s) Index | 1 second | Medium-high volatility |
| **1HZ75V** | Volatility 75 (1s) Index | 1 second | High volatility (Default) |
| **1HZ100V** | Volatility 100 (1s) Index | 1 second | Highest volatility, more noise |

**Note:** These are the 1-second tick indices, optimal for M1 candle formation.

**Recommendation:** Start with **1HZ75V** - good balance of volatility and signal clarity.

---

### Contract Duration

Choose contract duration based on market mode:

| Duration | Best For | Why |
|----------|----------|-----|
| **180s (3 min)** | RANGING markets | Mean reversion happens quickly at extremes |
| **240s (4 min)** | UNCERTAIN markets | Middle ground, wait for clearer direction |
| **300s (5 min)** | TRENDING markets | Pullback reversals take time to develop (Recommended) |
| **360s (6 min)** | Strong trends | Extended trend continuation |
| **420s (7 min)** | Very strong trends | Maximum trend follow-through |

**Default:** 300s (5 minutes) - Optimal for the multi-timeframe strategy design

---

## How to Configure

### Via Frontend UI
1. Click **"Show Trading Settings"** button in Control Panel
2. Select your preferred **Symbol** from dropdown
3. Select your preferred **Contract Duration** from dropdown
4. Adjust **Take Profit Target** and **Stop Loss Limit** if needed
5. Click **"Save Settings"**

**Note:** Symbol and duration changes take effect on the next trade.

---

### Via .env File
Edit `backend/.env`:

```bash
# Symbol options: 1HZ10V, 1HZ25V, 1HZ50V, 1HZ75V, 1HZ100V (1-second tick indices)
SYMBOL=1HZ75V

# Contract Duration (in seconds)
# Recommended: 180-300s (3-5 minutes)
TRADE_DURATION=300
TRADE_DURATION_UNIT=s
```

Restart the bot for changes to take effect.

---

## Strategy-Specific Recommendations

### For Trend Pullback Strategy
- **Duration:** 300s (5 minutes)
- **Symbol:** 1HZ75V or 1HZ50V
- **Why:** Pullbacks need time to reverse back to trend direction

### For Mean Reversion Strategy
- **Duration:** 180s (3 minutes)
- **Symbol:** 1HZ100V or 1HZ75V
- **Why:** Reversals from extremes happen quickly

### For Uncertain Markets
- **Duration:** 240s (4 minutes)
- **Symbol:** 1HZ75V
- **Why:** Balanced approach while waiting for clearer signals

---

## Testing Different Configurations

**Recommended Testing Approach:**
1. Start with default: 1HZ75V @ 300s
2. Monitor win rate and average profit per trade
3. If winning but exiting too early → Increase duration to 360s
4. If losing to late reversals → Decrease duration to 240s
5. If too much noise/whipsaws → Try lower volatility symbol (1HZ50V)
6. If not enough signals → Try higher volatility symbol (1HZ100V)

**Track your results** for each configuration to find optimal settings for your trading style.

---

## Important Notes

⚠️ **Symbol and duration changes require bot restart to take full effect**
- Changes are saved immediately
- Active trades use old settings
- New trades use new settings

💡 **Strategy is designed for 3-5 minute timeframes**
- Shorter than 3 min: High noise, low win rate
- Longer than 7 min: Strategy not optimized for extended holds

📊 **Different symbols have different spread costs**
- Higher volatility = Higher spread
- Factor this into your profit targets
