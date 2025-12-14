"""Hybrid Adaptive Strategy - Trend Following + Mean Reversion."""

from dataclasses import dataclass
from datetime import datetime, time
from enum import Enum
from typing import Optional, List, Dict
import pytz
import logging

from indicators import TechnicalIndicators, IndicatorValues
from config import trading_config

logger = logging.getLogger(__name__)


class Signal(Enum):
    RISE = "CALL"   # Predict price will go up
    FALL = "PUT"    # Predict price will go down
    NONE = "NONE"   # No signal


class MarketMode(Enum):
    TRENDING_UP = "TRENDING_UP"
    TRENDING_DOWN = "TRENDING_DOWN"
    RANGING = "RANGING"
    UNCERTAIN = "UNCERTAIN"


@dataclass
class TradeSignal:
    """A trading signal with all relevant data."""
    
    signal: Signal
    confidence: float  # 0-100
    timestamp: datetime
    price: float
    
    # Indicator values at signal time
    indicators: Dict
    
    # Confluence factors that triggered
    confluence_factors: List[str]
    
    # Timeframe confirmations
    m1_confirmed: bool
    m5_confirmed: bool
    m15_confirmed: bool
    
    # Market mode
    market_mode: str = "UNCERTAIN"


class HybridAdaptiveStrategy:
    """
    Hybrid Adaptive Strategy for Synthetic Indices.
    
    Uses ADX to detect market mode:
    - ADX > 25: TRENDING - Trade pullbacks WITH the trend
    - ADX < 20: RANGING - Use mean reversion at extremes
    - ADX 20-25: UNCERTAIN - Wait for clearer setup
    
    TRENDING UP Mode (ADX > 25, +DI > -DI):
    - Wait for pullback to EMA 50 or lower BB
    - Enter RISE when RSI bounces from 40-50 zone
    - Stochastic crosses up confirms entry
    
    TRENDING DOWN Mode (ADX > 25, -DI > +DI):
    - Wait for pullback to EMA 50 or upper BB  
    - Enter FALL when RSI bounces from 50-60 zone
    - Stochastic crosses down confirms entry
    
    RANGING Mode (ADX < 20):
    - Use classic mean reversion at BB extremes
    - RSI oversold/overbought for confirmation
    
    Time-Based Filters:
    - Optimal hours: 08:00-11:00 UTC, 13:00-16:00 UTC, 19:00-22:00 UTC
    - Avoid: Server reset (23:55-00:05 UTC)
    - Reduced confidence during off-peak hours
    """
    
    # Optimal trading hours (UTC) - these tend to have better price action
    OPTIMAL_HOURS = [
        (8, 11),   # Morning session
        (13, 16),  # Afternoon session  
        (19, 22),  # Evening session
    ]
    
    # Hours to completely avoid
    AVOID_HOURS = [
        (23, 24),  # Pre-reset
        (0, 1),    # Post-reset
    ]
    
    def __init__(self):
        self.indicators = TechnicalIndicators(
            bollinger_period=trading_config.bollinger_period,
            bollinger_std=trading_config.bollinger_std,
            rsi_period=trading_config.rsi_period,
            rsi_oversold=trading_config.rsi_oversold,
            rsi_overbought=trading_config.rsi_overbought,
            stochastic_k=trading_config.stochastic_k,
            stochastic_d=trading_config.stochastic_d,
            stochastic_smooth=trading_config.stochastic_smooth,
            stochastic_oversold=trading_config.stochastic_oversold,
            stochastic_overbought=trading_config.stochastic_overbought,
            ema_period=trading_config.ema_period
        )
        
        self.last_signal_time: Optional[datetime] = None
        self.min_signal_interval = 60  # Minimum seconds between signals
        
        # Time-based tracking
        self.hourly_stats: Dict[int, Dict[str, int]] = {h: {'wins': 0, 'losses': 0} for h in range(24)}
    
    def _detect_market_mode(self, ind_m5: IndicatorValues, ind_m15: IndicatorValues) -> MarketMode:
        """Detect current market mode using ADX from M5 and M15 with hysteresis."""
        # Use M5 ADX for more responsive detection
        adx = ind_m5.adx
        
        # Add hysteresis to prevent rapid mode switching
        # Enter trend: ADX > 27, Exit trend: ADX < 18
        if adx > 27:
            # Strong trend
            if ind_m5.trend_up and ind_m15.trend_up:
                return MarketMode.TRENDING_UP
            elif ind_m5.trend_down and ind_m15.trend_down:
                return MarketMode.TRENDING_DOWN
            else:
                return MarketMode.UNCERTAIN
        elif adx < 18:
            return MarketMode.RANGING
        else:
            return MarketMode.UNCERTAIN
    
    def is_trading_allowed(self) -> tuple[bool, str]:
        """Check if trading is allowed (avoid server reset times)."""
        uk_tz = pytz.timezone('Europe/London')
        now = datetime.now(uk_tz)
        current_time = now.time()
        
        # Parse avoid times
        avoid_start = time(23, 55)
        avoid_end = time(0, 5)
        
        # Check if in avoid window (handles midnight crossing)
        if avoid_start <= current_time or current_time <= avoid_end:
            return False, "Server reset period - trading paused"
        
        return True, "OK"
    
    def _get_time_confidence_bonus(self) -> tuple[int, str]:
        """
        Get confidence bonus/penalty based on current hour (UK time).
        
        Returns:
            tuple of (confidence_adjustment, reason)
        """
        uk_tz = pytz.timezone('Europe/London')
        now = datetime.now(uk_tz)
        current_hour = now.hour
        
        # Check if in avoid hours
        for start, end in self.AVOID_HOURS:
            if start <= current_hour < end:
                return -100, f"Avoid hour ({current_hour}:00 UTC) - no trading"
        
        # Check if in optimal hours
        for start, end in self.OPTIMAL_HOURS:
            if start <= current_hour < end:
                return 5, f"Optimal trading hour ({current_hour}:00 UTC)"
        
        # Off-peak hours - slight penalty
        return -5, f"Off-peak hour ({current_hour}:00 UTC)"
    
    def record_trade_result(self, hour: int, won: bool):
        """Record trade result for hourly statistics."""
        if won:
            self.hourly_stats[hour]['wins'] += 1
        else:
            self.hourly_stats[hour]['losses'] += 1
    
    def get_hourly_win_rate(self, hour: int) -> float:
        """Get win rate for a specific hour."""
        stats = self.hourly_stats[hour]
        total = stats['wins'] + stats['losses']
        if total == 0:
            return 0.5  # Default 50% if no data
        return stats['wins'] / total
    
    def analyze(
        self,
        candles_m1: List[dict],
        candles_m5: List[dict],
        candles_m15: List[dict]
    ) -> TradeSignal:
        """
        Analyze multiple timeframes and generate a trade signal.
        
        Args:
            candles_m1: 1-minute candles (trigger timeframe)
            candles_m5: 5-minute candles (alert timeframe)
            candles_m15: 15-minute candles (higher timeframe)
            
        Returns:
            TradeSignal with direction and confidence
        """
        # Check trading allowed
        allowed, reason = self.is_trading_allowed()
        if not allowed:
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=0,
                indicators={},
                confluence_factors=[reason],
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False
            )
        
        # Calculate indicators for each timeframe
        ind_m1 = self.indicators.calculate(candles_m1)
        ind_m5 = self.indicators.calculate(candles_m5)
        ind_m15 = self.indicators.calculate(candles_m15)
        
        if not all([ind_m1, ind_m5, ind_m15]):
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=0,
                indicators={},
                confluence_factors=["Insufficient data for indicators"],
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False
            )
        
        # Get divergence and candle patterns
        divergence = self.indicators.detect_divergence(candles_m5)
        patterns = self.indicators.detect_candle_pattern(candles_m1)
        
        # Detect market mode
        market_mode = self._detect_market_mode(ind_m5, ind_m15)
        
        # Log market mode and indicators
        logger.info(f"=== SIGNAL ANALYSIS ===")
        logger.info(f"MARKET MODE: {market_mode.value} (ADX={ind_m5.adx:.1f}, +DI={ind_m5.plus_di:.1f}, -DI={ind_m5.minus_di:.1f})")
        logger.info(f"M1: close={ind_m1.close:.2f}, RSI={ind_m1.rsi:.1f}, Stoch_K={ind_m1.stoch_k:.1f}")
        logger.info(f"M5: close={ind_m5.close:.2f}, RSI={ind_m5.rsi:.1f}, EMA50={ind_m5.ema_50:.2f}, BB_Width={ind_m5.bb_width:.4f}, Squeeze={ind_m5.bb_squeeze}")
        logger.info(f"M15: close={ind_m15.close:.2f}, EMA200={ind_m15.ema_200:.2f}, trend_up={ind_m15.trend_up}, trend_down={ind_m15.trend_down}")
        
        # Check for Bollinger Band squeeze (low volatility) - avoid trading unless breakout detected
        if ind_m5.bb_squeeze:
            # Check for breakout: price breaking out of BB with volume/momentum
            bb_breakout_up = ind_m5.close > ind_m5.bb_upper and ind_m5.rsi > 55
            bb_breakout_down = ind_m5.close < ind_m5.bb_lower and ind_m5.rsi < 45
            
            if not (bb_breakout_up or bb_breakout_down):
                logger.info("BB SQUEEZE detected - low volatility, avoiding trades")
                return TradeSignal(
                    signal=Signal.NONE,
                    confidence=0,
                    timestamp=datetime.now(pytz.UTC),
                    price=ind_m1.close,
                    indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
                    confluence_factors=[f"BB Squeeze (low volatility) - waiting for breakout"],
                    m1_confirmed=False,
                    m5_confirmed=False,
                    m15_confirmed=False,
                    market_mode=market_mode.value
                )
            else:
                logger.info(f"BB BREAKOUT detected during squeeze - proceeding with analysis")
        
        # Generate signals based on market mode
        if market_mode == MarketMode.TRENDING_UP:
            rise_signal = self._check_trend_pullback_rise(ind_m1, ind_m5, ind_m15, patterns, market_mode)
            fall_signal = self._empty_signal(ind_m1, ind_m5, ind_m15, market_mode)  # Don't short in uptrend
        elif market_mode == MarketMode.TRENDING_DOWN:
            fall_signal = self._check_trend_pullback_fall(ind_m1, ind_m5, ind_m15, patterns, market_mode)
            rise_signal = self._empty_signal(ind_m1, ind_m5, ind_m15, market_mode)  # Don't long in downtrend
        elif market_mode == MarketMode.RANGING:
            rise_signal = self._check_mean_reversion_rise(ind_m1, ind_m5, ind_m15, divergence, patterns, market_mode)
            fall_signal = self._check_mean_reversion_fall(ind_m1, ind_m5, ind_m15, divergence, patterns, market_mode)
        else:
            # Uncertain - wait for clearer setup
            logger.info("Market mode UNCERTAIN - waiting for clearer setup")
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=ind_m1.close,
                indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
                confluence_factors=[f"Market uncertain (ADX={ind_m5.adx:.1f}) - waiting"],
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False,
                market_mode=market_mode.value
            )
        
        logger.info(f"RISE confidence: {rise_signal.confidence}, FALL confidence: {fall_signal.confidence}")
        
        # Apply time-based confidence adjustment
        time_bonus, time_reason = self._get_time_confidence_bonus()
        logger.info(f"Time filter: {time_reason} (adjustment: {time_bonus:+d})")
        
        # Adjust confidence based on time
        rise_adjusted = rise_signal.confidence + time_bonus
        fall_adjusted = fall_signal.confidence + time_bonus
        
        # Check timeframe confluence - require at least 2 out of 3 timeframes to agree
        rise_timeframes_agree = sum([rise_signal.m1_confirmed, rise_signal.m5_confirmed, rise_signal.m15_confirmed])
        fall_timeframes_agree = sum([fall_signal.m1_confirmed, fall_signal.m5_confirmed, fall_signal.m15_confirmed])
        
        # Return the stronger signal (minimum 70% confidence + 3/3 timeframe confluence required)
        if rise_adjusted > fall_adjusted and rise_adjusted >= 70 and rise_timeframes_agree >= 3:
            # Update confluence factors with time info
            rise_signal.confluence_factors.append(time_reason)
            logger.info(f">>> SELECTED: RISE with {rise_adjusted}% confidence ({market_mode.value})")
            return rise_signal
        elif fall_adjusted > rise_adjusted and fall_adjusted >= 70 and fall_timeframes_agree >= 3:
            fall_signal.confluence_factors.append(time_reason)
            logger.info(f">>> SELECTED: FALL with {fall_adjusted}% confidence ({market_mode.value})")
            return fall_signal
        
        # No valid signal
        return TradeSignal(
            signal=Signal.NONE,
            confidence=0,
            timestamp=datetime.now(pytz.UTC),
            price=ind_m1.close,
            indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
            confluence_factors=[f"No confluence in {market_mode.value} mode - waiting"],
            m1_confirmed=False,
            m5_confirmed=False,
            m15_confirmed=False,
            market_mode=market_mode.value
        )
    
    def _empty_signal(
        self,
        ind_m1: IndicatorValues,
        ind_m5: IndicatorValues,
        ind_m15: IndicatorValues,
        market_mode: MarketMode
    ) -> TradeSignal:
        """Return an empty signal (used when direction is blocked by trend)."""
        return TradeSignal(
            signal=Signal.NONE,
            confidence=0,
            timestamp=datetime.now(pytz.UTC),
            price=ind_m1.close,
            indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
            confluence_factors=[f"Direction blocked - {market_mode.value}"],
            m1_confirmed=False,
            m5_confirmed=False,
            m15_confirmed=False,
            market_mode=market_mode.value
        )
    
    def _check_trend_pullback_rise(
        self,
        ind_m1: IndicatorValues,
        ind_m5: IndicatorValues,
        ind_m15: IndicatorValues,
        patterns: dict,
        market_mode: MarketMode
    ) -> TradeSignal:
        """Check for RISE signal in uptrend - buy the pullback."""
        confluence_factors = ["UPTREND DETECTED - Looking for pullback entry"]
        confidence = 0
        
        m15_confirmed = False
        m5_confirmed = False
        m1_confirmed = False
        
        # BLOCK: Don't buy when RSI is too high (>50) - price already extended
        # In uptrend, we want to buy pullbacks (RSI 38-50), not overbought levels
        if ind_m5.rsi > 50:
            confluence_factors.append(f"BLOCKED: RSI too high for RISE ({ind_m5.rsi:.1f} > 50) - wait for pullback")
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=ind_m1.close,
                indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
                confluence_factors=confluence_factors,
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False,
                market_mode=market_mode.value
            )
        
        # M15: Confirm uptrend
        if ind_m15.trend_up:
            confluence_factors.append(f"M15: Uptrend confirmed (+DI > -DI, above EMA50)")
            confidence += 15
            m15_confirmed = True
        
        # ADX Slope - trend strength momentum
        if ind_m5.adx_rising:
            confluence_factors.append(f"M5: ADX rising (slope={ind_m5.adx_slope:.1f}) - trend strengthening")
            confidence += 10
        elif ind_m5.adx_falling:
            confluence_factors.append(f"M5: ADX falling (slope={ind_m5.adx_slope:.1f}) - trend weakening")
            confidence -= 10  # Penalty for weakening trend
        
        # MACD momentum confirmation on M5
        if ind_m5.macd_bullish:
            confluence_factors.append(f"M5: MACD bullish momentum (histogram={ind_m5.macd_histogram:.4f})")
            confidence += 15
        
        # M5: Look for pullback conditions - MUST be near lower BB for RISE
        # Use BB %B to check position: <0.25 means in lower 25% of bands
        bb_percent = ind_m5.bb_percent
        near_lower_bb = bb_percent <= 0.25  # Price in lower 25% of BB range
        at_lower_bb = ind_m5.close <= ind_m5.bb_lower * 1.005  # Within 0.5% of lower BB
        
        if near_lower_bb or at_lower_bb:
            if at_lower_bb:
                confluence_factors.append(f"M5: At lower BB ({ind_m5.bb_lower:.2f})")
                confidence += 30  # Strong signal at BB
            else:
                confluence_factors.append(f"M5: Near lower BB zone (BB%={bb_percent:.2f})")
                confidence += 20
            m5_confirmed = True
        else:
            # Price not near lower BB - weak setup for RISE
            confluence_factors.append(f"M5: Price not at lower BB (BB%={bb_percent:.2f}) - weak setup")
        
        # RSI in buy zone (38-50 in uptrend is good entry) - REQUIRED
        if 38 <= ind_m5.rsi <= 50:
            confluence_factors.append(f"M5: RSI in buy zone ({ind_m5.rsi:.1f})")
            confidence += 20
            m5_confirmed = True
        else:
            # BLOCK: RSI outside ideal range for RISE in uptrend
            confluence_factors.append(f"BLOCKED: RSI outside buy zone ({ind_m5.rsi:.1f}) - need 38-50 range")
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=ind_m1.close,
                indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
                confluence_factors=confluence_factors,
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False,
                market_mode=market_mode.value
            )
        
        # M1: Entry trigger
        # Stochastic turning up
        if ind_m1.stoch_k > ind_m1.stoch_d and ind_m1.stoch_k < 50:
            confluence_factors.append(f"M1: Stochastic bullish cross ({ind_m1.stoch_k:.1f})")
            confidence += 15
            m1_confirmed = True
        
        # Bullish candle patterns
        if patterns.get('hammer') or patterns.get('engulfing_bullish'):
            pattern_name = 'Hammer' if patterns.get('hammer') else 'Bullish engulfing'
            confluence_factors.append(f"M1: {pattern_name} pattern")
            confidence += 15
            m1_confirmed = True
        
        # Bonus for full confluence in trend
        if m15_confirmed and m5_confirmed and m1_confirmed:
            confidence += 10
            confluence_factors.append("Full trend pullback confluence!")
        
        return TradeSignal(
            signal=Signal.RISE if confidence >= 60 else Signal.NONE,
            confidence=min(confidence, 100),
            timestamp=datetime.now(pytz.UTC),
            price=ind_m1.close,
            indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
            confluence_factors=confluence_factors,
            m1_confirmed=m1_confirmed,
            m5_confirmed=m5_confirmed,
            m15_confirmed=m15_confirmed,
            market_mode=market_mode.value
        )
    
    def _check_trend_pullback_fall(
        self,
        ind_m1: IndicatorValues,
        ind_m5: IndicatorValues,
        ind_m15: IndicatorValues,
        patterns: dict,
        market_mode: MarketMode
    ) -> TradeSignal:
        """Check for FALL signal in downtrend - sell the rally."""
        confluence_factors = ["DOWNTREND DETECTED - Looking for rally entry"]
        confidence = 0
        
        m15_confirmed = False
        m5_confirmed = False
        m1_confirmed = False
        
        # BLOCK: Don't sell when RSI is too low (<50) - price already extended down
        # In downtrend, we want to sell rallies (RSI 50-62), not oversold levels
        if ind_m5.rsi < 50:
            confluence_factors.append(f"BLOCKED: RSI too low for FALL ({ind_m5.rsi:.1f} < 50) - wait for rally")
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=ind_m1.close,
                indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
                confluence_factors=confluence_factors,
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False,
                market_mode=market_mode.value
            )
        
        # M15: Confirm downtrend
        if ind_m15.trend_down:
            confluence_factors.append(f"M15: Downtrend confirmed (-DI > +DI, below EMA50)")
            confidence += 15
            m15_confirmed = True
        
        # ADX Slope - trend strength momentum
        if ind_m5.adx_rising:
            confluence_factors.append(f"M5: ADX rising (slope={ind_m5.adx_slope:.1f}) - trend strengthening")
            confidence += 10
        elif ind_m5.adx_falling:
            confluence_factors.append(f"M5: ADX falling (slope={ind_m5.adx_slope:.1f}) - trend weakening")
            confidence -= 10  # Penalty for weakening trend
        
        # MACD momentum confirmation on M5
        if ind_m5.macd_bearish:
            confluence_factors.append(f"M5: MACD bearish momentum (histogram={ind_m5.macd_histogram:.4f})")
            confidence += 15
        
        # M5: Look for rally conditions - MUST be near upper BB for FALL
        # Use BB %B to check position: >0.8 means in upper 20% of bands
        bb_percent = ind_m5.bb_percent
        near_upper_bb = bb_percent >= 0.75  # Price in upper 25% of BB range
        at_upper_bb = ind_m5.close >= ind_m5.bb_upper * 0.995  # Within 0.5% of upper BB
        
        if near_upper_bb or at_upper_bb:
            if at_upper_bb:
                confluence_factors.append(f"M5: At upper BB ({ind_m5.bb_upper:.2f})")
                confidence += 30  # Strong signal at BB
            else:
                confluence_factors.append(f"M5: Near upper BB zone (BB%={bb_percent:.2f})")
                confidence += 20
            m5_confirmed = True
        else:
            # Price not near upper BB - weak setup for FALL
            confluence_factors.append(f"M5: Price not at upper BB (BB%={bb_percent:.2f}) - weak setup")
        
        # RSI in sell zone (50-62 in downtrend is good entry) - REQUIRED
        if 50 <= ind_m5.rsi <= 62:
            confluence_factors.append(f"M5: RSI in sell zone ({ind_m5.rsi:.1f})")
            confidence += 20
            m5_confirmed = True
        else:
            # BLOCK: RSI outside ideal range for FALL in downtrend
            confluence_factors.append(f"BLOCKED: RSI outside sell zone ({ind_m5.rsi:.1f}) - need 50-62 range")
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=ind_m1.close,
                indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
                confluence_factors=confluence_factors,
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False,
                market_mode=market_mode.value
            )
        
        # M1: Entry trigger
        # Stochastic turning down
        if ind_m1.stoch_k < ind_m1.stoch_d and ind_m1.stoch_k > 50:
            confluence_factors.append(f"M1: Stochastic bearish cross ({ind_m1.stoch_k:.1f})")
            confidence += 15
            m1_confirmed = True
        
        # Bearish candle patterns
        if patterns.get('shooting_star') or patterns.get('engulfing_bearish'):
            pattern_name = 'Shooting star' if patterns.get('shooting_star') else 'Bearish engulfing'
            confluence_factors.append(f"M1: {pattern_name} pattern")
            confidence += 15
            m1_confirmed = True
        
        # Bonus for full confluence in trend
        if m15_confirmed and m5_confirmed and m1_confirmed:
            confidence += 10
            confluence_factors.append("Full trend pullback confluence!")
        
        return TradeSignal(
            signal=Signal.FALL if confidence >= 60 else Signal.NONE,
            confidence=min(confidence, 100),
            timestamp=datetime.now(pytz.UTC),
            price=ind_m1.close,
            indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
            confluence_factors=confluence_factors,
            m1_confirmed=m1_confirmed,
            m5_confirmed=m5_confirmed,
            m15_confirmed=m15_confirmed,
            market_mode=market_mode.value
        )
    
    def _check_mean_reversion_rise(
        self,
        ind_m1: IndicatorValues,
        ind_m5: IndicatorValues,
        ind_m15: IndicatorValues,
        divergence: dict,
        patterns: dict,
        market_mode: MarketMode
    ) -> TradeSignal:
        """Check for RISE signal in ranging market - classic mean reversion."""
        confluence_factors = ["RANGING MARKET - Mean reversion mode"]
        confidence = 0
        
        m15_confirmed = False
        m5_confirmed = False
        m1_confirmed = False
        
        # M15: No strong trend bias needed in ranging
        if ind_m15.is_ranging:
            confluence_factors.append(f"M15: Confirmed ranging (ADX={ind_m15.adx:.1f})")
            confidence += 10
            m15_confirmed = True
        
        # MACD turning bullish adds confidence for mean reversion bounce
        if ind_m1.macd_bullish or ind_m1.macd_histogram > ind_m5.macd_histogram:
            confluence_factors.append(f"M1: MACD momentum turning bullish")
            confidence += 10
        
        # M5: Price at lower extreme - REQUIRED for mean reversion RISE
        # Must have EITHER price at lower BB OR RSI oversold
        at_extreme = ind_m5.price_at_lower_bb or ind_m5.rsi_oversold
        
        if not at_extreme:
            confluence_factors.append(f"BLOCKED: Not at extreme for RISE (BB={ind_m5.price_at_lower_bb}, RSI={ind_m5.rsi:.1f})")
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=ind_m1.close,
                indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
                confluence_factors=confluence_factors,
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False,
                market_mode=market_mode.value
            )
        
        if ind_m5.price_at_lower_bb:
            confluence_factors.append("M5: Price at lower Bollinger Band")
            confidence += 25
            m5_confirmed = True
        
        if ind_m5.rsi_oversold:
            confluence_factors.append(f"M5: RSI oversold ({ind_m5.rsi:.1f})")
            confidence += 20
            m5_confirmed = True
        
        if divergence.get('bullish_divergence'):
            confluence_factors.append("M5: Bullish RSI divergence")
            confidence += 15
        
        # M1: Entry trigger
        if ind_m1.stoch_oversold and ind_m1.stoch_k > ind_m1.stoch_d:
            confluence_factors.append(f"M1: Stochastic bullish cross ({ind_m1.stoch_k:.1f})")
            confidence += 15
            m1_confirmed = True
        
        if patterns.get('hammer') or patterns.get('engulfing_bullish'):
            pattern_name = 'Hammer' if patterns.get('hammer') else 'Bullish engulfing'
            confluence_factors.append(f"M1: {pattern_name} pattern")
            confidence += 10
            m1_confirmed = True
        
        # Bonus for full confluence
        if m5_confirmed and m1_confirmed:
            confidence += 10
            confluence_factors.append("Mean reversion setup confirmed!")
        
        return TradeSignal(
            signal=Signal.RISE if confidence >= 60 else Signal.NONE,
            confidence=min(confidence, 100),
            timestamp=datetime.now(pytz.UTC),
            price=ind_m1.close,
            indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
            confluence_factors=confluence_factors,
            m1_confirmed=m1_confirmed,
            m5_confirmed=m5_confirmed,
            m15_confirmed=m15_confirmed,
            market_mode=market_mode.value
        )
    
    def _check_mean_reversion_fall(
        self,
        ind_m1: IndicatorValues,
        ind_m5: IndicatorValues,
        ind_m15: IndicatorValues,
        divergence: dict,
        patterns: dict,
        market_mode: MarketMode
    ) -> TradeSignal:
        """Check for FALL signal in ranging market - classic mean reversion."""
        confluence_factors = ["RANGING MARKET - Mean reversion mode"]
        confidence = 0
        
        m15_confirmed = False
        m5_confirmed = False
        m1_confirmed = False
        
        # M15: No strong trend bias needed in ranging
        if ind_m15.is_ranging:
            confluence_factors.append(f"M15: Confirmed ranging (ADX={ind_m15.adx:.1f})")
            confidence += 10
            m15_confirmed = True
        
        # MACD turning bearish adds confidence for mean reversion drop
        if ind_m1.macd_bearish or ind_m1.macd_histogram < ind_m5.macd_histogram:
            confluence_factors.append(f"M1: MACD momentum turning bearish")
            confidence += 10
        
        # M5: Price at upper extreme - REQUIRED for mean reversion FALL
        # Must have EITHER price at upper BB OR RSI overbought
        at_extreme = ind_m5.price_at_upper_bb or ind_m5.rsi_overbought
        
        if not at_extreme:
            confluence_factors.append(f"BLOCKED: Not at extreme for FALL (BB={ind_m5.price_at_upper_bb}, RSI={ind_m5.rsi:.1f})")
            return TradeSignal(
                signal=Signal.NONE,
                confidence=0,
                timestamp=datetime.now(pytz.UTC),
                price=ind_m1.close,
                indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
                confluence_factors=confluence_factors,
                m1_confirmed=False,
                m5_confirmed=False,
                m15_confirmed=False,
                market_mode=market_mode.value
            )
        
        if ind_m5.price_at_upper_bb:
            confluence_factors.append("M5: Price at upper Bollinger Band")
            confidence += 25
            m5_confirmed = True
        
        if ind_m5.rsi_overbought:
            confluence_factors.append(f"M5: RSI overbought ({ind_m5.rsi:.1f})")
            confidence += 20
            m5_confirmed = True
        
        if divergence.get('bearish_divergence'):
            confluence_factors.append("M5: Bearish RSI divergence")
            confidence += 15
        
        # M1: Entry trigger
        if ind_m1.stoch_overbought and ind_m1.stoch_k < ind_m1.stoch_d:
            confluence_factors.append(f"M1: Stochastic bearish cross ({ind_m1.stoch_k:.1f})")
            confidence += 15
            m1_confirmed = True
        
        if patterns.get('shooting_star') or patterns.get('engulfing_bearish'):
            pattern_name = 'Shooting star' if patterns.get('shooting_star') else 'Bearish engulfing'
            confluence_factors.append(f"M1: {pattern_name} pattern")
            confidence += 10
            m1_confirmed = True
        
        # Bonus for full confluence
        if m5_confirmed and m1_confirmed:
            confidence += 10
            confluence_factors.append("Mean reversion setup confirmed!")
        
        return TradeSignal(
            signal=Signal.FALL if confidence >= 60 else Signal.NONE,
            confidence=min(confidence, 100),
            timestamp=datetime.now(pytz.UTC),
            price=ind_m1.close,
            indicators=self._format_indicators(ind_m1, ind_m5, ind_m15),
            confluence_factors=confluence_factors,
            m1_confirmed=m1_confirmed,
            m5_confirmed=m5_confirmed,
            m15_confirmed=m15_confirmed,
            market_mode=market_mode.value
        )
    
    def _format_indicators(
        self,
        ind_m1: IndicatorValues,
        ind_m5: IndicatorValues,
        ind_m15: IndicatorValues
    ) -> dict:
        """Format indicator values for output."""
        return {
            'm1': {
                'close': round(ind_m1.close, 5),
                'bb_upper': round(ind_m1.bb_upper, 5),
                'bb_middle': round(ind_m1.bb_middle, 5),
                'bb_lower': round(ind_m1.bb_lower, 5),
                'bb_width': round(ind_m1.bb_width, 4),
                'bb_squeeze': bool(ind_m1.bb_squeeze),
                'rsi': round(ind_m1.rsi, 2),
                'stoch_k': round(ind_m1.stoch_k, 2),
                'stoch_d': round(ind_m1.stoch_d, 2),
                'ema_50': round(ind_m1.ema_50, 5),
                'ema_200': round(ind_m1.ema_200, 5),
                'adx': round(ind_m1.adx, 2),
                'plus_di': round(ind_m1.plus_di, 2),
                'minus_di': round(ind_m1.minus_di, 2),
                'adx_slope': round(float(ind_m1.adx_slope), 2),
                'adx_rising': bool(ind_m1.adx_rising),
                'macd': round(ind_m1.macd, 5),
                'macd_signal': round(ind_m1.macd_signal, 5),
                'macd_histogram': round(ind_m1.macd_histogram, 5)
            },
            'm5': {
                'close': round(ind_m5.close, 5),
                'bb_upper': round(ind_m5.bb_upper, 5),
                'bb_middle': round(ind_m5.bb_middle, 5),
                'bb_lower': round(ind_m5.bb_lower, 5),
                'bb_width': round(ind_m5.bb_width, 4),
                'bb_squeeze': bool(ind_m5.bb_squeeze),
                'rsi': round(ind_m5.rsi, 2),
                'stoch_k': round(ind_m5.stoch_k, 2),
                'stoch_d': round(ind_m5.stoch_d, 2),
                'ema_50': round(ind_m5.ema_50, 5),
                'ema_200': round(ind_m5.ema_200, 5),
                'adx': round(ind_m5.adx, 2),
                'plus_di': round(ind_m5.plus_di, 2),
                'minus_di': round(ind_m5.minus_di, 2),
                'adx_slope': round(float(ind_m5.adx_slope), 2),
                'adx_rising': bool(ind_m5.adx_rising),
                'macd': round(ind_m5.macd, 5),
                'macd_signal': round(ind_m5.macd_signal, 5),
                'macd_histogram': round(ind_m5.macd_histogram, 5)
            },
            'm15': {
                'close': round(ind_m15.close, 5),
                'bb_upper': round(ind_m15.bb_upper, 5),
                'bb_middle': round(ind_m15.bb_middle, 5),
                'bb_lower': round(ind_m15.bb_lower, 5),
                'bb_width': round(ind_m15.bb_width, 4),
                'bb_squeeze': bool(ind_m15.bb_squeeze),
                'rsi': round(ind_m15.rsi, 2),
                'stoch_k': round(ind_m15.stoch_k, 2),
                'stoch_d': round(ind_m15.stoch_d, 2),
                'ema_50': round(ind_m15.ema_50, 5),
                'ema_200': round(ind_m15.ema_200, 5),
                'adx': round(ind_m15.adx, 2),
                'plus_di': round(ind_m15.plus_di, 2),
                'minus_di': round(ind_m15.minus_di, 2),
                'adx_slope': round(float(ind_m15.adx_slope), 2),
                'adx_rising': bool(ind_m15.adx_rising),
                'macd': round(ind_m15.macd, 5),
                'macd_signal': round(ind_m15.macd_signal, 5),
                'macd_histogram': round(ind_m15.macd_histogram, 5)
            }
        }
