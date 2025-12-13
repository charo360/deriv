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
    """
    
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
    
    def _detect_market_mode(self, ind_m5: IndicatorValues, ind_m15: IndicatorValues) -> MarketMode:
        """Detect current market mode using ADX from M5 and M15."""
        # Use M5 ADX for more responsive detection
        adx = ind_m5.adx
        
        if adx > 25:
            # Strong trend
            if ind_m5.trend_up and ind_m15.trend_up:
                return MarketMode.TRENDING_UP
            elif ind_m5.trend_down and ind_m15.trend_down:
                return MarketMode.TRENDING_DOWN
            else:
                return MarketMode.UNCERTAIN
        elif adx < 20:
            return MarketMode.RANGING
        else:
            return MarketMode.UNCERTAIN
    
    def is_trading_allowed(self) -> tuple[bool, str]:
        """Check if trading is allowed (avoid server reset times)."""
        now = datetime.now(pytz.UTC)
        current_time = now.time()
        
        # Parse avoid times
        avoid_start = time(23, 55)
        avoid_end = time(0, 5)
        
        # Check if in avoid window (handles midnight crossing)
        if avoid_start <= current_time or current_time <= avoid_end:
            return False, "Server reset period - trading paused"
        
        return True, "OK"
    
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
        logger.info(f"M5: close={ind_m5.close:.2f}, RSI={ind_m5.rsi:.1f}, EMA50={ind_m5.ema_50:.2f}")
        logger.info(f"M15: close={ind_m15.close:.2f}, EMA200={ind_m15.ema_200:.2f}, trend_up={ind_m15.trend_up}, trend_down={ind_m15.trend_down}")
        
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
        
        # Return the stronger signal (minimum 60% confidence required)
        if rise_signal.confidence > fall_signal.confidence and rise_signal.confidence >= 60:
            logger.info(f">>> SELECTED: RISE with {rise_signal.confidence}% confidence ({market_mode.value})")
            return rise_signal
        elif fall_signal.confidence > rise_signal.confidence and fall_signal.confidence >= 60:
            logger.info(f">>> SELECTED: FALL with {fall_signal.confidence}% confidence ({market_mode.value})")
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
        
        # BLOCK: Don't buy when RSI is overbought (>65) - price already extended
        if ind_m5.rsi > 65:
            confluence_factors.append(f"BLOCKED: RSI too high for RISE ({ind_m5.rsi:.1f} > 65)")
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
        
        # MACD momentum confirmation on M5
        if ind_m5.macd_bullish:
            confluence_factors.append(f"M5: MACD bullish momentum (histogram={ind_m5.macd_histogram:.4f})")
            confidence += 15
        
        # M5: Look for pullback conditions
        # Price pulled back to EMA50 or lower BB
        pullback_to_ema = ind_m5.close <= ind_m5.ema_50 * 1.002  # Within 0.2% of EMA50
        pullback_to_bb = ind_m5.close <= ind_m5.bb_lower * 1.01  # Near lower BB
        
        if pullback_to_ema or pullback_to_bb:
            if pullback_to_ema:
                confluence_factors.append(f"M5: Pullback to EMA50 ({ind_m5.ema_50:.2f})")
            if pullback_to_bb:
                confluence_factors.append(f"M5: Pullback to lower BB ({ind_m5.bb_lower:.2f})")
            confidence += 25
            m5_confirmed = True
        
        # RSI in buy zone (40-55 in uptrend is good entry)
        if 35 <= ind_m5.rsi <= 55:
            confluence_factors.append(f"M5: RSI in buy zone ({ind_m5.rsi:.1f})")
            confidence += 20
            m5_confirmed = True
        
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
        
        # BLOCK: Don't sell when RSI is oversold (<35) - price already extended down
        if ind_m5.rsi < 35:
            confluence_factors.append(f"BLOCKED: RSI too low for FALL ({ind_m5.rsi:.1f} < 35)")
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
        
        # MACD momentum confirmation on M5
        if ind_m5.macd_bearish:
            confluence_factors.append(f"M5: MACD bearish momentum (histogram={ind_m5.macd_histogram:.4f})")
            confidence += 15
        
        # M5: Look for rally conditions
        # Price rallied to EMA50 or upper BB
        rally_to_ema = ind_m5.close >= ind_m5.ema_50 * 0.998  # Within 0.2% of EMA50
        rally_to_bb = ind_m5.close >= ind_m5.bb_upper * 0.99  # Near upper BB
        
        if rally_to_ema or rally_to_bb:
            if rally_to_ema:
                confluence_factors.append(f"M5: Rally to EMA50 ({ind_m5.ema_50:.2f})")
            if rally_to_bb:
                confluence_factors.append(f"M5: Rally to upper BB ({ind_m5.bb_upper:.2f})")
            confidence += 25
            m5_confirmed = True
        
        # RSI in sell zone (45-65 in downtrend is good entry)
        if 45 <= ind_m5.rsi <= 65:
            confluence_factors.append(f"M5: RSI in sell zone ({ind_m5.rsi:.1f})")
            confidence += 20
            m5_confirmed = True
        
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
        
        # M5: Price at lower extreme
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
        
        # M5: Price at upper extreme
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
                'rsi': round(ind_m1.rsi, 2),
                'stoch_k': round(ind_m1.stoch_k, 2),
                'stoch_d': round(ind_m1.stoch_d, 2),
                'ema_50': round(ind_m1.ema_50, 5),
                'ema_200': round(ind_m1.ema_200, 5),
                'adx': round(ind_m1.adx, 2),
                'plus_di': round(ind_m1.plus_di, 2),
                'minus_di': round(ind_m1.minus_di, 2),
                'macd': round(ind_m1.macd, 5),
                'macd_signal': round(ind_m1.macd_signal, 5),
                'macd_histogram': round(ind_m1.macd_histogram, 5)
            },
            'm5': {
                'close': round(ind_m5.close, 5),
                'bb_upper': round(ind_m5.bb_upper, 5),
                'bb_middle': round(ind_m5.bb_middle, 5),
                'bb_lower': round(ind_m5.bb_lower, 5),
                'rsi': round(ind_m5.rsi, 2),
                'stoch_k': round(ind_m5.stoch_k, 2),
                'stoch_d': round(ind_m5.stoch_d, 2),
                'ema_50': round(ind_m5.ema_50, 5),
                'ema_200': round(ind_m5.ema_200, 5),
                'adx': round(ind_m5.adx, 2),
                'plus_di': round(ind_m5.plus_di, 2),
                'minus_di': round(ind_m5.minus_di, 2),
                'macd': round(ind_m5.macd, 5),
                'macd_signal': round(ind_m5.macd_signal, 5),
                'macd_histogram': round(ind_m5.macd_histogram, 5)
            },
            'm15': {
                'close': round(ind_m15.close, 5),
                'bb_upper': round(ind_m15.bb_upper, 5),
                'bb_middle': round(ind_m15.bb_middle, 5),
                'bb_lower': round(ind_m15.bb_lower, 5),
                'rsi': round(ind_m15.rsi, 2),
                'stoch_k': round(ind_m15.stoch_k, 2),
                'stoch_d': round(ind_m15.stoch_d, 2),
                'ema_50': round(ind_m15.ema_50, 5),
                'ema_200': round(ind_m15.ema_200, 5),
                'adx': round(ind_m15.adx, 2),
                'plus_di': round(ind_m15.plus_di, 2),
                'minus_di': round(ind_m15.minus_di, 2),
                'macd': round(ind_m15.macd, 5),
                'macd_signal': round(ind_m15.macd_signal, 5),
                'macd_histogram': round(ind_m15.macd_histogram, 5)
            }
        }
