# Trading Settings Configuration

This document explains the configurable trading settings available in the bot.

## Settings Overview

### Symbol Selection
Choose which Volatility Index to trade:

| Symbol | Name | Tick Frequency | Characteristics |
|--------|------|----------------|-----------------|
| **R_10** | Volatility 10 Index | 1 second | Lower volatility, smoother price action |
| **R_25** | Volatility 25 Index | 2 seconds | Medium volatility |
| **R_50** | Volatility 50 Index | 1 second | Medium-high volatility |
| **R_75** | Volatility 75 Index | 1 second | High volatility (Default) |
| **R_100** | Volatility 100 Index | 2 seconds | Highest volatility, more noise |

**Recommendation:** Start with **R_75** - good balance of volatility and signal clarity.

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
# Symbol options: R_10, R_25, R_50, R_75, R_100
SYMBOL=R_75

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
- **Symbol:** R_75 or R_50
- **Why:** Pullbacks need time to reverse back to trend direction

### For Mean Reversion Strategy
- **Duration:** 180s (3 minutes)
- **Symbol:** R_100 or R_75
- **Why:** Reversals from extremes happen quickly

### For Uncertain Markets
- **Duration:** 240s (4 minutes)
- **Symbol:** R_75
- **Why:** Balanced approach while waiting for clearer signals

---

## Testing Different Configurations

**Recommended Testing Approach:**
1. Start with default: R_75 @ 300s
2. Monitor win rate and average profit per trade
3. If winning but exiting too early → Increase duration to 360s
4. If losing to late reversals → Decrease duration to 240s
5. If too much noise/whipsaws → Try lower volatility symbol (R_50)
6. If not enough signals → Try higher volatility symbol (R_100)

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
